"""语言列表路由。"""
from fastapi import APIRouter
from app.config import SUPPORTED_LANGUAGES, SOURCE_LANGUAGES

router = APIRouter(prefix="/api/languages", tags=["languages"])


@router.get("")
def get_languages():
    return {
        "source_languages": SOURCE_LANGUAGES,
        "target_languages": SUPPORTED_LANGUAGES,
    }
