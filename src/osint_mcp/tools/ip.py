"""Outil "adresse IP" : localisation, propriétaire et services exposés.

À partir d'une adresse IP, on peut souvent savoir :
- où elle est située (pays, ville approximative) et qui la possède
  (fournisseur d'accès, hébergeur, entreprise) grâce à ipinfo.io ;
- quel nom de machine lui est associé (DNS inverse, ou "PTR") ;
- quels ports et services elle expose sur Internet, et s'ils ont des
  vulnérabilités connues, grâce à Shodan. Shodan scanne Internet en
  permanence : on consulte ses résultats sans jamais scanner nous-mêmes.

Sans clé, on utilise InternetDB, la version gratuite et simplifiée de Shodan.
Avec une clé SHODAN_API_KEY, on obtient en plus le détail de chaque service.
"""

import asyncio
import ipaddress
from typing import Any

import dns.asyncresolver
import dns.exception
import dns.resolver
import httpx

from .. import config


def normalize_ip(value: str) -> str:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        raise ValueError(
            f"Adresse IP invalide : {value!r}. Pour un nom de domaine, utilise "
            "plutôt l'outil recherche_domaine, qui donne ses adresses IP."
        ) from None


async def reverse_dns(ip: str) -> list[str]:
    resolver = dns.asyncresolver.Resolver()
    resolver.lifetime = 5.0
    try:
        answer = await resolver.resolve_address(ip)
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN,
            dns.resolver.NoNameservers, dns.exception.Timeout):
        return []
    return sorted(r.to_text().rstrip(".") for r in answer)


async def geolocation(ip: str, client: httpx.AsyncClient) -> dict[str, Any]:
    """Localisation et propriétaire via ipinfo.io (gratuit, sans clé)."""
    try:
        response = await client.get(f"https://ipinfo.io/{ip}/json")
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return {"erreur": f"ipinfo.io indisponible ({type(exc).__name__})"}
    result = {
        "pays": data.get("country"),
        "region": data.get("region"),
        "ville": data.get("city"),
        "coordonnees": data.get("loc"),
        "organisation": data.get("org"),  # ex. "AS16276 OVH SAS"
        "fuseau_horaire": data.get("timezone"),
    }
    if data.get("loc"):
        lat, _, lon = data["loc"].partition(",")
        result["carte"] = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=11/{lat}/{lon}"
        result["precision"] = "approximative (souvent la ville du fournisseur, pas l'adresse exacte)"
    return {key: value for key, value in result.items() if value}


async def internetdb(ip: str, client: httpx.AsyncClient) -> dict[str, Any] | None:
    """Ports ouverts et vulnérabilités connues via InternetDB (Shodan gratuit)."""
    try:
        response = await client.get(f"https://internetdb.shodan.io/{ip}")
    except httpx.HTTPError as exc:
        return {"erreur": f"InternetDB indisponible ({type(exc).__name__})"}
    if response.status_code == 404:
        return None  # Shodan n'a rien vu sur cette IP
    try:
        data = response.json()
    except ValueError:
        return {"erreur": "réponse illisible d'InternetDB"}
    result = {
        "ports_ouverts": data.get("ports"),
        "noms_d_hote": data.get("hostnames"),
        "logiciels": data.get("cpes"),  # format CPE, ex. "cpe:/a:nginx:nginx"
        "vulnerabilites": data.get("vulns"),  # identifiants CVE
        "etiquettes": data.get("tags"),  # ex. "cloud", "vpn", "self-signed"
    }
    return {key: value for key, value in result.items() if value}


async def shodan_host(ip: str, key: str, client: httpx.AsyncClient) -> dict[str, Any] | None:
    """Détail des services via l'API Shodan complète (clé nécessaire)."""
    try:
        response = await client.get(f"https://api.shodan.io/shodan/host/{ip}", params={"key": key})
    except httpx.HTTPError as exc:
        return {"erreur": f"Shodan indisponible ({type(exc).__name__})"}
    if response.status_code == 404:
        return None
    if response.status_code in (401, 403):
        return {"erreur": "clé Shodan refusée ou abonnement insuffisant"}
    try:
        data = response.json()
    except ValueError:
        return {"erreur": "réponse illisible de Shodan"}
    services = [
        {
            "port": s.get("port"),
            "protocole": s.get("transport"),
            "logiciel": " ".join(filter(None, [s.get("product"), s.get("version")])) or None,
            "vu_le": (s.get("timestamp") or "")[:10] or None,
        }
        for s in data.get("data", [])
    ]
    result = {
        "organisation": data.get("org"),
        "fournisseur": data.get("isp"),
        "systeme": data.get("os"),
        "derniere_mise_a_jour": data.get("last_update"),
        "services": [{k: v for k, v in s.items() if v} for s in services],
    }
    return {key: value for key, value in result.items() if value}


async def ip_lookup(ip: str, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
    """Point d'entrée de l'outil : analyse une adresse IP."""
    ip = normalize_ip(ip)
    address = ipaddress.ip_address(ip)
    if not address.is_global:
        return {
            "ip": ip,
            "remarque": "Adresse privée ou réservée (réseau local, localhost...) : "
            "elle n'est pas visible sur Internet, il n'y a rien à chercher en ligne.",
        }

    shodan_key = config.get_key(config.SHODAN)
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=15.0, follow_redirects=True)
    try:
        tasks = [reverse_dns(ip), geolocation(ip, client), internetdb(ip, client)]
        if shodan_key:
            tasks.append(shodan_host(ip, shodan_key, client))
        results = await asyncio.gather(*tasks)
    finally:
        if own_client:
            await client.aclose()

    result: dict[str, Any] = {
        "ip": ip,
        "version": f"IPv{address.version}",
        "dns_inverse": results[0],
        "localisation": results[1],
        "exposition_internet": results[2]
        or "Aucune donnée : Shodan n'a vu aucun service ouvert sur cette IP.",
    }
    if shodan_key:
        result["shodan"] = results[3] or "Shodan ne connaît pas cette IP."
    else:
        result["astuce"] = (
            "Ajoute une clé SHODAN_API_KEY dans le fichier .env pour obtenir "
            "le détail de chaque service (voir .env.example)."
        )
    return result
