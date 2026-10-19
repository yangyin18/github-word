"""译文组装服务。"""
from app.models.segment import Segment, SegmentStatus


class AssemblerService:
    @staticmethod
    def _heading_prefix(segment_type: str) -> str:
        """根据分段类型还原 Markdown 标题前缀（heading_3 -> "### "）。"""
        if segment_type and segment_type.startswith("heading_"):
            suffix = segment_type.split("_", 1)[1]
            if suffix.isdigit() and 1 <= int(suffix) <= 6:
                return "#" * int(suffix) + " "
        return ""

    @staticmethod
    def assemble(segments: list[Segment]) -> str:
        """按序号顺序组装译文，不可译分段原样保留。"""
        parts = []
        for seg in segments:
            if not seg.translatable:
                parts.append(seg.source_text)
            else:
                prefix = AssemblerService._heading_prefix(seg.segment_type)
                if seg.status == SegmentStatus.TRANSLATED and seg.translated_text:
                    parts.append(prefix + seg.translated_text)
                elif seg.status == SegmentStatus.MANUALLY_EDITED and seg.translated_text:
                    parts.append(prefix + seg.translated_text)
                else:
                    # 失败或未翻译：保留原文并标注
                    parts.append(prefix + seg.source_text)
                    if seg.status == SegmentStatus.FAILED:
                        parts.append("\n<!-- 翻译失败 -->\n")

            # 分段间加换行（代码块前后保留原换行）；
            # 特殊情况：源文本以换行结尾（代码块内逐行分段），但 LLM 返回的译文被 strip 掉行尾换行，需补回
            if seg.translatable and seg.source_text.endswith("\n") and seg.translated_text \
                    and not seg.translated_text.endswith("\n"):
                parts.append("\n")
            elif not seg.source_text.endswith("\n"):
                parts.append("\n")

        return "".join(parts).rstrip() + "\n"
