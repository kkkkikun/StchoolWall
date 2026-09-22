"""初始化敏感词库：幂等写入默认 hard/gray 词，供本地规则层兜底。

用法：
    cd backend
    python -m app.seed_sensitive_words
"""
import asyncio

from sqlalchemy import select

from app.database import async_session
from app.models.sensitive_word import SensitiveWord

# hard：命中直接拒绝；gray：命中转人工审核
DEFAULT_WORDS: list[tuple[str, str]] = [
    ("代考", "hard"),
    ("替考", "hard"),
    ("四六级答案", "hard"),
    ("考试答案", "hard"),
    ("代写论文", "hard"),
    ("代做毕设", "hard"),
    ("裸聊", "hard"),
    ("招嫖", "hard"),
    ("嫖娼", "hard"),
    ("赌博", "hard"),
    ("博彩", "hard"),
    ("下注", "hard"),
    ("毒品", "hard"),
    ("冰毒", "hard"),
    ("枪支", "hard"),
    ("办假证", "hard"),
    ("刷单", "gray"),
    ("贷款", "gray"),
    ("兼职", "gray"),
    ("低价", "gray"),
    ("交易", "gray"),
]


async def seed_default_words() -> int:
    """写入缺失的默认词，返回新增数量。已存在的词跳过。"""
    async with async_session() as db:
        existing = set((await db.execute(select(SensitiveWord.word))).scalars())
        added = 0
        for word, level in DEFAULT_WORDS:
            if word in existing:
                continue
            db.add(SensitiveWord(word=word, level=level))
            existing.add(word)
            added += 1
        await db.commit()
        return added


def main() -> None:
    added = asyncio.run(seed_default_words())
    print(f"[seed_sensitive_words] 新增 {added} 条，现有共 {len(DEFAULT_WORDS)} 条默认词。")


if __name__ == "__main__":
    main()
