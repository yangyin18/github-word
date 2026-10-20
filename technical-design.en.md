# GitHub Translation Tool — Technical Solution Document
Version v0.1 · Draft Date 2026-10-15 · Based on PRD v0.1
This document is the technical design for implementation, corresponding to the functional requirements FR-01 ~ FR-08 in the PRD.
## Table of Contents
[Technical Selection](#1-technical-selection)
[System Architecture](#2-system-architecture)
[Data Model Design](#3-data-model-design)
[API Interface Design](#4-api-interface-design)
[Implementation Plan for Core Modules](#5-implementation-plan-for-core-modules)
[Error Handling and Retry Mechanism](#6-error-handling-and-retry-mechanism)
[Security and Privacy](#7-security-and-privacy)
[Project Directory Structure](#8-project-directory-structure)
[Deployment Plan](#9-deployment-plan)
[TBD Decision Records](#10-tbd-decision-records)
## 1. Technical Selection
### 1.1 Overview of Selection
| Level | Technology | Rationale |
|---|---|---|
| Backend Framework | Python 3.11 + FastAPI | Native asynchronous support, suitable for I/O-bound tasks (GitHub API + concurrent API calls to translation engines); automatically generates OpenAPI documentation |
| Frontend Framework | Vue 3 + Vite + TypeScript | Reactive data binding suitable for parallel translation and segment editing; Vite build speed |
| UI Component Library | Element Plus | Comprehensive Chinese documentation, rich in table, dialog, and editor components |
| Markdown Parsing | `markdown-it-py` (backend) / `marked` (frontend preview) | Used for segment parsing in the backend, and for rendering previews of translations in the frontend |
| Database | SQLite (development) / PostgreSQL (production) | Zero-configuration during development; smooth migration to production |
| Cache | Redis (optional) | Caches translation results and rate limit counters |
| HTTP Client | `httpx` (asynchronous) | Asynchronous calls to GitHub API and translation engines |
| GitHub API | REST API v3 + `httpx` | Direct calls, no need for additional dependencies; publicly accessible resources can be accessed without a token (use token when rate limits are more generous) |
| Translation Engine | Abstract interface + multiple implementations (Mock / Google / DeepL) | Decoupling for easy switching and testing |
| Task Queue | FastAPI BackgroundTasks (P0) / Celery + Redis (P1+) | Background tasks suffice for P0; persistent queues are needed for P1 PR triggers |
### 1.2 Translation Engine Abstraction
Define a unified interface to support multiple implementations:
# app/services/translator/base.py
from abc import ABC, abstractmethod

class BaseTranslator(ABC):
    @abstractmethod
    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """翻译单段文本"""
        ...

    @abstractmethod
    async def translate_batch(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        """批量翻译，默认逐段调用，子类可覆盖优化"""
        ...
Implementation classes:
`MockTranslator`: For development and testing, returns the original text with a `[translation]` prefix
`GoogleTranslator`: Calls the Google Translate API
`DeepLTranslator`: Calls the DeepL API
Switch through configuration `TRANSLATOR_PROVIDER`.
### 1.3 Supported Language List (Q-02 Decision)
Initial support: `zh` (Chinese), `en` (English), `ja` (Japanese), `ko` (Korean), `fr` (French), `de` (German), `es` (Spanish), `ru` (Russian).
Decision: Source language is automatically detected when set to `auto`, target language is selected from the above list.
## 2. System Architecture
### 2.1 Overall Architecture
┌─────────────────────────────────────────────────────────┐
│                        前端 (Vue3)                       │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ 任务提交  │  │ 译文对照视图  │  │ 分段手动编辑器    │  │
│  └──────────┘  └──────────────┘  └──────────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP / JSON
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    后端 (FastAPI)                        │
│  ┌───────────────────────────────────────────────────┐  │
│  │                  API 层 (Routers)                  │  │
│  │  tasks / segments / languages / webhook / glossary │  │
│  └─────────────────────┬─────────────────────────────┘  │
│                        ▼                                │
│  ┌───────────────────────────────────────────────────┐  │
│  │                 服务层 (Services)                   │  │
│  │  TaskService / GitHubService / ParserService      │  │
│  │  Translator / GlossaryService / AssemblerService  │  │
│  └─────────────────────┬─────────────────────────────┘  │
│                        ▼                                │
│  ┌───────────────────────────────────────────────────┐  │
│  │              数据访问层 (Repositories)              │  │
│  │         TaskRepo / SegmentRepo / GlossaryRepo     │  │
│  └─────────────────────┬─────────────────────────────┘  │
│                        ▼                                │
│  ┌───────────────────────────────────────────────────┐  │
│  │              数据库 (SQLite / PostgreSQL)           │  │
│  └───────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
    GitHub API     翻译引擎 API    Redis (缓存)
### 2.2 Layered Responsibilities
| Layer | Responsibilities | Prohibitions |
|---|---|---|
| API Layer | Parameter validation, response packaging, calling service layer | Do not write business logic |
| Service Layer | Business orchestration, state transition, calling external services | Do not directly operate on the database |
| Data Access Layer | CRUD, querying | Do not contain business judgment |
## 3. Data model design
### 3.1 Table structure
**tasks table**
| Field | Type | Description |
|---|---|---|
| id | UUID PK | Task ID |
| resource_type | VARCHAR(20) | issue / pull_request / readme / repo_meta |
| resource_url | TEXT | GitHub resource URL |
| repo_full_name | VARCHAR(255) | Repository full name owner/repo |
| resource_number | INTEGER NULL | Issue/PR number |
| source_lang | VARCHAR(10) | Source language (auto indicates auto detection) |
| target_lang | VARCHAR(10) | Target language |
| status | VARCHAR(20) | Status: created/fetching/fetched/parsing/translating/completed/partial_failed/failed |
| source_content | TEXT | Retrieved original Markdown |
| error_message | TEXT NULL | Error message |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Update time |
**segments table**
| Field | Type | Description |
|---|---|---|
| id | UUID PK | Segment ID |
| task_id | UUID FK | Associated task |
| sequence | INTEGER | Sequence number (ensures order) |
| segment_type | VARCHAR(20) | text / code_block / inline_code / comment / link / mention |
| translatable | BOOLEAN | Translatable |
| source_text | TEXT | Original text |
| translated_text | TEXT NULL | Translated text |
| status | VARCHAR(20) | pending / translated / failed / manually_edited |
| error_message | TEXT NULL | Failure reason |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Update time |
**glossary table**
| Field | Type | Description |
|---|---|---|
| id | UUID PK | Glossary ID |
| source_term | VARCHAR(255) | Source term |
| target_term | VARCHAR(255) | Target term |
| source_lang | VARCHAR(10) | Source language |
| target_lang | VARCHAR(10) | Target language |
| created_at | TIMESTAMP | Creation time |
### 3.2 Indexes
`tasks(status)` — Query tasks by status
`segments(task_id, sequence)` — Retrieve ordered segments by task
`glossary(source_lang, target_lang)` — Query glossary by language pair
## 4. API interface design
### 4.1 Interface overview
| Method | Path | Description | Priority |
|---|---|---|---|
| POST | `/api/tasks` | Create translation task | P0 |
| GET | `/api/tasks/{task_id}` | Query task status | P0 |
| GET | `/api/tasks/{task_id}/segments` | Get segment list (with source/translation) | P0 |
| GET | `/api/tasks/{task_id}/result` | Get assembled translation | P0 |
| PUT | `/api/tasks/{task_id}/segments/{segment_id}` | Manually correct segment translation | P1 |
| POST | `/api/tasks/{task_id}/retry` | Retry failed segments | P1 |
| GET | `/api/languages` | Get supported language list | P0 |
| GET | `/api/glossary` | Query glossary | P1 |
| POST | `/api/glossary` | Add new term | P1 |
| DELETE | `/api/glossary/{id}` | Delete term | P1 |
| POST | `/api/webhook/github` | GitHub event callback (PR triggered) | P1 |
### 4.2 API details
#### POST `/api/tasks` — Create translation task
**Request body:**
{
  "resource_url": "https://github.com/owner/repo/issues/123",
  "target_lang": "zh",
  "source_lang": "auto"
}
**Response 201:**
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "fetching",
  "resource_type": "issue"
}
**Error response 400:**
{
  "error": "invalid_resource",
  "message": "仅支持公开 GitHub 资源（Issue/PR/README）",
  "detail": "资源格式示例: https://github.com/owner/repo/issues/123"
}
#### GET `/api/tasks/{task_id}` — Query task status
**Response 200:**
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "resource_type": "issue",
  "resource_url": "...",
  "source_lang": "auto",
  "target_lang": "zh",
  "total_segments": 12,
  "translated_segments": 10,
  "failed_segments": 0,
  "error_message": null,
  "created_at": "2026-10-15T10:00:00Z",
  "updated_at": "2026-10-15T10:00:05Z"
}
#### GET `/api/tasks/{task_id}/segments` — Get segment list
**Response 200:**
{
  "segments": [
    {
      "segment_id": "...",
      "sequence": 1,
      "segment_type": "text",
      "translatable": true,
      "source_text": "This is a sample issue.",
      "translated_text": "这是一个示例 Issue。",
      "status": "translated"
    },
    {
      "segment_id": "...",
      "sequence": 2,
      "segment_type": "code_block",
      "translatable": false,
      "source_text": "```python\nprint('hello')\n```",
      "translated_text": null,
      "status": "pending"
    }
  ]
}
#### GET `/api/tasks/{task_id}/result` — Get assembled translation
**Query parameter:** `format=markdown|comparison`
**Response 200 (format=markdown):**
{
  "translated_markdown": "# 标题译文\n\n正文译文...\n\n```python\nprint('hello')\n```"
}
#### PUT `/api/tasks/{task_id}/segments/{segment_id}` — Manually correct
**Request body:**
{
  "translated_text": "用户修正后的译文"
}
**Response 200:** Returns the updated segment, `status` changed to `manually_edited`.
#### POST `/api/tasks/{task_id}/retry` — Retry failed segments
**Response 200:**
{
  "retried_count": 2,
  "status": "translating"
}
#### GET `/api/languages` — Supported languages
**Response 200:**
{
  "source_languages": [{"code": "auto", "name": "自动检测"}, {"code": "en", "name": "英语"}, ...],
  "target_languages": [{"code": "zh", "name": "中文"}, {"code": "en", "name": "英语"}, ...]
}
#### POST `/api/webhook/github` — GitHub callback
**Triggered by:** PR creation/update, PR comment.
**Processing logic:**
Verify Webhook signature (`X-Hub-Signature-256`).
Identify event type: `pull_request` (opened/synchronize) or `issue_comment` (PR comment contains `/translate`).
Extract `repo_full_name`, `pr_number`, target language (parsed from comment parameters, default `zh`).
Create translation task and execute asynchronously.
Generate translation and call GitHub API to post a comment under the PR.
## 5. Core module implementation plan
### 5.1 GitHub content retrieval (corresponding to FR-02)
**Module:** `app/services/github_service.py`
**Functionality:**
Parse resource URL, identify type (issue / pull_request / readme).
Call GitHub REST API to retrieve content.
Handling rate limits (read `X-RateLimit-*` response headers).
**Key Implementation:**
class GitHubService:
    def parse_url(self, url: str) -> dict:
        """解析 URL → {repo, type, number}"""
# Match paths for issue / pull / blob/README etc.

    async def fetch_content(self, resource: dict) -> str:
        """根据资源类型调用对应 API，返回 Markdown 原文"""
        match resource["type"]:
            case "issue" | "pull_request":
                resp = await self.client.get(f"/repos/{repo}/issues/{number}")
                return resp.json()["body"] or ""
            case "readme":
                resp = await self.client.get(f"/repos/{repo}/readme")
                return base64.b64decode(resp.json()["content"]).decode("utf-8")

    async def post_pr_comment(self, repo: str, pr_number: int, body: str):
        """发布 PR 评论（FR-07）"""
**Rate Limit Handling:**
No Token: 60 times/hour; With Token: 5000 times/hour.
Exceeding the limit returns `403`, parses `X-RateLimit-Reset` to calculate retry time, does not automatically retry indefinitely.
### 5.2 Markdown Parsing and Segmentation (corresponding to FR-03)
**Module:** `app/services/parser_service.py`
**Solution:** Uses `markdown-it-py` to parse Markdown into a token stream, traverses tokens to generate segments.
**Segmentation Rules:**
| Token Type | segment_type | translatable |
|---|---|---|
| heading_open + inline + heading_close | text | true |
| paragraph_open + inline + paragraph_close | text | true |
| bullet_list / ordered_list inline | text | true |
| table_cell inline | text | true |
| fence (code block) | code_block | false |
| code_inline | inline_code | false |
| link_open / link_close wrapped text | link | true (only text, URL preserved) |
| image | link | false (URL preserved) |
**Comment Handling (within fence):**
def split_code_and_comments(code: str, lang: str) -> list[Segment]:
    """将代码块拆分为代码行(不可译)与注释行(可译)"""
    comment_patterns = {
        "python": [r"^\s*#"],
        "javascript": [r"^\s*//", r"^\s*/\*", r"^\s*\*"],
        "html": [r"^\s*<!--"],
        ...
    }
# Line-by-line judgment, comment line → translatable=True, preserves comment symbol prefix
**Degradation Strategy:** On parsing exceptions, treat the entire text as a single `text` segment, logs warning logs.
### 5.3 Translation Execution (corresponding to FR-04)
**Module:** `app/services/translator/`
**Process:**
Filter segments where `translatable=True`.
Batch call the translation engine (concurrency capped at 5 to avoid triggering rate limits of the translation service).
Post-process the returned translations for terminology correction.
If a segment fails, it does not interrupt the overall process; mark the segment as `failed`.
**Terminology Post-processing (FR-08):**
def apply_glossary(translated: str, source_lang: str, target_lang: str) -> str:
    """单词边界安全 + 最长匹配替换译文术语"""
    terms = glossary_repo.get_by_lang_pair(source_lang, target_lang)
# Sort by term length in descending order (longest match first)
    terms.sort(key=lambda t: len(t.target_term), reverse=True)
    result = translated
    for term in terms:
# Use \b word boundary to avoid intra-word replacement
        pattern = re.compile(r'\b' + re.escape(term.target_term) + r'\b')
        result = pattern.sub(term.target_term, result)  # 此处应为源→目标映射
    return result
**Note:** The terminology table stores `source_term → target_term`. During post-processing, we search for "potential inconsistencies in the translation engine's output" in the target language and replace them with the standard `target_term`. In actual implementation, you need to maintain a mapping from "translation synonyms in the target language → standard term" or directly replace common translations of `source_term` in the translation. Here, it is simplified to: if the target language translation contains common variants of `target_term`, they are统一为 `target_term`.
**Code Comment Translation:** Extract comment text (remove symbols) → Translate → Reassemble with comment symbols and indentation.
### 5.4 Translation Assembly (corresponding to FR-05)
**Module:** `app/services/assembler_service.py`
**Logic:**
Fetch all segments in ascending order of `sequence`.
If translation is successful, use `translated_text` (use `source_text` + `<!-- 翻译失败 -->` if translation fails).
For non-translatable segments, concatenate `source_text` directly.
Insert appropriate line breaks between segments based on type (empty line between headings/paragraphs, empty lines before and after code blocks).
**Side-by-side view:** Render the original and translated texts side by side in the frontend without relying on backend assembly.
### 5.5 Trigger translation based on PR (corresponding to FR-07)
**Module:** `app/routers/webhook.py` + `app/services/pr_service.py`
**Process:**
Webhook receives PR / comment events.
Verify the signature.
Determine if it is a translation request: For PR events, check if `action=opened` or `synchronize`, and if automatic translation is configured for the repository.
For comment events, check if the comment content starts with `/translate`, and parse the target language parameter.
Create a task → execute asynchronously → after translation is generated, call `post_pr_comment` to publish.
If there is an existing translation comment for the same PR, update the comment (find the bot comment's comment_id).
## 6. Error handling and retry mechanism
### 6.1 Error classification
| Error Type | Handling Method |
|---|---|
| Resource validation failure | Synchronously return 400, do not create a task |
| GitHub API 404 | Task status → failed, message: "Resource not found" |
| GitHub API 403 (rate limit) | Task status → failed, return remaining quota and retry time |
| GitHub API network timeout | Retry once, if still fails → failed |
| Translation engine unavailable | Task status → failed, message: "Translation service unavailable" |
| Single segment translation failure | Mark the segment as failed, continue with other segments |
| Translation breaks code structure | Discard the translation, keep the original text, and issue an alert |
### 6.2 Retry Strategy
**Crawling Retry:** Network timeout retry 1 time with an interval of 2 seconds.
**Translation Retry:** Single segment failure does not automatically retry; manual trigger of `POST /retry` by the user.
**Rate Limit Retry:** Does not automatically retry; prompts the user to retry after the `X-RateLimit-Reset` time.
### 6.3 Error Response Specification
All error responses have a unified format:
{
  "error": "错误代码",
  "message": "用户可读的错误说明",
  "detail": "可选：下一步操作建议或示例",
  "retry_after": 60  // 可选，秒
}
## 7. Security and Privacy
### 7.1 Data Boundaries
Only access GitHub public resources: Validate the `private` field of the repository to be `false` before calling the API.
Do not persist sensitive credentials: GitHub Token and translation service keys are only read from environment variables and not written to the database.
Minimal storage: The task table only stores resource URL, source content, translation, status, and error information.
### 7.2 Webhook Security
Verify the `X-Hub-Signature-256` signature using HMAC-SHA256.
Verify the event source is GitHub (IP whitelisting is optional).
### 7.3 Input Validation
Resource URL format validation (regular match `github.com/{owner}/{repo}/...`).
The target language must be in the supported list.
Source content size limit: single task not exceeding 1MB (Q-04 decision).
## 8. Project directory structure
github-translation/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口
│   │   ├── config.py                # 配置（环境变量）
│   │   ├── routers/
│   │   │   ├── tasks.py             # 任务相关接口
│   │   │   ├── segments.py          # 分段接口
│   │   │   ├── languages.py         # 语言列表
│   │   │   ├── glossary.py          # 术语表
│   │   │   └── webhook.py           # GitHub Webhook
│   │   ├── services/
│   │   │   ├── task_service.py      # 任务编排
│   │   │   ├── github_service.py    # GitHub API 调用
│   │   │   ├── parser_service.py    # Markdown 解析分段
│   │   │   ├── assembler_service.py # 译文组装
│   │   │   ├── glossary_service.py  # 术语后处理
│   │   │   └── translator/
│   │   │       ├── base.py          # 翻译引擎抽象
│   │   │       ├── mock.py          # Mock 实现
│   │   │       ├── google.py        # Google 翻译
│   │   │       └── deepl.py         # DeepL 翻译
│   │   ├── repositories/
│   │   │   ├── task_repo.py
│   │   │   ├── segment_repo.py
│   │   │   └── glossary_repo.py
│   │   ├── models/                  # SQLAlchemy 模型
│   │   ├── schemas/                 # Pydantic 请求/响应模型
│   │   └── utils/
│   │       ├── errors.py            # 统一错误处理
│   │       └── markdown.py          # Markdown 解析工具
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── TaskSubmit.vue       # 提交翻译任务
│   │   │   ├── TaskDetail.vue       # 任务详情（状态+分段）
│   │   │   └── ComparisonView.vue   # 原文-译文对照
│   │   ├── components/
│   │   │   ├── SegmentEditor.vue    # 分段编辑器
│   │   │   └── MarkdownPreview.vue  # Markdown 渲染
│   │   ├── api/                     # 接口封装
│   │   ├── stores/                  # Pinia 状态管理
│   │   └── router/
│   ├── package.json
│   └── vite.config.ts
└── docs/
    ├── prd.md                       # 需求规格文档
    └── technical-design.md          # 本文档
## 9. Deployment方案
### 9.1 Development environment
Backend: `uvicorn app.main:app --reload --port 8000`
Frontend: `npm run dev` (port 5173, proxy `/api` to 8000)
Database: SQLite local file
### 9.2 Production environment
Backend: Docker containers + Uvicorn / Gunicorn
Frontend: `npm run build` then served static files by Nginx, reverse proxy `/api` to backend
Database: PostgreSQL
Process management: Docker Compose (backend + frontend + postgres + redis)
### 9.3 Environment variables
# Backend
DATABASE_URL=sqlite:///./data.db
GITHUB_TOKEN=                    # 可选，提升速率限制
TRANSLATOR_PROVIDER=mock         # mock / google / deepl
GOOGLE_API_KEY=
DEEPL_API_KEY=
GITHUB_WEBHOOK_SECRET=           # Webhook 签名密钥

# Frontend
VITE_API_BASE_URL=/api
## 10. TBD Decision Record
6 unresolved issues in the PRD, the following decisions are made in this technical solution (subject to change):
| No. | Issue | Decision |
|---|---|---|
| Q-01 | Translation Engine Selection | Abstract Interface + Multiple Implementations, Default Mock, Switchable to Google/DeepL |
| Q-02 | Supported Language List | zh/en/ja/ko/fr/de/es/ru, Source Language Support auto |
| Q-03 | PR Trigger Method | Webhook Receives Events, Bot Account Publishes Comments (Only Comment Permissions) |
| Q-04 | Content Size Limit | Single Task Source Content ≤ 1MB, Number of Segments ≤ 500 |
| Q-05 | Term Matching Strategy | Word Boundary Safe + Longest Match, Preserve Original Term Capitalization |
| Q-06 | Storage Medium and Cycle | SQLite (Development)/PostgreSQL (Production), Task Retention 30 Days (Configurable) |
*— Technical Solution Document Ends —*
