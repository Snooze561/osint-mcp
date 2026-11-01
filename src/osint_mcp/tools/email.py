"""Outil "e-mail" : que peut-on apprendre d'une adresse e-mail sans clé API ?

- Le domaine accepte-t-il des e-mails ? (enregistrements MX)
- Qui héberge la messagerie ? (Google, Microsoft, OVH, Proton... d'après les MX)
- Est-ce une adresse jetable ? (liste de domaines connus)
- A-t-elle un profil Gravatar ? (photo, nom, liens vers d'autres comptes)

Gravatar est un service qui associe une photo à une adresse e-mail. Il est
utilisé par WordPress, GitHub, Stack Overflow... Le profil est retrouvé grâce
à une empreinte (hash SHA-256) de l'adresse : c'est une technique OSINT
classique.
"""

import asyncio
import hashlib
from typing import Any

import dns.asyncresolver
import dns.exception
import dns.resolver
import httpx

from .validation import normalize_email

# Quelques domaines d'adresses jetables très répandus (liste non exhaustive).
DISPOSABLE_DOMAINS = {
    "yopmail.com", "yopmail.fr", "mailinator.com", "guerrillamail.com",
    "10minutemail.com", "temp-mail.org", "tempmail.com", "trashmail.com",
    "getnada.com", "sharklasers.com", "maildrop.cc", "dispostable.com",
    "throwawaymail.com", "jetable.org", "mohmal.com", "emailondeck.com",
}

# Morceau du serveur MX -> fournisseur de messagerie.
MX_PROVIDERS = {
    "google.com": "Google (Gmail / Google Workspace)",
    "googlemail.com": "Google (Gmail / Google Workspace)",
    "outlook.com": "Microsoft (Outlook / Microsoft 365)",
    "hotmail.com": "Microsoft (Outlook / Microsoft 365)",
    "yahoodns.net": "Yahoo",
    "ovh.net": "OVHcloud",
    "protonmail.ch": "Proton Mail",
    "icloud.com": "Apple iCloud",
    "orange.fr": "Orange",
    "free.fr": "Free",
    "sfr.fr": "SFR",
    "laposte.net": "La Poste",
    "gandi.net": "Gandi",
    "zoho.com": "Zoho",
    "mimecast.com": "Mimecast (filtrage)",
    "pphosted.com": "Proofpoint (filtrage)",
}


async def mx_records(domain: str) -> list[str]:
    """Renvoie les serveurs de messagerie (MX) du domaine, par priorité."""
    resolver = dns.asyncresolver.Resolver()
    resolver.lifetime = 5.0
    try:
        answer = await resolver.resolve(domain, "MX")
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN,
            dns.resolver.NoNameservers, dns.exception.Timeout):
        return []
    records = sorted(answer, key=lambda r: r.preference)
    return [r.exchange.to_text().rstrip(".") for r in records]


def guess_provider(mx_hosts: list[str]) -> str | None:
    for host in mx_hosts:
        for fragment, provider in MX_PROVIDERS.items():
            if host.lower().endswith(fragment):
                return provider
    return None


async def gravatar_profile(email: str, client: httpx.AsyncClient) -> dict[str, Any] | None:
    """Cherche le profil Gravatar public associé à l'adresse."""
    digest = hashlib.sha256(email.encode()).hexdigest()
    try:
        response = await client.get(f"https://gravatar.com/{digest}.json")
    except httpx.HTTPError as exc:
        return {"erreur": f"Gravatar injoignable ({type(exc).__name__})"}
    if response.status_code != 200:
        return None
    try:
        entry = response.json()["entry"][0]
    except (ValueError, KeyError, IndexError):
        return None
    profile = {
        "nom_affiche": entry.get("displayName"),
        "profil": entry.get("profileUrl"),
        "photo": entry.get("thumbnailUrl"),
        "localisation": entry.get("currentLocation"),
        "bio": entry.get("aboutMe"),
        "comptes_lies": [
            {"service": a.get("shortname") or a.get("domain"), "url": a.get("url")}
            for a in entry.get("accounts", [])
        ],
    }
    return {key: value for key, value in profile.items() if value}


async def email_lookup(email: str, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
    """Point d'entrée de l'outil : analyse une adresse e-mail."""
    email = normalize_email(email)
    domain = email.rsplit("@", 1)[1]

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)
    try:
        mx, gravatar = await asyncio.gather(mx_records(domain), gravatar_profile(email, client))
    finally:
        if own_client:
            await client.aclose()

    return {
        "email": email,
        "domaine": domain,
        "accepte_les_emails": bool(mx),
        "serveurs_mx": mx,
        "fournisseur": guess_provider(mx),
        "jetable": domain in DISPOSABLE_DOMAINS,
        "gravatar": gravatar,
    }
