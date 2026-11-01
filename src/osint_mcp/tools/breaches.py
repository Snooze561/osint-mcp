"""Outil "fuites de données" : l'adresse apparaît-elle dans des fuites connues ?

Have I Been Pwned (HIBP), créé par le chercheur Troy Hunt, recense des
centaines de fuites de données publiques (LinkedIn, Adobe, Canva...). Savoir
qu'une adresse est dans une fuite indique quels services la personne a
utilisés, à quelle époque, et quelles données ont fuité (mots de passe,
téléphones, adresses...).

L'API de recherche par e-mail demande une clé payante (HIBP_API_KEY).
Le meilleur premier test : ta propre adresse !
"""

from typing import Any

import httpx

from .. import config
from .validation import normalize_email

HIBP_URL = "https://haveibeenpwned.com/api/v3/breachedaccount/{}"


async def email_breaches(email: str, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
    """Point d'entrée de l'outil : liste les fuites contenant l'adresse."""
    email = normalize_email(email)
    key = config.get_key(config.HIBP)
    if not key:
        return {
            "email": email,
            "erreur": "Clé HIBP_API_KEY absente.",
            "comment_faire": (
                "Achète une clé sur https://haveibeenpwned.com/API/Key puis ajoute-la "
                "dans le fichier .env (voir .env.example). Sans clé, tu peux vérifier "
                "ta propre adresse gratuitement sur https://haveibeenpwned.com."
            ),
        }

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=15.0)
    try:
        response = await client.get(
            HIBP_URL.format(email),
            params={"truncateResponse": "false"},
            # HIBP exige un User-Agent qui identifie l'application.
            headers={"hibp-api-key": key, "user-agent": "osint-mcp"},
        )
    except httpx.HTTPError as exc:
        return {"email": email, "erreur": f"HIBP injoignable ({type(exc).__name__})"}
    finally:
        if own_client:
            await client.aclose()

    if response.status_code == 404:
        return {"email": email, "nombre_de_fuites": 0, "fuites": []}
    if response.status_code == 401:
        return {"email": email, "erreur": "Clé HIBP refusée : vérifie HIBP_API_KEY dans .env."}
    if response.status_code == 429:
        return {"email": email, "erreur": "Trop de requêtes : attends quelques secondes."}
    if response.status_code != 200:
        return {"email": email, "erreur": f"Réponse inattendue de HIBP (HTTP {response.status_code})"}

    breaches = [
        {
            "nom": b.get("Title") or b.get("Name"),
            "site": b.get("Domain"),
            "date": b.get("BreachDate"),
            "donnees_exposees": b.get("DataClasses", []),
            "verifiee": b.get("IsVerified"),
        }
        for b in response.json()
    ]
    breaches.sort(key=lambda b: b["date"] or "", reverse=True)
    return {"email": email, "nombre_de_fuites": len(breaches), "fuites": breaches}
