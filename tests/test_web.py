"""Tests de l'interface web avec le client de test de FastAPI (aucun vrai serveur lancé)."""

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from osint_mcp.web import app as web_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # L'historique est écrit dans un dossier temporaire, pas dans ~/.osint-mcp.
    monkeypatch.setenv("OSINT_MCP_DATA", str(tmp_path / "data"))
    return TestClient(web_app.app)


@pytest.fixture
def fake_tool(monkeypatch):
    async def fake_domain(valeur):
        if valeur == "invalide":
            raise ValueError("Nom de domaine invalide : 'invalide'")
        return {"domaine": valeur, "dns": {"A": ["1.2.3.4"]}}

    tool = web_app.TOOLS["recherche_domaine"]
    monkeypatch.setitem(
        web_app.TOOLS, "recherche_domaine",
        web_app.WebTool(tool.label, tool.description, tool.placeholder, fake_domain, tool.categorie),
    )


def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "osint-mcp" in response.text
    assert client.get("/static/app.js").status_code == 200


def test_list_tools(client):
    tools = client.get("/api/outils").json()
    ids = [t["id"] for t in tools]
    assert len(ids) == 8
    assert "metadonnees_image" in ids
    assert next(t for t in tools if t["id"] == "metadonnees_image")["type"] == "fichier"


def test_run_tool_and_history(client, fake_tool):
    response = client.post("/api/outils/recherche_domaine", json={"valeur": " exemple.fr "})
    assert response.status_code == 200
    data = response.json()
    assert data["valeur"] == "exemple.fr"
    assert data["resultat"]["dns"]["A"] == ["1.2.3.4"]

    history = client.get("/api/historique").json()
    assert [(h["outil"], h["valeur"]) for h in history] == [("recherche_domaine", "exemple.fr")]

    detail = client.get(f"/api/historique/{history[0]['id']}").json()
    assert detail["resultat"] == data["resultat"]

    assert client.delete("/api/historique").status_code == 204
    assert client.get("/api/historique").json() == []


def test_invalid_input_returns_400(client, fake_tool):
    response = client.post("/api/outils/recherche_domaine", json={"valeur": "invalide"})
    assert response.status_code == 400
    assert "invalide" in response.json()["detail"]
    assert client.get("/api/historique").json() == []


def test_unknown_tool(client):
    assert client.post("/api/outils/inconnu", json={"valeur": "x"}).status_code == 404
    assert client.get("/api/historique/999").status_code == 404


def test_image_upload(client, tmp_path):
    photo = tmp_path / "photo.png"
    Image.new("RGB", (20, 10)).save(photo)
    with photo.open("rb") as f:
        response = client.post("/api/image", files={"fichier": ("vacances.png", f, "image/png")})
    assert response.status_code == 200
    result = response.json()["resultat"]
    assert result["fichier"] == "vacances.png"  # pas le chemin temporaire
    assert result["dimensions"] == "20 x 10"


def test_upload_that_is_not_an_image(client):
    response = client.post("/api/image", files={"fichier": ("notes.txt", b"bonjour", "text/plain")})
    assert response.status_code == 400
