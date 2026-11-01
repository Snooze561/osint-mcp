"""Test de bout en bout : un vrai client MCP parle au serveur, comme le ferait Claude."""

from mcp import Client
from PIL import Image

from osint_mcp.server import mcp


async def test_server_exposes_the_tools():
    async with Client(mcp) as client:
        tools = await client.list_tools()
    names = {tool.name for tool in tools.tools}
    assert names == {"recherche_domaine", "recherche_pseudo", "analyse_email", "metadonnees_image"}


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
