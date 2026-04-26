"""Load system prompts from YAML files, cached in-process."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    """Load ``prompts/<name>.yaml`` and return the ``system`` field."""
    path = PROMPTS_DIR / name if name.endswith(".yaml") else PROMPTS_DIR / f"{name}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "system" not in data:
        raise ValueError(f"Prompt file '{path}' must have a 'system' field.")
    return str(data["system"]).strip()
