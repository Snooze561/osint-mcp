"""Outil "domaine" : enregistrements DNS et informations WHOIS.

En OSINT, un domaine est souvent le point de départ d'une enquête :
- le DNS dit OÙ sont hébergés le site (A/AAAA), les e-mails (MX), qui gère
  la zone (NS), et contient parfois des indices (TXT : vérifications Google,
  services utilisés...) ;
- le WHOIS dit QUI a enregistré le domaine, chez quel registrar et QUAND.
"""

import asyncio
from datetime import date, datetime
from typing import Any

import dns.asyncresolver
import dns.exception
import dns.resolver
import whois

from .validation import normalize_domain

RECORD_TYPES = ["A", "AAAA", "MX", "NS", "TXT", "SOA"]

# Les champs WHOIS les plus utiles. Le format brut varie énormément d'un
# registrar à l'autre, on ne garde donc que ceux-là.
WHOIS_FIELDS = [
    "registrar",
    "creation_date",
    "updated_date",
    "expiration_date",
    "name_servers",
    "status",
    "emails",
    "org",
    "country",
    "dnssec",
]


async def dns_records(domain: str) -> dict[str, list[str]]:
    """Récupère les principaux enregistrements DNS d'un domaine."""
    resolver = dns.asyncresolver.Resolver()
    resolver.lifetime = 5.0  # secondes max par requête

    async def query(rtype: str) -> tuple[str, list[str]]:
        try:
            answer = await resolver.resolve(domain, rtype)
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
            return rtype, []
        except dns.exception.Timeout:
            return rtype, ["(délai dépassé)"]
        return rtype, sorted(record.to_text() for record in answer)

    # asyncio.gather lance toutes les requêtes en parallèle.
    results = await asyncio.gather(*(query(rtype) for rtype in RECORD_TYPES))
    return {rtype: values for rtype, values in results if values}


def _to_json(value: Any) -> Any:
    """Convertit les valeurs WHOIS (dates, listes, ensembles) en JSON simple."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (list, tuple, set)):
        items = [_to_json(v) for v in value]
        # Supprime les doublons, fréquents dans les WHOIS ("NS1.OVH.NET" et
        # "ns1.ovh.net"). On compare sans tenir compte des majuscules.
        unique: dict[Any, Any] = {}
        for item in items:
            key = item.lower() if isinstance(item, str) else item
            unique.setdefault(key, item)
        values = list(unique.values())
        return values[0] if len(values) == 1 else values
    return value


async def whois_info(domain: str) -> dict[str, Any]:
    """Interroge le WHOIS d'un domaine."""
    try:
        # python-whois n'est pas asynchrone : on l'exécute dans un thread
        # pour ne pas bloquer le serveur pendant la requête réseau.
        entry = await asyncio.to_thread(whois.whois, domain)
    except Exception as exc:  # noqa: BLE001 - le WHOIS échoue souvent (quotas, TLD exotiques...)
        return {"erreur": f"WHOIS indisponible : {exc}"}
    return {field: _to_json(entry.get(field)) for field in WHOIS_FIELDS if entry.get(field)}


async def domain_lookup(domain: str) -> dict[str, Any]:
    """Point d'entrée de l'outil : DNS + WHOIS d'un domaine."""
    domain = normalize_domain(domain)
    dns_result, whois_result = await asyncio.gather(dns_records(domain), whois_info(domain))
    return {"domaine": domain, "dns": dns_result, "whois": whois_result}
