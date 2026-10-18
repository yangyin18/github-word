"""译文组装服务。"""
from app.models.segment import Segment, SegmentStatus


class AssemblerService:
    @staticmethod
    def assemble(segments: list[Segment]) -> str:
        """按序号顺序组装译文，不可译分段原样保留。"""
        parts = []
        for seg in segments:
            if not seg.translatable:
                parts.append(seg.source_text)
            else:
                if seg.status == SegmentStatus.TRANSLATED and seg.translated_text:
                    parts.append(seg.translated_text)
                elif seg.status == SegmentStatus.MANUALLY_EDITED and seg.translated_text:
                    parts.append(seg.translated_text)
                else:
                    # 失败或未翻译：保留原文并标注
                    parts.append(seg.source_text)
                    if seg.status == SegmentStatus.FAILED:
                        parts.append("\n<!-- 翻译失败 -->\n")

            # 分段间加换行（代码块前后保留原换行）
            if not seg.source_text.endswith("\n"):
                parts.append("\n")

        return "".join(parts).rstrip() + "\n"
