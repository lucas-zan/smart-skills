#!/usr/bin/env python3
import os
from pathlib import Path


SKILLS_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def load_skills_env() -> dict[str, str]:
    if not SKILLS_ENV_FILE.is_file():
        return {}

    values: dict[str, str] = {}
    for raw_line in SKILLS_ENV_FILE.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            values[key] = value
    return values


def get_env(name: str) -> str | None:
    fallback = load_skills_env().get(name)
    if fallback:
        return fallback

    value = os.getenv(name)
    if value:
        return value
    return None
