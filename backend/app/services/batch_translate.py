"""批量翻译调度：按批切分调用 LLM，逐批写缓存，失败回退逐条。

单批上限：最多 15 段或累计 4000 字符（取先到者），
避免长文档一次性发送超出模型上下文/输出限制。
"""
from typing import Callable

from app.services.translation_cache import TranslationCacheService
from app.services.translator.base import BaseTranslator

MAX_BATCH_SEGMENTS = 15
MAX_BATCH_CHARS = 4000


def chunk_texts(texts: list[str]) -> list[list[str]]:
    """按段数与累计字符数上限切分为多批。"""
    batches: list[list[str]] = []
    current: list[str] = []
    current_chars = 0
    for t in texts:
        t_len = len(t)
        if current and (len(current) >= MAX_BATCH_SEGMENTS or current_chars + t_len > MAX_BATCH_CHARS):
            batches.append(current)
            current = []
            current_chars = 0
        current.append(t)
        current_chars += t_len
    if current:
        batches.append(current)
    return batches


async def translate_missing(
    translator: BaseTranslator,
    cache_svc: TranslationCacheService,
    missing: list[str],
    source_lang: str,
    target_lang: str,
    glossary: dict[str, str] | None = None,
    on_progress: Callable[[int], None] | None = None,
) -> dict[str, str]:
    """批量翻译未命中缓存的文本，返回 {原文: 译文}。

    - 分批调用 translate_batch，每批完成后立即写入缓存（中途失败已完成的批次不丢）
    - 整批失败时回退逐条；逐条仍失败的文本不出现在返回结果中
    - on_progress(resolved) 在每批完成后回调，resolved 为累计成功条数
    """
    translation_map: dict[str, str] = {}
    resolved = 0
    for batch in chunk_texts(missing):
        try:
            results = await translator.translate_batch(batch, source_lang, target_lang, glossary)
        except Exception:
            results = None  # 整批失败：回退逐条
        if results is None:
            results = []
            for t in batch:
                try:
                    results.append(await translator.translate(t, source_lang, target_lang, glossary))
                except Exception:
                    results.append(None)

        batch_map = {t: r for t, r in zip(batch, results) if r is not None}
        if batch_map:
            cache_svc.put_many(
                batch_map, source_lang, target_lang,
                model=getattr(translator, "model", None), glossary=glossary,
            )
            translation_map.update(batch_map)
        resolved += sum(1 for r in results if r is not None)
        if on_progress:
            on_progress(resolved)
    return translation_map
