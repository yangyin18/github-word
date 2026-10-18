# GitHub 翻译工具 — 技术方案文档

> 版本 v0.1 · 编写日期 2026-10-15 · 基于 PRD v0.1
> 本文档为实现层面的技术设计，对应 PRD 中的功能需求 FR-01 ~ FR-08。

## 目录

1. [技术选型](#1-技术选型)
2. [系统架构](#2-系统架构)
3. [数据模型设计](#3-数据模型设计)
4. [API 接口设计](#4-api-接口设计)
5. [核心模块实现方案](#5-核心模块实现方案)
6. [错误处理与重试机制](#6-错误处理与重试机制)
7. [安全与隐私](#7-安全与隐私)
8. [项目目录结构](#8-项目目录结构)
9. [部署方案](#9-部署方案)
10. [TBD 决策记录](#10-tbd-决策记录)

---

## 1. 技术选型

### 1.1 选型总览

| 层级 | 技术 | 选型理由 |
|---|---|---|
| 后端框架 | Python 3.11 + FastAPI | 原生异步支持，适合 I/O 密集型（GitHub API + 翻译引擎并发调用）；自动生成 OpenAPI 文档 |
| 前端框架 | Vue 3 + Vite + TypeScript | 响应式数据绑定适合译文对照与分段编辑；Vite 构建快 |
| UI 组件库 | Element Plus | 中文文档完善，表格/对话框/编辑器组件丰富 |
| Markdown 解析 | `markdown-it-py`（后端）/ `marked`（前端预览） | 后端用于分段解析，前端用于译文渲染预览 |
| 数据库 | SQLite（开发）/ PostgreSQL（生产） | 开发期零配置；生产可平滑迁移 |
| 缓存 | Redis（可选） | 翻译结果缓存、速率限制计数 |
| HTTP 客户端 | `httpx`（异步） | 异步调用 GitHub API 与翻译引擎 |
| GitHub API | REST API v3 + `httpx` | 直接调用，无需重依赖；公开资源无需 Token 也可访问（速率限制更宽松时用 Token） |
| 翻译引擎 | 抽象接口 + 多实现（Mock / Google / DeepL） | 解耦，便于切换与测试 |
| 任务队列 | FastAPI BackgroundTasks（P0）/ Celery + Redis（P1+） | P0 用后台任务即可；P1 PR 触发需要持久化队列 |

### 1.2 翻译引擎抽象

定义统一接口，支持多种实现：

```python
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
```

实现类：
- `MockTranslator`：开发/测试用，返回原文 + `[翻译]` 前缀
- `GoogleTranslator`：调用 Google Translate API
- `DeepLTranslator`：调用 DeepL API

通过配置 `TRANSLATOR_PROVIDER` 切换。

### 1.3 支持语言列表（Q-02 决策）

首批支持：`zh`（中文）、`en`（英语）、`ja`（日语）、`ko`（韩语）、`fr`（法语）、`de`（德语）、`es`（西班牙语）、`ru`（俄语）。

> 决策：源语言支持自动检测（传 `auto`），目标语言从上述列表选择。

---

## 2. 系统架构

### 2.1 整体架构

```
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
```

### 2.2 分层职责

| 层 | 职责 | 禁止 |
|---|---|---|
| API 层 | 参数校验、响应封装、调用服务层 | 不写业务逻辑 |
| 服务层 | 业务编排、状态流转、调用外部服务 | 不直接操作数据库 |
| 数据访问层 | CRUD、查询 | 不含业务判断 |

---

## 3. 数据模型设计

### 3.1 表结构

**tasks 表**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | 任务 ID |
| resource_type | VARCHAR(20) | issue / pull_request / readme / repo_meta |
| resource_url | TEXT | GitHub 资源 URL |
| repo_full_name | VARCHAR(255) | 仓库全名 owner/repo |
| resource_number | INTEGER NULL | Issue/PR 编号 |
| source_lang | VARCHAR(10) | 源语言（auto 表示自动检测） |
| target_lang | VARCHAR(10) | 目标语言 |
| status | VARCHAR(20) | 状态：created/fetching/fetched/parsing/translating/completed/partial_failed/failed |
| source_content | TEXT | 抓取的原始 Markdown |
| error_message | TEXT NULL | 错误信息 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

**segments 表**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | 分段 ID |
| task_id | UUID FK | 所属任务 |
| sequence | INTEGER | 序号（保证顺序） |
| segment_type | VARCHAR(20) | text / code_block / inline_code / comment / link / mention |
| translatable | BOOLEAN | 是否可译 |
| source_text | TEXT | 原文 |
| translated_text | TEXT NULL | 译文 |
| status | VARCHAR(20) | pending / translated / failed / manually_edited |
| error_message | TEXT NULL | 失败原因 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

**glossary 表**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | 术语 ID |
| source_term | VARCHAR(255) | 源术语 |
| target_term | VARCHAR(255) | 目标术语 |
| source_lang | VARCHAR(10) | 源语言 |
| target_lang | VARCHAR(10) | 目标语言 |
| created_at | TIMESTAMP | 创建时间 |

### 3.2 索引

- `tasks(status)` — 按状态查询任务
- `segments(task_id, sequence)` — 按任务取有序分段
- `glossary(source_lang, target_lang)` — 按语言对查术语表

---

## 4. API 接口设计

### 4.1 接口总览

| 方法 | 路径 | 说明 | 优先级 |
|---|---|---|---|
| POST | `/api/tasks` | 创建翻译任务 | P0 |
| GET | `/api/tasks/{task_id}` | 查询任务状态 | P0 |
| GET | `/api/tasks/{task_id}/segments` | 获取分段列表（含原文/译文） | P0 |
| GET | `/api/tasks/{task_id}/result` | 获取组装后的译文 | P0 |
| PUT | `/api/tasks/{task_id}/segments/{segment_id}` | 手动修正分段译文 | P1 |
| POST | `/api/tasks/{task_id}/retry` | 重试失败分段 | P1 |
| GET | `/api/languages` | 获取支持语言列表 | P0 |
| GET | `/api/glossary` | 查询术语表 | P1 |
| POST | `/api/glossary` | 新增术语 | P1 |
| DELETE | `/api/glossary/{id}` | 删除术语 | P1 |
| POST | `/api/webhook/github` | GitHub 事件回调（PR 触发） | P1 |

### 4.2 接口详情

#### POST `/api/tasks` — 创建翻译任务

**请求体：**
```json
{
  "resource_url": "https://github.com/owner/repo/issues/123",
  "target_lang": "zh",
  "source_lang": "auto"
}
```

**响应 201：**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "fetching",
  "resource_type": "issue"
}
```

**错误响应 400：**
```json
{
  "error": "invalid_resource",
  "message": "仅支持公开 GitHub 资源（Issue/PR/README）",
  "detail": "资源格式示例: https://github.com/owner/repo/issues/123"
}
```

#### GET `/api/tasks/{task_id}` — 查询任务状态

**响应 200：**
```json
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
```

#### GET `/api/tasks/{task_id}/segments` — 获取分段列表

**响应 200：**
```json
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
```

#### GET `/api/tasks/{task_id}/result` — 获取组装译文

**Query 参数：** `format=markdown|comparison`

**响应 200 (format=markdown)：**
```json
{
  "translated_markdown": "# 标题译文\n\n正文译文...\n\n```python\nprint('hello')\n```"
}
```

#### PUT `/api/tasks/{task_id}/segments/{segment_id}` — 手动修正

**请求体：**
```json
{
  "translated_text": "用户修正后的译文"
}
```

**响应 200：** 返回更新后的分段，`status` 变为 `manually_edited`。

#### POST `/api/tasks/{task_id}/retry` — 重试失败分段

**响应 200：**
```json
{
  "retried_count": 2,
  "status": "translating"
}
```

#### GET `/api/languages` — 支持语言

**响应 200：**
```json
{
  "source_languages": [{"code": "auto", "name": "自动检测"}, {"code": "en", "name": "英语"}, ...],
  "target_languages": [{"code": "zh", "name": "中文"}, {"code": "en", "name": "英语"}, ...]
}
```

#### POST `/api/webhook/github` — GitHub 回调

**触发：** PR 创建/更新、PR 评论。

**处理逻辑：**
1. 验证 Webhook 签名（`X-Hub-Signature-256`）。
2. 识别事件类型：`pull_request`（opened/synchronize）或 `issue_comment`（PR 评论含 `/translate`）。
3. 提取 `repo_full_name`、`pr_number`、目标语言（从评论参数解析，默认 `zh`）。
4. 创建翻译任务并异步执行。
5. 译文生成后，调用 GitHub API 在 PR 下发布评论。

---

## 5. 核心模块实现方案

### 5.1 GitHub 内容获取（对应 FR-02）

**模块：** `app/services/github_service.py`

**功能：**
- 解析资源 URL，识别类型（issue / pull_request / readme）。
- 调用 GitHub REST API 获取内容。
- 处理速率限制（读取 `X-RateLimit-*` 响应头）。

**关键实现：**
```python
class GitHubService:
    def parse_url(self, url: str) -> dict:
        """解析 URL → {repo, type, number}"""
        # 匹配 issue / pull / blob/README 等路径

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
```

**速率限制处理：**
- 无 Token：60 次/小时；有 Token：5000 次/小时。
- 达限时返回 `403`，解析 `X-RateLimit-Reset` 计算重试时间，不自动无限重试。

### 5.2 Markdown 解析与分段（对应 FR-03）

**模块：** `app/services/parser_service.py`

**方案：** 使用 `markdown-it-py` 解析 Markdown 为 token 流，遍历 token 生成分段。

**分段规则：**

| Token 类型 | segment_type | translatable |
|---|---|---|
| heading_open + inline + heading_close | text | true |
| paragraph_open + inline + paragraph_close | text | true |
| bullet_list / ordered_list 中的 inline | text | true |
| table_cell 中的 inline | text | true |
| fence（代码块） | code_block | false |
| code_inline | inline_code | false |
| link_open / link_close 包裹的文本 | link | true（仅文字，URL 保留） |
| image | link | false（URL 保留） |

**代码注释处理（fence 内）：**
```python
def split_code_and_comments(code: str, lang: str) -> list[Segment]:
    """将代码块拆分为代码行(不可译)与注释行(可译)"""
    comment_patterns = {
        "python": [r"^\s*#"],
        "javascript": [r"^\s*//", r"^\s*/\*", r"^\s*\*"],
        "html": [r"^\s*<!--"],
        ...
    }
    # 逐行判断，注释行 → translatable=True，保留注释符号前缀
```

**降级策略：** 解析异常时，将全文作为单个 `text` 分段，记录告警日志。

### 5.3 翻译执行（对应 FR-04）

**模块：** `app/services/translator/`

**流程：**
1. 筛选 `translatable=True` 的分段。
2. 批量调用翻译引擎（并发数限制为 5，避免触发翻译服务限速）。
3. 对返回译文做术语表后处理校正。
4. 单段失败不中断整体，标记该段 `failed`。

**术语后处理（FR-08）：**
```python
def apply_glossary(translated: str, source_lang: str, target_lang: str) -> str:
    """单词边界安全 + 最长匹配替换译文术语"""
    terms = glossary_repo.get_by_lang_pair(source_lang, target_lang)
    # 按术语长度降序排列（最长匹配优先）
    terms.sort(key=lambda t: len(t.target_term), reverse=True)
    result = translated
    for term in terms:
        # 使用 \b 单词边界，避免词内替换
        pattern = re.compile(r'\b' + re.escape(term.target_term) + r'\b')
        result = pattern.sub(term.target_term, result)  # 此处应为源→目标映射
    return result
```

> **注意：** 术语表存储的是 `source_term → target_term`。后处理时，是在译文（目标语言）中查找"翻译引擎可能译出的不一致说法"并替换为标准 `target_term`。实际实现需维护"译文同义词 → 标准术语"的映射，或直接在译文中对 `source_term` 的常见译文做替换。此处简化为：译文中若出现 `target_term` 的常见变体，统一为 `target_term`。

**代码注释翻译：** 提取注释文本（去掉符号）→ 翻译 → 拼回注释符号与缩进。

### 5.4 译文组装（对应 FR-05）

**模块：** `app/services/assembler_service.py`

**逻辑：**
1. 按 `sequence` 升序取全部分段。
2. 可译分段取 `translated_text`（失败则取原文 + `<!-- 翻译失败 -->`）。
3. 不可译分段取 `source_text` 原样拼接。
4. 分段间根据类型插入合适的换行（标题/段落间空行，代码块前后空行）。

**对照视图：** 前端按分段并排渲染原文与译文，不依赖后端组装。

### 5.5 PR 触发翻译（对应 FR-07）

**模块：** `app/routers/webhook.py` + `app/services/pr_service.py`

**流程：**
1. Webhook 接收 PR / 评论事件。
2. 校验签名。
3. 判断是否为翻译请求：
   - PR 事件：`action=opened` 或 `synchronize`，且配置了自动翻译该仓库。
   - 评论事件：评论内容以 `/translate` 开头，解析目标语言参数。
4. 创建任务 → 异步执行 → 译文生成后调用 `post_pr_comment` 发布。
5. 同一 PR 已有翻译评论时，更新评论（通过查找 bot 评论的 comment_id）。

---

## 6. 错误处理与重试机制

### 6.1 错误分类

| 错误类型 | 处理方式 |
|---|---|
| 资源校验失败 | 同步返回 400，不创建任务 |
| GitHub API 404 | 任务状态 → failed，提示"资源不存在" |
| GitHub API 403（限速） | 任务状态 → failed，返回剩余配额与重试时间 |
| GitHub API 网络超时 | 重试 1 次，仍失败 → failed |
| 翻译引擎不可用 | 任务状态 → failed，提示"翻译服务不可用" |
| 单分段翻译失败 | 标记该段 failed，继续其余分段 |
| 译文破坏代码结构 | 丢弃译文，保留原文，标记告警 |

### 6.2 重试策略

- **抓取重试：** 网络超时重试 1 次，间隔 2 秒。
- **翻译重试：** 单段失败不自动重试，由用户手动触发 `POST /retry`。
- **限速重试：** 不自动重试，提示用户在 `X-RateLimit-Reset` 时间后重试。

### 6.3 错误响应规范

所有错误响应统一格式：
```json
{
  "error": "错误代码",
  "message": "用户可读的错误说明",
  "detail": "可选：下一步操作建议或示例",
  "retry_after": 60  // 可选，秒
}
```

---

## 7. 安全与隐私

### 7.1 数据边界

- 仅访问 GitHub 公开资源：调用 API 前校验仓库 `private` 字段为 `false`。
- 不持久化敏感凭证：GitHub Token、翻译服务密钥仅从环境变量读取，不写入数据库。
- 最小存储：任务表仅存资源 URL、源内容、译文、状态、错误信息。

### 7.2 Webhook 安全

- 校验 `X-Hub-Signature-256` 签名，使用 HMAC-SHA256。
- 校验事件来源为 GitHub（IP 白名单可选）。

### 7.3 输入校验

- 资源 URL 格式校验（正则匹配 `github.com/{owner}/{repo}/...`）。
- 目标语言必须在支持列表内。
- 源内容大小限制：单任务不超过 1MB（Q-04 决策）。

---

## 8. 项目目录结构

```
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
```

---

## 9. 部署方案

### 9.1 开发环境

- 后端：`uvicorn app.main:app --reload --port 8000`
- 前端：`npm run dev`（端口 5173，代理 `/api` 到 8000）
- 数据库：SQLite 本地文件

### 9.2 生产环境

- 后端：Docker 容器 + Uvicorn / Gunicorn
- 前端：`npm run build` 后由 Nginx 托管静态文件，`/api` 反向代理到后端
- 数据库：PostgreSQL
- 进程管理：Docker Compose（backend + frontend + postgres + redis）

### 9.3 环境变量

```env
# 后端
DATABASE_URL=sqlite:///./data.db
GITHUB_TOKEN=                    # 可选，提升速率限制
TRANSLATOR_PROVIDER=mock         # mock / google / deepl
GOOGLE_API_KEY=
DEEPL_API_KEY=
GITHUB_WEBHOOK_SECRET=           # Webhook 签名密钥

# 前端
VITE_API_BASE_URL=/api
```

---

## 10. TBD 决策记录

PRD 中 6 项未决问题，在本技术方案中做出以下决策（可调整）：

| 编号 | 问题 | 决策 |
|---|---|---|
| Q-01 | 翻译引擎选型 | 抽象接口 + 多实现，默认 Mock，可切换 Google/DeepL |
| Q-02 | 支持语言列表 | zh/en/ja/ko/fr/de/es/ru，源语言支持 auto |
| Q-03 | PR 触发方式 | Webhook 接收事件，bot 账号发布评论（仅评论权限） |
| Q-04 | 内容大小上限 | 单任务源内容 ≤ 1MB，分段数 ≤ 500 |
| Q-05 | 术语匹配策略 | 单词边界安全 + 最长匹配，大小写保留原术语大小写 |
| Q-06 | 存储介质与周期 | SQLite(开发)/PostgreSQL(生产)，任务保留 30 天（可配置） |

---

*— 技术方案文档结束 —*
