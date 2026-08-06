"""通用工具函数。"""


def trim_text(text: str, max_chars: int) -> str:
    """按句子边界截断文本（硬上限；优先在句末标点/换行处收尾，避免腰斩句子）。"""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    for marker in ("。", "！", "？", "\n", "！"):
        idx = cut.rfind(marker)
        if idx >= max_chars * 0.7:  # 边界太靠前则直接硬截，避免内容损失过多
            return cut[: idx + 1]
    return cut
