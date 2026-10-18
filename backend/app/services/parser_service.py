"""Markdown 解析与分段服务。"""
from markdown_it import MarkdownIt
from app.models.segment import SegmentType

# 各语言注释符号
COMMENT_PATTERNS = {
    "python": [r"^\s*#"],
    "py": [r"^\s*#"],
    "javascript": [r"^\s*//", r"^\s*/\*", r"^\s*\*"],
    "js": [r"^\s*//", r"^\s*/\*", r"^\s*\*"],
    "typescript": [r"^\s*//", r"^\s*/\*", r"^\s*\*"],
    "ts": [r"^\s*//", r"^\s*/\*", r"^\s*\*"],
    "html": [r"^\s*<!--"],
    "xml": [r"^\s*<!--"],
    "css": [r"^\s*/\*", r"^\s*\*"],
    "java": [r"^\s*//", r"^\s*/\*", r"^\s*\*"],
    "c": [r"^\s*//", r"^\s*/\*", r"^\s*\*"],
    "cpp": [r"^\s*//", r"^\s*/\*", r"^\s*\*"],
    "go": [r"^\s*//"],
    "rust": [r"^\s*//"],
    "sql": [r"^\s*--"],
}

import re


class ParsedSegment:
    def __init__(self, segment_type: str, source_text: str, translatable: bool):
        self.segment_type = segment_type
        self.source_text = source_text
        self.translatable = translatable


class ParserService:
    def __init__(self):
        self.md = MarkdownIt("commonmark")

    def parse(self, markdown_text: str) -> list[ParsedSegment]:
        """将 Markdown 解析为分段列表。"""
        if not markdown_text or not markdown_text.strip():
            return []

        tokens = self.md.parse(markdown_text)
        segments: list[ParsedSegment] = []
        i = 0
        n = len(tokens)

        while i < n:
            token = tokens[i]

            # 围栏代码块
            if token.type == "fence":
                lang = (token.info or "").strip().lower()
                segments.extend(self._parse_code_block(token.content, lang))
                i += 1
                continue

            # 代码块（缩进）
            if token.type == "code_block":
                segments.append(ParsedSegment(SegmentType.CODE_BLOCK, token.content, False))
                i += 1
                continue

            # 标题
            if token.type == "heading_open":
                inline = tokens[i + 1] if i + 1 < n else None
                text = inline.content if inline else ""
                segments.append(ParsedSegment(SegmentType.TEXT, text, True))
                i += 3  # open + inline + close
                continue

            # 段落
            if token.type == "paragraph_open":
                inline = tokens[i + 1] if i + 1 < n else None
                text = inline.content if inline else ""
                if text.strip():
                    segments.append(ParsedSegment(SegmentType.TEXT, text, True))
                i += 3
                continue

            # 列表项
            if token.type == "list_item_open":
                # 找到 list_item_close，提取内部 inline
                j = i + 1
                item_text = ""
                while j < n and tokens[j].type != "list_item_close":
                    if tokens[j].type == "inline":
                        item_text += tokens[j].content
                    j += 1
                if item_text.strip():
                    segments.append(ParsedSegment(SegmentType.TEXT, item_text, True))
                i = j + 1
                continue

            i += 1

        # 兜底：若未解析出任何分段，将全文作为文本
        if not segments and markdown_text.strip():
            segments.append(ParsedSegment(SegmentType.TEXT, markdown_text, True))

        return segments

    def _parse_code_block(self, code: str, lang: str) -> list[ParsedSegment]:
        """将代码块拆分为代码行(不可译)与注释行(可译)。"""
        segments = []
        patterns = COMMENT_PATTERNS.get(lang, [r"^\s*#", r"^\s*//"])

        for line in code.splitlines(keepends=True):
            is_comment = any(re.match(p, line) for p in patterns)
            if is_comment:
                segments.append(ParsedSegment(SegmentType.COMMENT, line, True))
            else:
                segments.append(ParsedSegment(SegmentType.CODE_BLOCK, line, False))

        # 若无注释模式匹配，整块作为不可译代码
        if not any(s.translatable for s in segments):
            return [ParsedSegment(SegmentType.CODE_BLOCK, code, False)]

        return segments
