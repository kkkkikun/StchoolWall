"""守卫 scripts/load/campus.js 的场景配比与请求路径。

配比与请求路径是容量报告（docs/production/capacity.md）的口径来源，
一旦被误改，G3 的证据就与文档不符，因此用静态解析锁住。
"""

import re
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "load/campus.js"

# 文档记录的配比：既有七项的权重保持不变，只新增推荐流。
EXPECTED_WEIGHTS = {
    "feed": 45,
    "post_detail": 25,
    "hot": 10,
    "search": 7,
    "like+unlike": 6,
    "comment": 4,
    "unread": 3,
    "recommend_feed": 10,
}


def load_script() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def constants(source: str) -> dict[str, int]:
    return {
        name: int(value)
        for name, value in re.findall(r"const (MIX_[A-Z_]+) = (\d+);", source)
    }


def branches(source: str) -> list[tuple[str | None, list[str], list[str]]]:
    """返回 (阈值常量名, 路径列表, 场景标签列表)；阈值为 None 表示最后的 else 分支。"""
    body = source.split("const kind = sequence % MIX_TOTAL;", 1)[1]
    body = body.split("sleep(", 1)[0]
    condition = re.compile(r"(?:else\s+)?if\(kind < (MIX_[A-Z_]+)\)")
    matches = list(condition.finditer(body))
    result = []
    else_content = ""
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        content = body[match.end():end]
        if index + 1 == len(matches):
            # 最后一个条件之后可能还有 else 分支（推荐流）。
            content, _, else_content = content.partition("\n  else ")
        result.append((match.group(1), *_describe(content)))
    if else_content:
        result.append((None, *_describe(else_content)))
    return result


def _describe(content: str) -> tuple[list[str], list[str]]:
    paths = re.findall(r"send\('(?:GET|POST|DELETE|PUT)',\s*'([^']*)'", content)
    tags = re.findall(r"send\([^;]*?'([a-z_]+)'\);", content, re.DOTALL)
    return paths, tags


def mix_of(source: str) -> dict[str, int]:
    """按分支统计权重：一个分支内的多个标签（如赞/取消）算同一份权重。"""
    values = constants(source)
    total = values["MIX_TOTAL"]
    counts: dict[str, int] = {}
    previous = 0
    for threshold, _paths, tags in branches(source):
        limit = total if threshold is None else values[threshold]
        bucket = limit - previous
        previous = limit
        group = tags[0] if len(tags) == 1 else "+".join(sorted(tags))
        counts[group] = counts.get(group, 0) + bucket
    return counts


class CampusMixTests(unittest.TestCase):
    def setUp(self):
        self.source = load_script()

    def test_documented_mix_is_preserved(self):
        counts = mix_of(self.source)
        self.assertEqual(counts, EXPECTED_WEIGHTS)

    def test_effective_share_of_each_scenario(self):
        counts = mix_of(self.source)
        total = constants(self.source)["MIX_TOTAL"]
        self.assertEqual(sum(counts.values()), total)
        shares = {tag: round(bucket / total * 100, 1) for tag, bucket in counts.items()}
        self.assertEqual(shares["recommend_feed"], 9.1)
        self.assertEqual(shares["feed"], 40.9)
        self.assertEqual(shares["unread"], 2.7)

    def test_existing_scenario_paths_are_unchanged(self):
        source = self.source
        self.assertIn("'/api/v1/posts?limit=20&order=time'", source)
        self.assertIn("'/api/v1/posts/hot'", source)
        self.assertIn("'/api/v1/posts/search?q=course'", source)
        self.assertIn("'/api/v1/notifications/unread-summary'", source)

    def test_recommend_feed_calls_posts_without_order(self):
        recommend = [
            (paths, tags)
            for _threshold, paths, tags in branches(self.source)
            if "recommend_feed" in tags
        ]
        self.assertEqual(len(recommend), 1, "推荐流场景应只出现一次")
        paths, tags = recommend[0]
        self.assertEqual(paths, ["/api/v1/posts?limit=20"])
        self.assertNotIn("order=", paths[0], "推荐流必须是不带 order 的默认排序")

    def test_every_scenario_tag_has_its_own_metrics(self):
        declared = set(
            re.findall(r"'(feed|post_detail|hot|search|like|unlike|comment|unread|recommend_feed)'", self.source)
        )
        used = set()
        for _threshold, _paths, tags in branches(self.source):
            used.update(tags)
        self.assertTrue(used.issubset(declared), f"缺少按场景统计的指标：{used - declared}")


if __name__ == "__main__":
    unittest.main()
