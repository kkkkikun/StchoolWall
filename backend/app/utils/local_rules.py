"""本地敏感词规则：归一化子串匹配（零依赖）。

与微信层并联，verdict 语义同 utils/moderation.ModerationResult：
- hard 命中 → reject（硬违规直接拒绝）
- gray 命中 → review（灰度转人工）
- 其余 → pass

已知边界：不识别谐音/拆字变形（如"呆考"），此类靠灰词命中或微信层兜底。
"""
import unicodedata

from app.utils.moderation import ModerationResult

# 零宽字符（isspace 不覆盖，变体绕过常用）
_ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"}


def normalize_text(text: str) -> str:
    """归一化：NFKC（全角→半角）+ 小写 + 去所有空白与零宽字符。"""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text).lower()
    return "".join(c for c in normalized if not c.isspace() and c not in _ZERO_WIDTH)


def check_text_local(content: str, words: list[tuple[str, str]]) -> tuple[ModerationResult, list[str]]:
    """本地敏感词判定。words 为 (原始词, level)，词与内容都归一化后子串匹配。

    返回 (判定结果, 命中的归一化词表)；hard 优先于 gray。
    """
    if not words or not (content or "").strip():
        return ModerationResult("pass"), []

    normalized = normalize_text(content)
    matched_hard: list[str] = []
    matched_gray: list[str] = []
    for word, level in words:
        w = normalize_text(word)
        if not w or w not in normalized:
            continue
        (matched_hard if level == "hard" else matched_gray).append(w)

    if matched_hard:
        return (
            ModerationResult("reject", reason=f"命中敏感词：{'、'.join(matched_hard)}（硬违规）"),
            matched_hard,
        )
    if matched_gray:
        return (
            ModerationResult("review", reason=f"命中敏感词：{'、'.join(matched_gray)}（灰度）"),
            matched_gray,
        )
    return ModerationResult("pass"), []
