"""Export the deployed OpenAPI contract and check invariants without calling external APIs."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.main import app


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    contract = app.openapi()
    check(contract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"contract validated: {len(contract['paths'])} paths")
