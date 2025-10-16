from pathlib import Path
from typing import Any

import requests

AI_SERVICE_URL = (
    "http://prj-flax:8000/v2/ai/infer"  # host name trong docker-compose
)


def run_ocr(file_path: str) -> Any:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError("File not found: %s", file_path)

    with path.open("rb") as f:
        resp = requests.post(AI_SERVICE_URL, files={"file": f}, timeout=30)
    resp.raise_for_status()
    return resp.json()
