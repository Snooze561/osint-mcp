import httpx
import pytest

from osint_mcp.tools.username import (
    Site,
    by_status,
    json_not_empty,
    text_means_absent,
    username_search,
)

SITES = [
    Site("ParStatut", "https://statut.test/{}"),
    Site("ParTexte", "https://texte.test/{}", text_means_absent("Introuvable")),
    Site("ParJson", "https://json.test/{}", json_not_empty, check_url="https://json.test/api/{}"),
    Site("Bloque", "https://bloque.test/{}"),
    Site("Court", "https://court.test/{}", min_length=10),
]


def handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    if host == "statut.test":
        return httpx.Response(200)
    if host == "texte.test":
        return httpx.Response(200, text="<h1>Introuvable</h1>")
    if host == "json.test":
        assert request.url.path == "/api/alice"  # on interroge bien l'API
        return httpx.Response(200, json=[{"id": 1}])
    if host == "bloque.test":
        return httpx.Response(429)
    raise AssertionError(f"requête inattendue : {request.url}")


async def test_username_search_sorts_results(mock_client):
    async with mock_client(handler) as client:
        result = await username_search("@alice", sites=SITES, client=client)

    assert result["pseudo"] == "alice"
    assert result["trouves"] == [
        {"site": "ParStatut", "url": "https://statut.test/alice"},
        {"site": "ParJson", "url": "https://json.test/alice"},
    ]
    assert result["absents"] == ["ParTexte", "Court"]
    assert result["incertains"] == [{"site": "Bloque", "raison": "réponse inattendue (HTTP 429)"}]


async def test_network_error_is_uncertain(mock_client):
    def failing(request):
        raise httpx.ConnectError("boom")

    async with mock_client(failing) as client:
        result = await username_search("alice", sites=SITES[:1], client=client)
    assert result["incertains"][0]["raison"] == "erreur réseau (ConnectError)"


@pytest.mark.parametrize("bad", ["", "deux mots", "x" * 41, "a/b"])
async def test_rejects_invalid_username(bad):
    with pytest.raises(ValueError):
        await username_search(bad, sites=[])


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (httpx.Response(200, content=b"null"), False),
        (httpx.Response(200, json=[]), False),
        (httpx.Response(200, json={"them": [None]}), False),
        (httpx.Response(200, json={"them": [{"id": "x"}]}), True),
        (httpx.Response(404), False),
        (httpx.Response(200, text="pas du json"), None),
    ],
)
def test_json_not_empty(response, expected):
    assert json_not_empty(response) is expected


def test_by_status():
    assert by_status(httpx.Response(200)) is True
    assert by_status(httpx.Response(404)) is False
    assert by_status(httpx.Response(503)) is None


def test_lowercase_site():
    site = Site("X", "https://x.test/{}", lowercase=True)
    assert site.url_for("Alice") == "https://x.test/alice"
