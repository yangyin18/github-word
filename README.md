# GitHub 翻译工具

基于 GitHub OAuth 的文档翻译工具：登录后选择仓库文档一键翻译，保留 Markdown 结构与代码块，译文一键提 PR，支持 PR 评论触发自动翻译。

## 功能特性

- **GitHub 登录**：OAuth 授权即可使用，无需安装 GitHub App
- **仓库文档翻译**：浏览自己的仓库与文件树，选择 Markdown 文件翻译
- **URL 手动翻译**：粘贴 Issue / Pull Request / README 链接直接翻译
- **结构保真**：自动还原标题层级（# 前缀），代码块与代码内注释不翻译，格式与占位符原样保留
- **一键提 PR**：自动创建分支，译文以新文件（如 `README.zh.md`）提交，不覆盖原文
- **PR 评论自动翻译**（可选）：在 PR 描述或评论中写翻译指令，机器人自动翻译并回评，需仓库安装 GitHub App
- **术语表**：注入提示词约束译名 + 译文后处理兜底替换，双重生效
- **翻译缓存**：相同原文（含语言对与术语表指纹）自动命中缓存，重复翻译零成本
- **批量翻译**：多段落合并为一次 LLM 调用（每批 ≤15 段或 4000 字符），长文档自动分批
- **分段修正**：对任意分段手动修正译文，支持失败分段一键重试
- **实时进度**：任务详情页显示真实翻译进度条，历史记录可随时回查

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI + SQLAlchemy，SQLite（可切换 PostgreSQL） |
| 前端 | Vue3 + Vite + TypeScript |
| 翻译引擎 | 可插拔接口：Mock / OpenRouter（兼容硅基流动等 OpenAI 兼容接口），预留 Google / DeepL |
| GitHub 集成 | GitHub App（OAuth 登录 + Webhook 事件） |

## 快速开始

### 1. 配置环境变量

```bash
cd backend
cp .env.example .env
```

编辑 `.env`，按需填写：

```ini
# 翻译引擎（mock / openrouter）
TRANSLATOR_PROVIDER=openrouter

# OpenRouter 或任意 OpenAI 兼容接口（如硅基流动 https://api.siliconflow.cn/v1）
OPENROUTER_API_KEY=sk-xxx
OPENROUTER_MODEL=Qwen/Qwen2.5-7B-Instruct
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# GitHub OAuth（在 GitHub App 设置页获取，用户登录必填）
GITHUB_CLIENT_ID=xxx
GITHUB_CLIENT_SECRET=xxx
GITHUB_OAUTH_CALLBACK_URL=http://localhost:8000/api/auth/callback

# Session 签名密钥，生产环境务必修改
SESSION_SECRET=change-me-in-production-please-use-random-string
```

### 2. 启动后端

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000
```

API 文档：http://127.0.0.1:8000/docs

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 ，点击「用 GitHub 登录」即可开始使用。

## GitHub App 配置（可选）

网页翻译与提 PR 只需 OAuth 授权，无需安装 App。仅「PR 评论自动翻译」需要以下配置：

| 配置项 | 说明 |
|---|---|
| 权限 | Pull requests: Write、Issues: Write |
| 事件订阅 | Pull request、Issue comment |
| OAuth | 勾选「Request user authorization (OAuth) during installation」，配置 Callback URL |
| Webhook URL | 本地开发用 smee.io / ngrok 等内网穿透地址 |
| Webhook Secret | 与 `.env` 中 `GITHUB_WEBHOOK_SECRET` 一致 |

配置后，在 PR 描述或评论中写「翻译为 zh」即可触发自动翻译，机器人会将译文回评到该 PR。

## 项目结构

```
backend/
  app/
    routers/        # API 路由层（tasks / translate / repos / pr / auth / webhook）
    services/       # 服务层（翻译引擎、批量调度、缓存、术语表、GitHub 集成）
    repositories/   # 数据访问层
    models/         # ORM 模型
frontend/
  src/
    views/          # 页面（仓库浏览 / 文件翻译 / 任务详情 / 翻译历史）
    api/            # 接口封装
    stores/         # 全局登录态
```
