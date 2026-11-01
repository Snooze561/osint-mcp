"""Le serveur MCP : il expose les outils OSINT à Claude (ou à tout client MCP).

MCP (Model Context Protocol) est un protocole qui permet à une IA d'appeler
des fonctions d'un programme externe. Ici, chaque fonction décorée par
`@mcp.tool()` devient un outil que Claude peut utiliser. Sa docstring sert de
description : c'est elle qui explique à Claude quand et comment s'en servir,
il faut donc la rédiger avec soin.

Par défaut le serveur communique en "stdio" : Claude Desktop lance ce
programme et dialogue avec lui via l'entrée/sortie standard.
"""

from typing import Any

from mcp.server.mcpserver import MCPServer

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


def main() -> None:
    """Lance le serveur (commande `osint-mcp`)."""
    mcp.run()


if __name__ == "__main__":
    main()
