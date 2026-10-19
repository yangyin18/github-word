"""一键提 PR 路由：翻译仓库文档并以 PR 形式提交。"""
import uuid
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from app.routers.auth import get_token_from_session
from app.services.github_user_service import GitHubUserService, GitHubUserError

router = APIRouter(prefix="/api/pr", tags=["pr"])


class PRCreateRequest(BaseModel):
    repo: str  # owner/name
    path: str  # 文件路径，如 README.md
    content: str  # 翻译后的内容
    target_lang: str  # 目标语言代码，如 zh
    original_sha: str = ""  # 原文件 sha（更新文件时需要）


@router.post("/create")
async def create_translation_pr(request: Request, req: PRCreateRequest):
    """创建分支、写入译文、开 PR。"""
    token = get_token_from_session(request)
    gh = GitHubUserService(token)

    branch = f"translation-{req.target_lang}-{uuid.uuid4().hex[:8]}"
    # 译文文件名：README.md -> README.zh.md，docs/guide.md -> docs/guide.zh.md
    if "." in req.path.rsplit("/", 1)[-1]:
        parts = req.path.rsplit(".", 1)
        new_path = f"{parts[0]}.{req.target_lang}.{parts[1]}"
    else:
        new_path = f"{req.path}.{req.target_lang}"

    try:
        default_branch = await gh.get_default_branch(req.repo)
        await gh.create_branch(req.repo, branch, default_branch)
        await gh.create_or_update_file(
            repo=req.repo,
            path=new_path,
            content=req.content,
            branch=branch,
            message=f"docs: 翻译 {req.path} 为 {req.target_lang}",
        )
        pr = await gh.create_pull_request(
            repo=req.repo,
            title=f"翻译 {req.path} 为 {req.target_lang}",
            head=branch,
            base=default_branch,
            body=(
                f"由 GitHub 翻译工具自动生成。\n\n"
                f"- 源文件：`{req.path}`\n"
                f"- 目标语言：`{req.target_lang}`\n"
                f"- 译文文件：`{new_path}`\n\n"
                f"请审阅译文后合并。"
            ),
        )
    except GitHubUserError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=str(e))

    return {
        "pr_url": pr["html_url"],
        "pr_number": pr["number"],
        "branch": branch,
        "translated_path": new_path,
    }
