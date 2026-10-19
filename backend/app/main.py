"""FastAPI 应用入口。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from app.database import init_db
from app.config import settings
from app.utils.errors import register_error_handlers
from app.routers import tasks, languages, webhook, auth, repos, pr as pr_router, translate

app = FastAPI(title="GitHub 翻译工具 API", version="0.1.0")

# Session（OAuth 登录态）
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 错误处理
register_error_handlers(app)

# 路由
app.include_router(tasks.router)
app.include_router(languages.router)
app.include_router(webhook.router)
app.include_router(auth.router)
app.include_router(repos.router)
app.include_router(pr_router.router)
app.include_router(translate.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}
