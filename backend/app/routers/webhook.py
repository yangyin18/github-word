"""GitHub Webhook 路由：接收 PR/评论事件，后台触发翻译。"""
import json

from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import SessionLocal
from app.services.github_app_auth import verify_signature
from app.services.pr_service import PRService, run_translation_job

router = APIRouter(prefix="/api/webhook", tags=["webhook"])


def _extract_translate_request(event: str, payload: dict) -> tuple[str, str, int] | None:
    """轻量判断该事件是否为翻译请求，返回 (repo, pr_number, target_lang) 或 None。"""
    action = payload.get("action")
    if event == "pull_request" and action in ("opened", "synchronize"):
        pr = payload.get("pull_request", {})
        target_lang = PRService.parse_translate_request(pr.get("body") or "")
        if target_lang:
            return payload["repository"]["full_name"], pr["number"], target_lang
    elif event == "issue_comment" and action == "created":
        issue = payload.get("issue", {})
        if issue.get("pull_request"):  # 仅 PR 评论
            target_lang = PRService.parse_translate_request(payload.get("comment", {}).get("body") or "")
            if target_lang:
                return payload["repository"]["full_name"], issue["number"], target_lang
    return None


@router.post("/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    body_bytes = await request.body()

    # 签名校验
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(body_bytes, signature, settings.github_webhook_secret):
        return JSONResponse(status_code=401, content={"error": "invalid_signature"})

    event = request.headers.get("X-GitHub-Event", "")
    try:
        payload = json.loads(body_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JSONResponse(status_code=400, content={"error": "invalid_payload"})

    # 请求内只做轻量判断，重活（抓取/翻译/发评论）全部放后台
    req = _extract_translate_request(event, payload)
    if not req:
        return {"status": "ignored"}

    repo, pr_number, target_lang = req
    installation_id = payload.get("installation", {}).get("id")
    background_tasks.add_task(run_translation_job, repo, pr_number, target_lang, installation_id)
    return {"status": "accepted"}
