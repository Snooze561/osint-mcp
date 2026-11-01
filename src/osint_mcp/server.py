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

from .tools.domain import domain_lookup
from .tools.email import email_lookup
from .tools.image import image_metadata
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


def main() -> None:
    """Lance le serveur (commande `osint-mcp`)."""
    mcp.run()


if __name__ == "__main__":
    main()
