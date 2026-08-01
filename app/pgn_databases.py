"""Beheer van geüploade PGN-databases voor historische robotzetten.

Bestanden staan in ``pgn/databases/``; actieve keuze en modus in
``pgn/databases_config.json``.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PGN_DIR = _PROJECT_ROOT / "pgn"
_DB_DIR = _PGN_DIR / "databases"
_CONFIG_PATH = _PGN_DIR / "databases_config.json"

# Ruimer dan naspelen (één partij): databases tot ~500 partijen.
MAX_DATABASE_CHARS = 2_000_000

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,120}\.pgn$", re.IGNORECASE)


def databases_dir() -> Path:
    """Geef de databases-map terug en maak die aan indien nodig."""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    return _DB_DIR


def _default_config() -> dict:
    return {"enabled": False, "active": None, "include_variations": False}


def load_config() -> dict:
    """Laad enabled/active/include_variations uit JSON; ontbrekende config → defaults."""
    config = _default_config()
    try:
        raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return config
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("databases_config.json onleesbaar: %s", exc)
        return config

    if not isinstance(raw, dict):
        return config

    config["enabled"] = bool(raw.get("enabled", False))
    config["include_variations"] = bool(raw.get("include_variations", False))
    active = raw.get("active")
    if active is None or active == "":
        config["active"] = None
    else:
        try:
            config["active"] = sanitize_name(str(active))
        except ValueError:
            config["active"] = None
    return config


def save_config(config: dict) -> None:
    """Schrijf enabled/active/include_variations naar JSON."""
    _PGN_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "enabled": bool(config.get("enabled", False)),
        "active": config.get("active"),
        "include_variations": bool(config.get("include_variations", False)),
    }
    try:
        _CONFIG_PATH.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("databases_config.json schrijven mislukt: %s", exc)


def sanitize_name(name: str) -> str:
    """Normaliseer en valideer een databasebestandsnaam."""
    base = Path(str(name).strip()).name
    if not base.lower().endswith(".pgn"):
        base = f"{base}.pgn"
    if not _SAFE_NAME.match(base):
        raise ValueError("Ongeldige databasennaam")
    return base


def list_databases() -> list[str]:
    """Gesorteerde lijst van ``*.pgn`` in de databases-map."""
    directory = databases_dir()
    names = sorted(p.name for p in directory.glob("*.pgn") if p.is_file())
    return names


def get_active_path(config: dict | None = None) -> Path | None:
    """Pad naar de actieve database, of None als die niet bestaat."""
    cfg = config if config is not None else load_config()
    active = cfg.get("active")
    if not active:
        return None
    try:
        name = sanitize_name(str(active))
    except ValueError:
        return None
    path = databases_dir() / name
    if not path.is_file():
        return None
    return path


def set_enabled(enabled: bool, config: dict | None = None) -> dict:
    """Zet PGN-modus aan/uit en persist."""
    cfg = config if config is not None else load_config()
    cfg["enabled"] = bool(enabled)
    save_config(cfg)
    return cfg


def set_include_variations(include: bool, config: dict | None = None) -> dict:
    """Zet meenemen van PGN-varianten aan/uit en persist."""
    cfg = config if config is not None else load_config()
    cfg["include_variations"] = bool(include)
    save_config(cfg)
    return cfg


def set_active(name: str | None, config: dict | None = None) -> dict:
    """Kies actieve database (None = geen) en persist."""
    cfg = config if config is not None else load_config()
    if name is None or name == "":
        cfg["active"] = None
    else:
        safe = sanitize_name(name)
        if safe not in list_databases():
            raise FileNotFoundError(safe)
        cfg["active"] = safe
    save_config(cfg)
    return cfg


def save_database(name: str, content: str) -> Path:
    """Schrijf/upload een PGN-database. Overschrijft bij dezelfde naam."""
    if len(content) > MAX_DATABASE_CHARS:
        raise ValueError(f"PGN te groot (max {MAX_DATABASE_CHARS} tekens)")
    safe = sanitize_name(name)
    path = databases_dir() / safe
    path.write_text(content, encoding="utf-8")
    return path


def delete_database(name: str, config: dict | None = None) -> dict:
    """Verwijder een database; wis active als die hetzelfde was."""
    cfg = config if config is not None else load_config()
    safe = sanitize_name(name)
    path = databases_dir() / safe
    if not path.is_file():
        raise FileNotFoundError(safe)
    path.unlink()
    if cfg.get("active") == safe:
        cfg["active"] = None
        save_config(cfg)
    return cfg


def state_payload(config: dict | None = None) -> dict:
    """Payload voor WebSocket ``pgn_databases``."""
    cfg = config if config is not None else load_config()
    databases = list_databases()
    active = cfg.get("active")
    if active and active not in databases:
        active = None
        cfg["active"] = None
        save_config(cfg)
    return {
        "type": "pgn_databases",
        "enabled": bool(cfg.get("enabled", False)),
        "include_variations": bool(cfg.get("include_variations", False)),
        "active": active,
        "databases": databases,
    }
