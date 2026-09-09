"""查询工具：ILIKE 通配符转义。"""


def escape_like(q: str) -> str:
    """转义用户输入中的 ILIKE 通配符（% _ \\），防通配注入导致全表扫描/全量命中。"""
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
