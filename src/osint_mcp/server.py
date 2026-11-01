"""Le serveur MCP : il expose les outils OSINT à Claude (ou à tout client MCP).

MCP (Model Context Protocol) est un protocole qui permet à une IA d'appeler
des fonctions d'un programme externe. Ici, chaque fonction décorée par
`@mcp.tool()` devient un outil que Claude peut utiliser. Sa docstring sert de
description : c'est elle qui explique à Claude quand et comment s'en servir,
il faut donc la rédiger avec soin.

Par défaut le serveur communique en "stdio" : Claude Desktop lance ce
programme et dialogue avec lui via l'entrée/sortie standard.
"""

import argparse
import os
import sys
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from .tools.breaches import email_breaches
from .tools.domain import domain_lookup
from .tools.email import email_lookup
from .tools.email_accounts import email_accounts
from .tools.image import image_metadata
from .tools.ip import ip_lookup
from .tools.subdomains import subdomain_search
from .tools.username import username_search

mcp = MCPServer(
    name="osint-mcp",
    instructions=(
        "Boîte à outils OSINT (renseignement en sources ouvertes). "
        "N'utilise ces outils que sur des cibles légitimes : soi-même, des "
        "personnes ou organisations consentantes, ou dans un cadre autorisé "
        "(CTF, audit, journalisme). Présente les résultats comme des pistes "
        "à recouper, pas comme des certitudes."
    ),
)


@mcp.tool()
async def recherche_domaine(domaine: str) -> dict[str, Any]:
    """Analyse un nom de domaine : enregistrements DNS (A, AAAA, MX, NS, TXT, SOA)
    et informations WHOIS (registrar, dates de création et d'expiration,
    organisation, serveurs de noms).

    Args:
        domaine: le domaine à analyser, par exemple "exemple.fr" (une URL
            complète est aussi acceptée).
    """
    return await domain_lookup(domaine)


@mcp.tool()
async def recherche_pseudo(pseudo: str) -> dict[str, Any]:
    """Cherche sur quels sites (GitHub, Reddit, Telegram, Steam, Bluesky...)
    un compte existe avec ce pseudo. Renvoie les comptes trouvés avec leur
    lien, les sites où il est absent et ceux où le résultat est incertain.

    Args:
        pseudo: le nom d'utilisateur à chercher, sans espace.
    """
    return await username_search(pseudo)


@mcp.tool()
async def analyse_email(email: str) -> dict[str, Any]:
    """Analyse une adresse e-mail sans clé API : le domaine accepte-t-il des
    e-mails, quel est le fournisseur de messagerie, est-ce une adresse
    jetable, et existe-t-il un profil Gravatar public (nom, photo, comptes liés).

    Args:
        email: l'adresse e-mail à analyser.
    """
    return await email_lookup(email)


@mcp.tool()
def metadonnees_image(chemin: str) -> dict[str, Any]:
    """Extrait les métadonnées EXIF d'une image présente sur l'ordinateur :
    appareil photo, date de prise de vue, logiciel et coordonnées GPS
    (avec un lien vers la carte) si elles sont présentes.

    Args:
        chemin: le chemin complet du fichier image, par exemple
            "C:/Users/moi/Images/photo.jpg" ou "~/Images/photo.jpg".
    """
    return image_metadata(chemin)


@mcp.tool()
async def sous_domaines(domaine: str) -> dict[str, Any]:
    """Liste les sous-domaines connus d'un domaine (ex. mail.exemple.fr,
    dev.exemple.fr) grâce aux journaux publics de certificats HTTPS
    (Certificate Transparency, via crt.sh). Méthode passive : aucun contact
    avec les serveurs de la cible. Peut prendre jusqu'à 45 secondes.

    Args:
        domaine: le domaine principal, par exemple "exemple.fr".
    """
    return await subdomain_search(domaine)


@mcp.tool()
async def analyse_ip(ip: str) -> dict[str, Any]:
    """Analyse une adresse IP publique : localisation approximative,
    propriétaire (fournisseur, hébergeur), DNS inverse, ports ouverts et
    vulnérabilités connues d'après Shodan (InternetDB gratuit, ou API
    complète si une clé est configurée).

    Args:
        ip: l'adresse IPv4 ou IPv6, par exemple "8.8.8.8".
    """
    return await ip_lookup(ip)


@mcp.tool()
async def comptes_email(email: str) -> dict[str, Any]:
    """Cherche sur plus de 110 sites (réseaux sociaux, services en ligne...)
    si un compte est inscrit avec cette adresse e-mail, grâce à holehe.
    Peut révéler des indices comme un e-mail de secours ou un téléphone
    partiellement masqués. Prend 10 à 30 secondes.

    Args:
        email: l'adresse e-mail à vérifier.
    """
    return await email_accounts(email)


@mcp.tool()
async def fuites_email(email: str) -> dict[str, Any]:
    """Liste les fuites de données publiques (Have I Been Pwned) qui
    contiennent cette adresse e-mail : nom du site, date de la fuite et
    types de données exposées. Nécessite une clé HIBP_API_KEY.

    Args:
        email: l'adresse e-mail à vérifier.
    """
    return await email_breaches(email)


def http_security(host: str) -> TransportSecuritySettings | None:
    """Protection contre le "DNS rebinding" quand le serveur écoute sur le réseau.

    Le serveur n'accepte que les requêtes adressées à localhost, plus les noms
    listés dans la variable OSINT_ALLOWED_HOSTS (ex. "osint.mondomaine.fr:*").
    Sur 127.0.0.1, le SDK MCP active déjà cette protection tout seul.
    """
    if host in ("127.0.0.1", "localhost", "::1"):
        return None
    extra = [h.strip() for h in os.environ.get("OSINT_ALLOWED_HOSTS", "").split(",") if h.strip()]
    return TransportSecuritySettings(
        allowed_hosts=["127.0.0.1:*", "localhost:*", *extra],
        allowed_origins=["http://127.0.0.1:*", "http://localhost:*",
                         *(f"https://{h.removesuffix(':*')}" for h in extra)],
    )


def main() -> None:
    """Lance le serveur (commande `osint-mcp`).

    - `osint-mcp`        : mode stdio, pour Claude Desktop (par défaut) ;
    - `osint-mcp --http` : mode HTTP, adresse http://127.0.0.1:8001/mcp, pour
      un serveur qui tourne en continu (Docker, hébergement).
    """
    parser = argparse.ArgumentParser(description="Serveur MCP osint-mcp")
    parser.add_argument("--http", action="store_true", help="servir en HTTP au lieu de stdio")
    parser.add_argument("--host", default="127.0.0.1", help="adresse d'écoute en HTTP")
    parser.add_argument("--port", type=int, default=8001, help="port en HTTP (8001 par défaut)")
    args = parser.parse_args()

    if not args.http:
        mcp.run()
        return
    print(f"Serveur MCP en HTTP sur http://{args.host}:{args.port}/mcp", file=sys.stderr)
    mcp.run(
        transport="streamable-http",
        host=args.host,
        port=args.port,
        transport_security=http_security(args.host),
    )


if __name__ == "__main__":
    main()
