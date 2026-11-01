"""Outil "comptes liés à un e-mail" : sur quels sites cette adresse est-elle inscrite ?

On s'appuie sur holehe (https://github.com/megadose/holehe), un outil OSINT
très connu. Son astuce : les formulaires d'inscription ou de connexion de
nombreux sites répondent différemment selon que l'adresse est déjà utilisée
(« cette adresse est déjà associée à un compte ») ou non. holehe interroge
ces formulaires pour plus de 120 sites, sans prévenir la personne.

Par discrétion, on désactive les modules qui passent par la récupération de
mot de passe : ils pourraient déclencher un e-mail chez la personne ciblée.
"""

import asyncio
from collections.abc import Awaitable, Callable
from functools import cache
from typing import Any

import httpx

from .validation import normalize_email

# Modules holehe qui utilisent la récupération de mot de passe (option -NP de holehe).
PASSWORD_RECOVERY_MODULES = {"adobe", "mail_ru", "odnoklassniki", "samsung"}

HoleheModule = Callable[[str, httpx.AsyncClient, list], Awaitable[None]]


@cache
def load_modules() -> tuple[HoleheModule, ...]:
    """Charge les modules de holehe une seule fois (c'est un peu long)."""
    from holehe.core import get_functions, import_submodules

    modules = get_functions(import_submodules("holehe.modules"))
    return tuple(m for m in modules if m.__name__ not in PASSWORD_RECOVERY_MODULES)


async def run_module(module: HoleheModule, email: str, client: httpx.AsyncClient) -> dict[str, Any]:
    """Lance un module holehe et renvoie son résultat, même en cas d'erreur."""
    out: list[dict[str, Any]] = []
    try:
        await asyncio.wait_for(module(email, client, out), timeout=20)
    except Exception:  # noqa: BLE001 - un site cassé ne doit pas tout faire échouer
        return {"name": module.__name__, "exists": None, "rateLimit": True}
    return out[0] if out else {"name": module.__name__, "exists": None, "rateLimit": True}


async def email_accounts(
    email: str,
    modules: tuple[HoleheModule, ...] | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Point d'entrée de l'outil : cherche les sites où l'adresse a un compte."""
    email = normalize_email(email)
    modules = load_modules() if modules is None else modules

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=10.0)
    try:
        results = await asyncio.gather(*(run_module(m, email, client) for m in modules))
    finally:
        if own_client:
            await client.aclose()

    found = []
    for r in sorted(results, key=lambda r: r.get("name", "")):
        if r.get("exists") is True:
            item = {"site": r.get("domain") or r.get("name")}
            # Certains sites révèlent un indice : e-mail de secours ou téléphone masqués.
            if r.get("emailrecovery"):
                item["email_de_secours_masque"] = r["emailrecovery"]
            if r.get("phoneNumber"):
                item["telephone_masque"] = r["phoneNumber"]
            found.append(item)

    return {
        "email": email,
        "sites_verifies": len(results),
        "comptes_trouves": found,
        "non_verifiables": sorted(
            r.get("domain") or r.get("name", "?")
            for r in results
            if r.get("exists") is None or r.get("rateLimit")
        ),
        "source": "holehe",
        "avertissement": (
            "Les sites changent souvent leurs formulaires : un résultat peut être "
            "faux. Les sites « non vérifiables » ont bloqué la requête ou ont changé."
        ),
    }
