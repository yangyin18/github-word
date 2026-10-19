"""仓库相关路由：列仓库、列目录、读文件。"""
from fastapi import APIRouter, Request, HTTPException, Query
from app.routers.auth import get_token_from_session
from app.services.github_user_service import GitHubUserService, GitHubUserError

router = APIRouter(prefix="/api/repos", tags=["repos"])


@router.get("")
async def list_repos(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    """列出当前用户的仓库。"""
    token = get_token_from_session(request)
    gh = GitHubUserService(token)
    try:
        repos = await gh.list_repos(page, per_page)
    except GitHubUserError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=str(e))
    return {
        "repos": [
            {
                "id": r["id"],
                "name": r["name"],
                "full_name": r["full_name"],
                "private": r["private"],
                "default_branch": r["default_branch"],
                "description": r.get("description"),
                "html_url": r["html_url"],
                "updated_at": r["updated_at"],
                "language": r.get("language"),
            }
            for r in repos
        ]
    }


@router.get("/{owner}/{repo}/contents/{path:path}")
@router.get("/{owner}/{repo}/contents")
async def get_contents(
    request: Request,
    owner: str,
    repo: str,
    path: str = "",
    ref: str = None,
):
    """列出目录或读取文件内容。"""
    token = get_token_from_session(request)
    gh = GitHubUserService(token)
    full_name = f"{owner}/{repo}"
    try:
        data = await gh.list_contents(full_name, path, ref)
    except GitHubUserError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=str(e))

    # 目录返回列表，文件返回对象
    if isinstance(data, list):
        return {
            "type": "dir",
            "items": [
                {
                    "name": item["name"],
                    "path": item["path"],
                    "type": item["type"],  # file / dir
                    "size": item.get("size", 0),
                }
                for item in data
            ],
        }
    else:
        # 单个文件，解码内容
        import base64
        content_b64 = data.get("content", "")
        content = base64.b64decode(content_b64).decode("utf-8") if content_b64 else ""
        return {
            "type": "file",
            "name": data["name"],
            "path": data["path"],
            "size": data["size"],
            "sha": data["sha"],
            "content": content,
        }
