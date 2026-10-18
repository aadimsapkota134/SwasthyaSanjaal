"""Content-addressed upload storage with directory traversal protection."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from backend.config import settings

EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "application/pdf": ".pdf",
    "audio/webm": ".webm",
    "audio/wav": ".wav",
    "audio/mpeg": ".mp3",
}

_SAFE = re.compile(r"[^a-z0-9.]+")


def extension_for(mime_type: str, filename: str | None = None) -> str:
    known = EXTENSIONS.get(mime_type.split(";")[0].strip().lower())
    if known:
        return known
    if filename and "." in filename:
        candidate = "." + _SAFE.sub("", filename.rsplit(".", 1)[1].lower())
        if 1 < len(candidate) <= 6:
            return candidate
    return ".bin"


def save_upload(data: bytes, mime_type: str, filename: str | None = None) -> str:
    """Content-addressed upload storage. Returns path relative to uploads directory."""
    directory = Path(settings.upload_dir)
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(data).hexdigest()[:16]
    name = f"{digest}{extension_for(mime_type, filename)}"
    target = directory / name
    if not target.exists():
        target.write_bytes(data)
    return name


def resolve_upload(name: str) -> Path:
    """Safely resolve upload path preventing directory traversal."""
    if not name or name != Path(name).name or name in {os.curdir, os.pardir}:
        raise ValueError(f"not a stored upload name: {name!r}")
    directory = Path(settings.upload_dir).resolve()
    target = (directory / name).resolve()
    if target.parent != directory:
        raise ValueError(f"upload path escapes the upload directory: {name!r}")
    return target
