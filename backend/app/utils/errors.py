"""统一错误处理。"""
from fastapi import Request
from fastapi.responses import JSONResponse
from app.services.github_service import GitHubError


class AppError(Exception):
    def __init__(self, error: str, message: str, detail: str = None, status_code: int = 400, retry_after: int = None):
        self.error = error
        self.message = message
        self.detail = detail
        self.status_code = status_code
        self.retry_after = retry_after


def register_error_handlers(app):
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        body = {"error": exc.error, "message": exc.message}
        if exc.detail:
            body["detail"] = exc.detail
        if exc.retry_after:
            body["retry_after"] = exc.retry_after
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(GitHubError)
    async def github_error_handler(request: Request, exc: GitHubError):
        body = {"error": "github_error", "message": str(exc)}
        if exc.retry_after:
            body["retry_after"] = exc.retry_after
        status = exc.status_code or 502
        return JSONResponse(status_code=status, content=body)

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "服务器内部错误"},
        )
