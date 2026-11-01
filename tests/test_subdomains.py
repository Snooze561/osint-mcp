import httpx

from osint_mcp.tools.subdomains import extract_subdomains, subdomain_search


def test_extract_subdomains():
    entries = [
        {"name_value": "exemple.fr\nwww.exemple.fr"},
        {"name_value": "*.dev.exemple.fr"},
        {"name_value": "MAIL.exemple.fr"},
        {"name_value": "exemple.fr.pirate.com"},  # ne fait pas partie du domaine
        {"name_value": "autreexemple.fr"},  # non plus
    ]
    assert extract_subdomains(entries, "exemple.fr") == [
        "dev.exemple.fr",
        "exemple.fr",
        "mail.exemple.fr",
        "www.exemple.fr",
    ]


async def test_subdomain_search(mock_client):
    def handler(request):
        assert request.url.params["q"] == "%.exemple.fr"
        return httpx.Response(200, json=[{"name_value": "a.exemple.fr\nb.exemple.fr"}])

    async with mock_client(handler) as client:
        result = await subdomain_search("exemple.fr", client=client)
    assert result["nombre"] == 2
    assert result["sous_domaines"] == ["a.exemple.fr", "b.exemple.fr"]


async def test_crtsh_down(mock_client):
    async with mock_client(lambda request: httpx.Response(502)) as client:
        result = await subdomain_search("exemple.fr", client=client)
    assert "réessaie" in result["erreur"]
