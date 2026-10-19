"""GitHub OAuth 路由：登录、回调、登出、获取当前用户。"""
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.services.oauth_service import OAuthService
from app.config import settings
from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/login")
async def login(request: Request):
    """重定向到 GitHub 授权页。"""
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state
    url = OAuthService.get_authorize_url(state)
    return RedirectResponse(url)


@router.get("/callback")
async def callback(request: Request, code: str = "", state: str = "", error: str = "", db: Session = Depends(get_db)):
    """GitHub 回调：校验 state、换 token、存 session、用户落库。"""
    if error:
        raise HTTPException(status_code=400, detail=f"授权失败: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="缺少 code 参数")

    # 校验 state 防 CSRF
    saved_state = request.session.get("oauth_state")
    if not saved_state or saved_state != state:
        raise HTTPException(status_code=400, detail="state 校验失败")
    request.session.pop("oauth_state", None)

    token = await OAuthService.exchange_code(code)
    user = await OAuthService.get_user_info(token)

    # 用户落库（已存在则更新登录时间和资料）
    db_user = db.query(User).filter(User.github_login == user["login"]).first()
    if db_user:
        db_user.name = user["name"]
        db_user.avatar_url = user["avatar_url"]
        db_user.html_url = user["html_url"]
        db_user.last_login_at = datetime.utcnow()
    else:
        db_user = User(
            github_login=user["login"],
            name=user["name"],
            avatar_url=user["avatar_url"],
            html_url=user["html_url"],
        )
        db.add(db_user)
    db.commit()

    # 把 token 和用户信息存 session
    request.session["access_token"] = token
    request.session["user"] = user

    # 跳回前端
    frontend_url = settings.github_oauth_callback_url.replace("/api/auth/callback", "").replace(":8000", ":5173")
    return RedirectResponse(url=frontend_url + "/")


@router.get("/me")
async def me(request: Request):
    """获取当前登录用户信息。"""
    user = request.session.get("user")
    if not user:
        return JSONResponse({"logged_in": False}, status_code=401)
    return {"logged_in": True, "user": user}


@router.post("/logout")
async def logout(request: Request):
    """登出：清空服务端 session，并显式删除会话 cookie（双保险）。"""
    request.session.clear()
    response = JSONResponse({"status": "logged_out"})
    # SessionMiddleware 检测到空 session 会删除 cookie，这里再显式删一次确保生效
    response.delete_cookie("session")
    return response


def get_token_from_session(request: Request) -> str:
    """从 session 取 user access token，未登录抛 401。"""
    token = request.session.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    return token
