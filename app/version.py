"""Applicatieversie – bron is het VERSION-bestand in de projectroot."""

from pathlib import Path

_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


def get_version() -> str:
    try:
        text = _VERSION_FILE.read_text(encoding="utf-8").strip()
        return text.splitlines()[0].strip() if text else "0.0.0"
    except OSError:
        return "0.0.0"


__version__ = get_version()
