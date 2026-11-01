"""Outil "sous-domaines" : les retrouver grâce aux certificats TLS.

Chaque fois qu'un site obtient un certificat HTTPS, celui-ci est publié dans
des journaux publics appelés "Certificate Transparency". Le site crt.sh
permet de les fouiller : on y retrouve des sous-domaines parfois oubliés
(dev., staging., vpn., admin....), une mine d'or en reconnaissance.

C'est une technique "passive" : on ne touche jamais aux serveurs de la cible.
"""

from typing import Any

import httpx

from .validation import normalize_domain

CRT_SH_URL = "https://crt.sh/"
MAX_RESULTS = 300


def extract_subdomains(entries: list[dict[str, Any]], domain: str) -> list[str]:
    """Extrait les sous-domaines uniques d'une réponse de crt.sh."""
    found: set[str] = set()
    for entry in entries:
        # Un certificat peut couvrir plusieurs noms, séparés par des retours à la ligne.
        for name in str(entry.get("name_value", "")).splitlines():
            name = name.strip().lower().removeprefix("*.")
            if name == domain or name.endswith("." + domain):
                found.add(name)
    return sorted(found)


async def subdomain_search(domain: str, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
    """Point d'entrée de l'outil : liste les sous-domaines connus d'un domaine."""
    domain = normalize_domain(domain)

    own_client = client is None
    if own_client:
        # crt.sh est souvent lent : on lui laisse du temps.
        client = httpx.AsyncClient(timeout=45.0, follow_redirects=True)
    try:
        response = await client.get(CRT_SH_URL, params={"q": f"%.{domain}", "output": "json"})
        response.raise_for_status()
        entries = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return {
            "domaine": domain,
            "erreur": f"crt.sh ne répond pas correctement ({type(exc).__name__}). "
            "Le service est souvent surchargé : réessaie dans quelques minutes.",
        }
    finally:
        if own_client:
            await client.aclose()

    subdomains = extract_subdomains(entries, domain)
    result: dict[str, Any] = {
        "domaine": domain,
        "nombre": len(subdomains),
        "sous_domaines": subdomains[:MAX_RESULTS],
        "source": "Certificate Transparency (crt.sh)",
    }
    if len(subdomains) > MAX_RESULTS:
        result["remarque"] = f"Liste tronquée aux {MAX_RESULTS} premiers résultats."
    return result
