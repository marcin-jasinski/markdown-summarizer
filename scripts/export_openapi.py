"""
Export the MindForge FastAPI OpenAPI schema to a static JSON file.

Usage:
    python scripts/export_openapi.py [output_path]

Default output: openapi.json (project root)

The exported file is used by `openapi-typescript` to generate / validate
`frontend/src/app/core/models/api.models.ts`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")

    # Import the factory WITHOUT triggering the lifespan (no DB/Redis needed).
    from mindforge.api.main import create_app

    app = create_app()
    schema = app.openapi()

    output_path.write_text(
        json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"OpenAPI schema exported to: {output_path} ({len(schema['paths'])} paths)")


if __name__ == "__main__":
    main()
