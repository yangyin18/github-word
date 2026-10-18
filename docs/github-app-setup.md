# GitHub App 接入指南

> 本文档说明：何时需要 GitHub App、如何创建、如何与本系统对接，以及与 PAT 方案的对比。

## 1. 什么时候需要 GitHub App

本系统有两个 GitHub 交互场景：

| 场景 | 读/写 | 是否需要鉴权 | 推荐方式 |
|---|---|---|---|
| 手动提交 URL，抓取公开 Issue/PR/README 内容 | 只读公开数据 | 否（无 Token 也能读，60次/小时） | 无需 App；可选 Token 提速 |
| PR 事件触发翻译，并把译文作为评论回写到 PR | 写入评论 | 是 | **GitHub App**（推荐）或 PAT |

**结论**：仅做 P0 手动翻译公开内容 → 不需要 GitHub App。要做 P1「PR 触发 + 回写评论」→ 建议创建 GitHub App。

---

## 2. 鉴权方案对比

| 维度 | GitHub App | Personal Access Token (PAT) |
|---|---|---|
| 身份 | Bot 身份，评论显示为 App 名称 | 你的个人账号 |
| 权限范围 | 仅授予所需权限（如 Issues: Write），可按仓库安装 | 账号级权限，粒度粗 |
| 安全 | 使用短期 Installation Token，私钥本地保管 | 长期 Token，泄露风险高 |
| 速率限制 | 按安装计，5000次/小时/安装 | 按用户计，5000次/小时 |
| 适用场景 | 生产、多仓库、团队 | 个人测试、快速验证 |

> **推荐生产环境使用 GitHub App**。PAT 仅用于本地开发验证。

---

## 3. 创建 GitHub App 步骤

### 3.1 注册 App

1. 登录 GitHub，进入 **Settings → Developer settings → GitHub Apps → New GitHub App**
   （直达：https://github.com/settings/apps/new）

2. 填写基础信息：

| 字段 | 填写内容 |
|---|---|
| GitHub App name | 例如 `github-translation-bot`（全局唯一） |
| Homepage URL | 你的项目地址或任意公开 URL |
| Webhook URL | `https://你的域名/api/webhook/github`（本地开发可用 smee.io 代理） |
| Webhook secret | 自定义一串随机字符串，记下来（用于签名校验） |

3. **Permissions**（仅授予最小权限）：

| 权限类别 | 权限 | 说明 |
|---|---|---|
| Issues | Read & write | 读取 PR/Issue 内容、发布评论 |
| Pull requests | Read & write | 读取 PR 信息（PR 本质是 Issue） |
| Metadata | Read-only | 必填 |

4. **Subscribe to events**，勾选：
   - `Pull request`
   - `Issue comment`

5. 点击 **Create GitHub App**。

### 3.2 生成密钥

创建后进入 App 详情页：

1. **App ID**：记录下来（如 `123456`）。
2. **Private keys** → **Generate a private key**，下载 `.pem` 文件，妥善保管（**不要提交到 Git**）。
3. **Install App** → 在目标仓库上安装该 App。

---

## 4. 系统对接方式

### 4.1 环境变量

在 `backend/.env` 中配置：

```env
# GitHub App 配置
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY_PATH=./github-app.pem
GITHUB_WEBHOOK_SECRET=你设置的secret

# 翻译引擎
TRANSLATOR_PROVIDER=mock
```

> 将下载的 `.pem` 文件放到 `backend/` 目录下（并加入 `.gitignore`）。

### 4.2 Installation Token 获取流程

GitHub App 不能直接用私钥调 API，需先换取短期 Installation Token（有效期 1 小时）：

```
私钥 (.pem) ──JWT签名──► 换取 Installation Token ──► 调用 GitHub API
```

核心代码（`backend/app/services/github_app_auth.py`）：

```python
import time
import jwt
import httpx
from cryptography.hazmat.primitives import serialization

class GitHubAppAuth:
    def __init__(self, app_id: int, private_key_path: str):
        self.app_id = app_id
        with open(private_key_path, "rb") as f:
            self.private_key = serialization.load_pem_private_key(f.read(), password=None)

    def _make_jwt(self) -> str:
        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 600, "iss": str(self.app_id)}
        return jwt.encode(payload, self.private_key, algorithm="RS256")

    async def get_installation_token(self, installation_id: int) -> str:
        jwt_token = self._make_jwt()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            resp.raise_for_status()
            return resp.json()["token"]
```

### 4.3 Webhook 签名校验

```python
import hmac
import hashlib

def verify_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(), payload_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)
```

### 4.4 用 Installation Token 调用 API

```python
# 发布 PR 评论
token = await auth.get_installation_token(installation_id)
resp = await httpx.AsyncClient().post(
    f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments",
    headers={"Authorization": f"Bearer {token}"},
    json={"body": translated_comment},
)
```

---

## 5. 本地开发无公网域名怎么办

GitHub Webhook 需要公网可访问的 URL。本地开发有两种方案：

| 方案 | 说明 |
|---|---|
| **smee.io** | 免费 Webhook 代理。在 https://smee.io 新建通道，把 URL 填到 App 的 Webhook URL，本地用 `smee-client` 转发到 `127.0.0.1:8000/api/webhook/github` |
| **ngrok** | `ngrok http 8000`，把生成的公网 URL 填到 App 配置 |

---

## 6. PAT 简化方案（仅开发/测试）

如果暂时不想建 GitHub App，可用 PAT 快速验证 P1：

1. GitHub → Settings → Developer settings → Personal access tokens → Generate new token (classic)
2. 勾选 `repo` 权限（读写仓库）
3. 复制 Token，配置环境变量：

```env
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxx
```

当前 `github_service.py` 已支持读取 `GITHUB_TOKEN` 并附加到请求头，无需改代码即可验证抓取与评论发布。

> ⚠️ PAT 绑定个人账号，Token 泄露即账号泄露，**生产环境务必改用 GitHub App**。

---

## 7. 安全清单

- [ ] 私钥 `.pem` 文件加入 `.gitignore`，不提交到仓库
- [ ] Webhook secret 通过环境变量注入，不硬编码
- [ ] 所有 Webhook 请求校验 `X-Hub-Signature-256` 签名
- [ ] App 权限最小化（仅 Issues: Read & write）
- [ ] Installation Token 内存缓存，过期自动刷新，不持久化
- [ ] 日志中不打印 Token、私钥、签名

---

## 8. 与现有系统的集成点

| 模块 | 现状 | 需补充 |
|---|---|---|
| `github_service.py` | 支持 `GITHUB_TOKEN` 抓取公开内容 | 增加 GitHub App Installation Token 鉴权分支 |
| `routers/webhook.py` | 未创建 | 新增 Webhook 路由：签名校验、事件分发、触发翻译 |
| `services/pr_service.py` | 未创建 | 新增：识别 `/translate` 评论、发布译文评论、更新已有评论 |
| `.env.example` | 有 `GITHUB_TOKEN` | 增加 `GITHUB_APP_ID` / `GITHUB_APP_PRIVATE_KEY_PATH` |

> 当前 P0（手动 URL 翻译）已可运行，无需 GitHub App。P1（PR 触发）需要按本文档接入。

---

*— 文档结束 —*
