"""Configuration : les clés API optionnelles.

Les clés sont lues dans les variables d'environnement, ou dans un fichier
`.env` à la racine du projet (copie `.env.example` en `.env` pour commencer).
Le fichier `.env` est listé dans `.gitignore` : il ne sera jamais publié sur
GitHub, ce qui est essentiel car une clé API est un secret.
"""

import os

from dotenv import find_dotenv, load_dotenv

# find_dotenv cherche un fichier .env en remontant depuis ce fichier source.
load_dotenv(find_dotenv(usecwd=False))


def get_key(name: str) -> str | None:
    """Renvoie la clé API demandée, ou None si elle n'est pas configurée."""
    value = os.environ.get(name, "").strip()
    return value or None


SHODAN = "SHODAN_API_KEY"
HIBP = "HIBP_API_KEY"
