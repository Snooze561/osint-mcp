import httpx
import pytest

from osint_mcp import config
from osint_mcp.tools import ip as ip_tool


@pytest.fixture(autouse=True)
def no_reverse_dns(monkeypatch):
    async def fake_reverse(ip):
        return ["dns.google"]

    monkeypatch.setattr(ip_tool, "reverse_dns", fake_reverse)


def handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    if host == "ipinfo.io":
        return httpx.Response(200, json={
            "ip": "8.8.8.8", "city": "Mountain View", "region": "California",
            "country": "US", "loc": "37.4056,-122.0775", "org": "AS15169 Google LLC",
        })
    if host == "internetdb.shodan.io":
        return httpx.Response(200, json={
            "ip": "8.8.8.8", "ports": [53, 443], "hostnames": ["dns.google"],
            "cpes": [], "vulns": [], "tags": [],
        })
    if host == "api.shodan.io":
        assert request.url.params["key"] == "cle-test"
        return httpx.Response(200, json={
            "org": "Google LLC", "isp": "Google LLC",
            "data": [{"port": 53, "transport": "udp", "product": "Google DNS",
                      "timestamp": "2026-10-30T12:00:00"}],
        })
    raise AssertionError(f"requête inattendue : {request.url}")


async def test_ip_lookup_without_key(monkeypatch, mock_client):
    monkeypatch.delenv(config.SHODAN, raising=False)
    async with mock_client(handler) as client:
        result = await ip_tool.ip_lookup(" 8.8.8.8 ", client=client)

    assert result["ip"] == "8.8.8.8"
    assert result["dns_inverse"] == ["dns.google"]
    assert result["localisation"]["organisation"] == "AS15169 Google LLC"
    assert "openstreetmap" in result["localisation"]["carte"]
    # Les listes vides sont retirées pour garder un résultat lisible.
    assert result["exposition_internet"] == {"ports_ouverts": [53, 443], "noms_d_hote": ["dns.google"]}
    assert "shodan" not in result
    assert "SHODAN_API_KEY" in result["astuce"]


async def test_ip_lookup_with_shodan_key(monkeypatch, mock_client):
    monkeypatch.setenv(config.SHODAN, "cle-test")
    async with mock_client(handler) as client:
        result = await ip_tool.ip_lookup("8.8.8.8", client=client)
    assert result["shodan"]["services"] == [
        {"port": 53, "protocole": "udp", "logiciel": "Google DNS", "vu_le": "2026-10-30"}
    ]


async def test_unknown_ip_in_internetdb(monkeypatch, mock_client):
    monkeypatch.delenv(config.SHODAN, raising=False)

    def not_found(request):
        if request.url.host == "internetdb.shodan.io":
            return httpx.Response(404, json={"detail": "No information available"})
        return handler(request)

    async with mock_client(not_found) as client:
        result = await ip_tool.ip_lookup("8.8.8.8", client=client)
    assert "Aucune donnée" in result["exposition_internet"]


@pytest.mark.parametrize("private", ["192.168.1.10", "127.0.0.1", "10.0.0.1", "::1"])
async def test_private_ip_is_not_looked_up(private):
    result = await ip_tool.ip_lookup(private)  # aucun appel réseau
    assert "privée" in result["remarque"]


async def test_invalid_ip():
    with pytest.raises(ValueError, match="recherche_domaine"):
        await ip_tool.ip_lookup("exemple.fr")
