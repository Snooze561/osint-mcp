"""Outil "pseudo" : sur quels sites ce pseudo possède-t-il un compte ?

Les gens réutilisent souvent le même pseudo partout. Retrouver ses comptes
permet de recouper des informations (photo, bio, liens, localisation...).
C'est le principe d'outils célèbres comme Sherlock ou Maigret, que l'on
réimplémente ici en version simple pour comprendre comment ils marchent.

Le principe : pour chaque site, on demande la page (ou l'API) du profil,
puis on regarde la réponse pour décider si le compte existe :
- code HTTP 200 = trouvé, 404 = absent (le cas le plus fréquent) ;
- ou bien la présence/absence d'un texte dans la page ;
- ou bien le contenu d'une réponse JSON.
"""

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

# Résultat d'une vérification : True = trouvé, False = absent, None = on ne sait pas.
Verdict = bool | None

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
)

_USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,40}$")


def by_status(response: httpx.Response) -> Verdict:
    """200 = le profil existe, 404 = il n'existe pas, autre = incertain."""
    if response.status_code == 200:
        return True
    if response.status_code == 404:
        return False
    return None


def text_means_absent(marker: str) -> Callable[[httpx.Response], Verdict]:
    """Le site répond toujours 200, mais affiche `marker` si le profil n'existe pas."""

    def check(response: httpx.Response) -> Verdict:
        if response.status_code != 200:
            return by_status(response)
        return marker not in response.text

    return check


def text_means_present(marker: str) -> Callable[[httpx.Response], Verdict]:
    """Le site répond toujours 200, mais n'affiche `marker` que si le profil existe."""

    def check(response: httpx.Response) -> Verdict:
        if response.status_code != 200:
            return by_status(response)
        return marker in response.text

    return check


def json_not_empty(response: httpx.Response) -> Verdict:
    """L'API renvoie `null`, `[]` ou `[null]` quand l'utilisateur n'existe pas."""
    if response.status_code != 200:
        return by_status(response)
    try:
        data = response.json()
    except ValueError:
        return None
    if isinstance(data, dict) and "them" in data:  # format de l'API Keybase
        data = data["them"]
    return data not in (None, [], [None])


def bluesky_check(response: httpx.Response) -> Verdict:
    """L'API Bluesky répond 400 quand le profil n'existe pas."""
    if response.status_code == 400:
        return False
    return by_status(response)


@dataclass(frozen=True)
class Site:
    name: str
    profile_url: str  # l'adresse du profil, montrée à l'utilisateur
    check: Callable[[httpx.Response], Verdict] = by_status
    check_url: str | None = None  # adresse interrogée si différente (souvent une API)
    lowercase: bool = False  # certains sites n'acceptent le pseudo qu'en minuscules
    min_length: int = 1

    def url_for(self, username: str, *, for_check: bool = False) -> str:
        if self.lowercase:
            username = username.lower()
        template = self.check_url if for_check and self.check_url else self.profile_url
        return template.format(username)


# Pour ajouter un site : trouver une adresse dont la réponse diffère selon que
# le compte existe ou non, puis l'ajouter ici. C'est un bon exercice !
SITES: list[Site] = [
    Site("GitHub", "https://github.com/{}", check_url="https://api.github.com/users/{}"),
    Site("GitLab", "https://gitlab.com/{}", json_not_empty,
         check_url="https://gitlab.com/api/v4/users?username={}"),
    Site("Codeberg", "https://codeberg.org/{}", check_url="https://codeberg.org/api/v1/users/{}"),
    Site("Bitbucket", "https://bitbucket.org/{}/",
         check_url="https://api.bitbucket.org/2.0/workspaces/{}"),
    Site("Docker Hub", "https://hub.docker.com/u/{}", check_url="https://hub.docker.com/v2/users/{}/"),
    Site("PyPI", "https://pypi.org/user/{}/"),
    Site("Dev.to", "https://dev.to/{}", check_url="https://dev.to/api/users/by_username?url={}"),
    Site("Hacker News", "https://news.ycombinator.com/user?id={}", json_not_empty,
         check_url="https://hacker-news.firebaseio.com/v0/user/{}.json"),
    Site("Keybase", "https://keybase.io/{}", json_not_empty,
         check_url="https://keybase.io/_/api/1.0/user/lookup.json?usernames={}"),
    Site("Reddit", "https://www.reddit.com/user/{}", check_url="https://www.reddit.com/user/{}/about.json"),
    Site("Mastodon (mastodon.social)", "https://mastodon.social/@{}",
         check_url="https://mastodon.social/api/v1/accounts/lookup?acct={}"),
    Site("Bluesky", "https://bsky.app/profile/{}.bsky.social", bluesky_check, lowercase=True,
         check_url="https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={}.bsky.social"),
    Site("Telegram", "https://t.me/{}", text_means_present("tgme_page_title"), min_length=5),
    Site("Steam", "https://steamcommunity.com/id/{}",
         text_means_absent("The specified profile could not be found")),
    Site("Chess.com", "https://www.chess.com/member/{}", lowercase=True,
         check_url="https://api.chess.com/pub/player/{}"),
    Site("Lichess", "https://lichess.org/@/{}", check_url="https://lichess.org/api/user/{}"),
]


async def check_site(client: httpx.AsyncClient, site: Site, username: str) -> dict[str, Any]:
    """Vérifie un seul site et renvoie un petit dictionnaire de résultat."""
    result: dict[str, Any] = {"site": site.name, "url": site.url_for(username)}
    if len(username) < site.min_length:
        result["verdict"] = False
        return result
    try:
        response = await client.get(site.url_for(username, for_check=True))
    except httpx.HTTPError as exc:
        result["verdict"] = None
        result["raison"] = f"erreur réseau ({type(exc).__name__})"
        return result
    result["verdict"] = site.check(response)
    if result["verdict"] is None:
        result["raison"] = f"réponse inattendue (HTTP {response.status_code})"
    return result


async def username_search(
    username: str,
    sites: list[Site] | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Point d'entrée de l'outil : cherche un pseudo sur tous les sites connus."""
    username = username.strip().lstrip("@")
    if not _USERNAME_RE.match(username):
        raise ValueError(
            f"Pseudo invalide : {username!r} (lettres, chiffres, '.', '_' et '-' uniquement)"
        )
    sites = SITES if sites is None else sites

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=10.0,
            follow_redirects=True,
        )
    try:
        # On interroge tous les sites en même temps plutôt que l'un après l'autre.
        results = await asyncio.gather(*(check_site(client, s, username) for s in sites))
    finally:
        if own_client:
            await client.aclose()

    return {
        "pseudo": username,
        "trouves": [{"site": r["site"], "url": r["url"]} for r in results if r["verdict"] is True],
        "absents": [r["site"] for r in results if r["verdict"] is False],
        "incertains": [
            {"site": r["site"], "raison": r["raison"]} for r in results if r["verdict"] is None
        ],
        "avertissement": (
            "Un compte trouvé porte le même pseudo, mais n'appartient pas forcément "
            "à la même personne : recoupez avant de conclure."
        ),
    }
