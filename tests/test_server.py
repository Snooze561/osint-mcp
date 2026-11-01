"""Test de bout en bout : un vrai client MCP parle au serveur, comme le ferait Claude."""

from mcp import Client
from PIL import Image

from osint_mcp.server import mcp


async def test_server_exposes_the_tools():
    async with Client(mcp) as client:
        tools = await client.list_tools()
    names = {tool.name for tool in tools.tools}
    assert names == {
        "recherche_domaine", "recherche_pseudo", "analyse_email", "metadonnees_image",
        "sous_domaines", "analyse_ip", "comptes_email", "fuites_email",
    }


async def test_call_image_tool(tmp_path):
    photo = tmp_path / "photo.png"
    Image.new("RGB", (10, 10)).save(photo)
    async with Client(mcp) as client:
        result = await client.call_tool("metadonnees_image", {"chemin": str(photo)})
    assert not result.is_error
    assert result.structured_content["format"] == "PNG"


async def test_invalid_input_returns_an_error():
    async with Client(mcp) as client:
        result = await client.call_tool("recherche_domaine", {"domaine": "pas un domaine"})
    assert result.is_error


def test_http_security_on_localhost_is_left_to_the_sdk():
    from osint_mcp.server import http_security

    assert http_security("127.0.0.1") is None


def test_http_security_in_docker(monkeypatch):
    from osint_mcp.server import http_security

    monkeypatch.setenv("OSINT_ALLOWED_HOSTS", "osint.exemple.fr:*")
    settings = http_security("0.0.0.0")
    assert settings.enable_dns_rebinding_protection
    assert settings.allowed_hosts == ["127.0.0.1:*", "localhost:*", "osint.exemple.fr:*"]
    assert "https://osint.exemple.fr" in settings.allowed_origins
