import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json_log(
    filename: str,
    payload: Dict[str, Any],
) -> None:
    evidence_dir = Path("evidence")
    evidence_dir.mkdir(exist_ok=True)

    path = evidence_dir / filename

    with open(path, "w", encoding="utf-8") as file:
        json.dump(
            payload,
            file,
            indent=2,
            ensure_ascii=False,
        )