"""直接翻译接口：输入 Markdown 文本，返回译文（不创建任务，用于文件翻译预览）。

每次翻译都会把原文、译文、状态等写入 translation_records 表。
"""
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.services.parser_service import ParserService
from app.services.assembler_service import AssemblerService
from app.services.glossary_service import GlossaryService
from app.services.translation_cache import TranslationCacheService
from app.services.batch_translate import translate_missing
from app.services.translator import get_translator
from app.models.segment import Segment, SegmentType, SegmentStatus
from app.models.user import User
from app.models.translation_record import TranslationRecord, TranslationStatus
from app.database import get_db
from app.config import SUPPORTED_LANGUAGES

router = APIRouter(prefix="/api/translate", tags=["translate"])


class TranslateRequest(BaseModel):
    content: str
    target_lang: str
    source_lang: str = "auto"
    resource_url: str | None = None  # 翻译来源（文件/issue/PR 的 URL）


class TranslateResponse(BaseModel):
    translated: str
    record_id: str | None = None


def _get_db_user(request: Request, db: Session) -> User | None:
    """从 session 取 GitHub 登录名，查数据库用户（未登录返回 None）。"""
    user = request.session.get("user")
    if not user or not user.get("login"):
        return None
    return db.query(User).filter(User.github_login == user["login"]).first()


@router.post("", response_model=TranslateResponse)
async def translate_text(req: TranslateRequest, request: Request, db: Session = Depends(get_db)):
    """直接翻译 Markdown 文本并返回译文，同时保存翻译记录。"""
    if req.target_lang not in [l["code"] for l in SUPPORTED_LANGUAGES]:
        raise HTTPException(status_code=400, detail=f"不支持的目标语言: {req.target_lang}")
    if not req.content or not req.content.strip():
        return TranslateResponse(translated="")

    # 解析分段
    parser = ParserService()
    parsed = parser.parse(req.content)

    # 构建分段对象（可译分段稍后统一批量翻译）
    translator = get_translator()
    cache_svc = TranslationCacheService(db)
    glossary = GlossaryService(db)
    # 术语表：注入提示词约束译名，同时纳入缓存键（术语表变更后缓存自动失效）
    terms = glossary.get_terms_dict(req.source_lang, req.target_lang) if req.source_lang != "auto" else {}
    glossary_kw = terms or None
    segments = []
    for idx, ps in enumerate(parsed):
        seg = Segment(
            sequence=idx,
            segment_type=ps.segment_type,
            translatable=ps.translatable,
            source_text=ps.source_text,
            status=SegmentStatus.TRANSLATED if ps.translatable else SegmentStatus.PENDING,
        )
        segments.append(seg)

    translatable_positions = [i for i, ps in enumerate(parsed) if ps.translatable]
    texts = [parsed[i].source_text for i in translatable_positions]

    # 1) 缓存命中直接复用，未命中的分批调用 LLM（逐批写缓存）
    translation_map = cache_svc.get_many(texts, req.source_lang, req.target_lang, glossary_kw)
    unique_missing = list(dict.fromkeys(t for t in texts if t not in translation_map))

    if unique_missing:
        new_map = await translate_missing(
            translator, cache_svc, unique_missing,
            req.source_lang, req.target_lang, glossary_kw,
        )
        translation_map.update(new_map)

    # 2) 回填译文 + 术语后处理
    failed = 0
    t0 = time.time()
    for pos in translatable_positions:
        seg = segments[pos]
        translated = translation_map.get(parsed[pos].source_text)
        if translated is None:
            seg.status = SegmentStatus.FAILED
            seg.error_message = "翻译失败"
            failed += 1
            continue
        if req.source_lang != "auto":
            translated = glossary.apply(translated, req.source_lang, req.target_lang)
        seg.translated_text = translated
    elapsed_ms = int((time.time() - t0) * 1000)

    # 组装
    translated = AssemblerService.assemble(segments)

    # 翻译记录落库
    db_user = _get_db_user(request, db)
    record = TranslationRecord(
        user_id=db_user.id if db_user else None,
        resource_url=req.resource_url,
        source_type="file" if req.resource_url and "/blob/" in req.resource_url else "text",
        source_lang=req.source_lang,
        target_lang=req.target_lang,
        source_text=req.content,
        translated_text=translated,
        status=TranslationStatus.PARTIAL if failed else TranslationStatus.COMPLETED,
        error_message=f"{failed} 个分段翻译失败" if failed else None,
        segment_count=len(parsed),
        failed_count=failed,
        elapsed_ms=elapsed_ms,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return TranslateResponse(translated=translated, record_id=record.id)


@router.get("/history")
async def history(request: Request, limit: int = 50, db: Session = Depends(get_db)):
    """查询当前登录用户的翻译记录（最近 limit 条）。"""
    db_user = _get_db_user(request, db)
    if not db_user:
        raise HTTPException(status_code=401, detail="未登录")

    rows = (
        db.query(TranslationRecord)
        .filter(TranslationRecord.user_id == db_user.id)
        .order_by(TranslationRecord.created_at.desc())
        .limit(min(limit, 200))
        .all()
    )
    return {
        "user": {"login": db_user.github_login, "name": db_user.name},
        "total": len(rows),
        "records": [
            {
                "id": r.id,
                "resource_url": r.resource_url,
                "source_type": r.source_type,
                "target_lang": r.target_lang,
                "status": r.status,
                "segment_count": r.segment_count,
                "failed_count": r.failed_count,
                "elapsed_ms": r.elapsed_ms,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "source_preview": (r.source_text or "")[:120],
                "translated_preview": (r.translated_text or "")[:120],
            }
            for r in rows
        ],
    }
