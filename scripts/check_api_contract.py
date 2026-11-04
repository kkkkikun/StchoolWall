"""Export the deployed OpenAPI contract and check invariants without calling external APIs."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / 'backend'
# 入库的契约快照：接口面（路径与方法）以它为准，任何增删都必须先刷新它。
SNAPSHOT_PATH = ROOT / 'release/openapi.json'
HTTP_METHODS = frozenset({"get", "put", "post", "delete", "options", "head", "patch", "trace"})


def load_contract() -> dict:
    sys.path.insert(0, str(BACKEND_DIR))
    from app.main import app
    return app.openapi()


def check(contract: dict) -> None:
    paths = contract["paths"]
    for endpoint in ("/health/live", "/health/ready", "/api/v1/posts", "/api/v1/auth/web-login"):
        if endpoint not in paths:
            raise SystemExit(f"required contract endpoint missing: {endpoint}")
    for path in paths:
        if path.startswith("/api/") and not path.startswith("/api/v1/"):
            raise SystemExit(f"unversioned API: {path}")
    # Secrets must never become response fields; request-side passwords are legitimate.
    schemas = contract.get("components", {}).get("schemas", {})
    forbidden = {"password_hash", "web_password_hash", "session_key", "refresh_token_hash", "verification_fingerprint"}
    def inspect(value, visiting=frozenset()):
        if isinstance(value, dict):
            ref = value.get("$ref", "")
            if ref.startswith("#/components/schemas/") and ref not in visiting:
                inspect(schemas[ref.rsplit("/", 1)[-1]], visiting | {ref})
            if forbidden.intersection(value.get("properties", {})):
                raise SystemExit("secret field in response schema")
            for key, child in value.items():
                if key != "$ref":
                    inspect(child, visiting)
        elif isinstance(value, list):
            for item in value:
                inspect(item, visiting)
    for methods in paths.values():
        for operation in methods.values():
            if isinstance(operation, dict):
                inspect(operation.get("responses", {}))


def contract_surface(contract: dict) -> dict[str, frozenset[str]]:
    """接口面：路径 -> 该路径上的方法集合（路径项里其余键不是方法）。"""
    surface = {}
    for path, operations in contract["paths"].items():
        methods = {name.lower() for name in operations if name.lower() in HTTP_METHODS}
        surface[path] = frozenset(methods)
    return surface


def read_snapshot() -> dict:
    if not SNAPSHOT_PATH.exists():
        raise SystemExit(f"committed contract snapshot missing: {SNAPSHOT_PATH}")
    try:
        return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"committed contract snapshot is not valid JSON: {SNAPSHOT_PATH} ({error})")


def compare_with_snapshot(exported: dict, snapshot: dict) -> None:
    """导出的接口面必须与入库快照逐条一致：路径集合、每个路径的方法集合、路径数。"""
    exported_surface = contract_surface(exported)
    snapshot_surface = contract_surface(snapshot)
    added = sorted(set(exported_surface) - set(snapshot_surface))
    removed = sorted(set(snapshot_surface) - set(exported_surface))
    changed = sorted(
        path for path in set(exported_surface) & set(snapshot_surface)
        if exported_surface[path] != snapshot_surface[path]
    )
    if not added and not removed and not changed:
        return
    lines = [f"API contract drifted from the committed snapshot {SNAPSHOT_PATH.name}:"]
    if added:
        lines.append(f"  added paths: {', '.join(added)}")
    if removed:
        lines.append(f"  removed paths: {', '.join(removed)}")
    for path in changed:
        lines.append(
            f"  changed methods: {path} (snapshot: {', '.join(sorted(snapshot_surface[path])) or '-'}; "
            f"exported: {', '.join(sorted(exported_surface[path])) or '-'})"
        )
    lines.append(
        f"  path count: snapshot {len(snapshot_surface)}, exported {len(exported_surface)}"
    )
    lines.append(
        "  refresh the snapshot deliberately with: "
        "python scripts/check_api_contract.py --output release/openapi.json --update-snapshot"
    )
    raise SystemExit("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--update-snapshot",
        action="store_true",
        help="有意变更接口面时刷新入库快照（默认严格比对，任何增删都失败）",
    )
    args = parser.parse_args()
    contract = load_contract()
    check(contract)
    if args.update_snapshot:
        if args.output.resolve() != SNAPSHOT_PATH.resolve():
            raise SystemExit(
                f"--update-snapshot 要求 --output 指向入库快照 {SNAPSHOT_PATH}"
            )
    else:
        compare_with_snapshot(contract, read_snapshot())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"contract validated: {len(contract['paths'])} paths")


if __name__ == "__main__":
    main()
