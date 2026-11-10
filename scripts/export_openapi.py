"""Writes the backend's OpenAPI schema to docs/api/openapi.json, keylessly and in-process.

    uv run python scripts/export_openapi.py            # write docs/api/openapi.json
    uv run python scripts/export_openapi.py --check    # exit 1 if the committed file is stale (for CI or a pre-commit)

The app is built in fake mode (PUKAAR_FAKE=1) with an empty Settings and a throwaway cache folder, and only
`app.openapi()` is called: no server starts, the lifespan never runs, and nothing reaches Gnani or Groq.
WebSocket routes (/ws/call, /ws/control) are not part of OpenAPI; docs/API.md documents them.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "api" / "openapi.json"


def build_schema() -> dict:
    os.environ["PUKAAR_FAKE"] = "1"
    from voice_core.config import Settings

    from pukaar.app import create_app

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        app = create_app(Settings(cache_dir=Path(tmp) / "cache"))
        try:
            return app.openapi()
        finally:
            app.state.store.db.close()  # Windows cannot delete an open SQLite file


def main(argv: list[str]) -> int:
    text = json.dumps(build_schema(), indent=2, ensure_ascii=False) + "\n"
    if "--check" in argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print(f"{OUT.relative_to(ROOT)} is stale: run `uv run python scripts/export_openapi.py`", file=sys.stderr)
            return 1
        print(f"{OUT.relative_to(ROOT)} is up to date")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    paths = json.loads(text)["paths"]
    print(f"wrote {OUT.relative_to(ROOT)}: {len(paths)} paths, {sum(len(v) for v in paths.values())} operations")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
