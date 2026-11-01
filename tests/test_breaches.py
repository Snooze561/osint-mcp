import httpx

from osint_mcp import config
from osint_mcp.tools.breaches import email_breaches


async def test_without_key(monkeypatch):
    monkeypatch.delenv(config.HIBP, raising=False)
    result = await email_breaches("jean@exemple.fr")
    assert "HIBP_API_KEY" in result["erreur"]


async def test_with_breaches(monkeypatch, mock_client):
    monkeypatch.setenv(config.HIBP, "cle-test")

    def handler(request):
        assert request.headers["hibp-api-key"] == "cle-test"
        assert request.url.path == "/api/v3/breachedaccount/jean@exemple.fr"
        return httpx.Response(200, json=[
            {"Name": "Adobe", "Title": "Adobe", "Domain": "adobe.com", "BreachDate": "2013-10-04",
             "DataClasses": ["Email addresses", "Passwords"], "IsVerified": True},
            {"Name": "Canva", "Title": "Canva", "Domain": "canva.com", "BreachDate": "2019-05-24",
             "DataClasses": ["Email addresses", "Names"], "IsVerified": True},
        ])

    async with mock_client(handler) as client:
        result = await email_breaches("jean@exemple.fr", client=client)

    assert result["nombre_de_fuites"] == 2
    assert [b["nom"] for b in result["fuites"]] == ["Canva", "Adobe"]  # la plus récente d'abord


async def test_no_breach(monkeypatch, mock_client):
    monkeypatch.setenv(config.HIBP, "cle-test")
    async with mock_client(lambda request: httpx.Response(404)) as client:
        result = await email_breaches("jean@exemple.fr", client=client)
    assert result == {"email": "jean@exemple.fr", "nombre_de_fuites": 0, "fuites": []}


async def test_bad_key(monkeypatch, mock_client):
    monkeypatch.setenv(config.HIBP, "mauvaise")
    async with mock_client(lambda request: httpx.Response(401)) as client:
        result = await email_breaches("jean@exemple.fr", client=client)
    assert "refusée" in result["erreur"]
