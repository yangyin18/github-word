"""GitHub Webhook 路由：接收 PR/评论事件，触发翻译。"""
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app.services.github_app_auth import verify_signature
from app.services.pr_service import PRService

router = APIRouter(prefix="/api/webhook", tags=["webhook"])


@router.post("/github")
async def github_webhook(request: Request, db: Session = Depends(get_db)):
    body_bytes = await request.body()

    # 签名校验
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(body_bytes, signature, settings.github_webhook_secret):
        return {"error": "invalid_signature"}, 401

    event = request.headers.get("X-GitHub-Event", "")
    import json
    payload = json.loads(body_bytes)

    pr_service = PRService(db)
    installation_id = payload.get("installation", {}).get("id")

    if event == "pull_request":
        await pr_service.handle_pr_event(payload, installation_id)
    elif event == "issue_comment":
        await pr_service.handle_comment_event(payload, installation_id)

    return {"status": "accepted"}
