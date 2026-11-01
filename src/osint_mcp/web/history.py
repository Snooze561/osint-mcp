"""Historique des recherches, stocké dans une petite base SQLite locale.

SQLite est une base de données contenue dans un seul fichier, intégrée à
Python (module sqlite3) : rien à installer. Le fichier est rangé dans le
dossier personnel (~/.osint-mcp/historique.db), jamais dans le dépôt Git,
car l'historique peut contenir des données personnelles.
"""

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def data_dir() -> Path:
    # La variable OSINT_MCP_DATA permet de choisir un autre dossier (utile pour les tests).
    return Path(os.environ.get("OSINT_MCP_DATA", Path.home() / ".osint-mcp"))


def _connect() -> sqlite3.Connection:
    folder = data_dir()
    folder.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(folder / "historique.db")
    conn.row_factory = sqlite3.Row  # pour lire les lignes comme des dictionnaires
    conn.execute(
        """CREATE TABLE IF NOT EXISTS recherches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            outil TEXT NOT NULL,
            valeur TEXT NOT NULL,
            resultat TEXT NOT NULL
        )"""
    )
    return conn


def add(outil: str, valeur: str, resultat: dict[str, Any]) -> int:
    """Enregistre une recherche et renvoie son numéro."""
    with _connect() as conn:
        cursor = conn.execute(
            # Les "?" évitent les injections SQL : sqlite3 insère les valeurs proprement.
            "INSERT INTO recherches (date, outil, valeur, resultat) VALUES (?, ?, ?, ?)",
            (
                datetime.now(UTC).isoformat(timespec="seconds"),
                outil,
                valeur,
                json.dumps(resultat, ensure_ascii=False),
            ),
        )
        return cursor.lastrowid


def latest(limit: int = 50) -> list[dict[str, Any]]:
    """Les dernières recherches, sans leur résultat (pour la liste)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, date, outil, valeur FROM recherches ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def get(search_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM recherches WHERE id = ?", (search_id,)).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["resultat"] = json.loads(item["resultat"])
    return item


def clear() -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM recherches")
