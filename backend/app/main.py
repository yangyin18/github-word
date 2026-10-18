"""FastAPI 应用入口。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.utils.errors import register_error_handlers
from app.routers import tasks, languages, webhook

app = FastAPI(title="GitHub 翻译工具 API", version="0.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 错误处理
register_error_handlers(app)

# 路由
app.include_router(tasks.router)
app.include_router(languages.router)
app.include_router(webhook.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}
