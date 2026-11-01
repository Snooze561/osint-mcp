import hashlib

import httpx

from osint_mcp.tools import email as email_tool


async def test_email_lookup(monkeypatch, mock_client):
    async def fake_mx(domain):
        assert domain == "exemple.fr"
        return ["aspmx.l.google.com", "alt1.aspmx.l.google.com"]

    monkeypatch.setattr(email_tool, "mx_records", fake_mx)
    expected_hash = hashlib.sha256(b"jean@exemple.fr").hexdigest()

    def handler(request):
        assert request.url.path == f"/{expected_hash}.json"
        return httpx.Response(200, json={"entry": [{
            "displayName": "Jean D.",
            "profileUrl": "https://gravatar.com/jeand",
            "accounts": [{"shortname": "github", "url": "https://github.com/jeand"}],
        }]})

    async with mock_client(handler) as client:
        result = await email_tool.email_lookup("Jean@Exemple.fr", client=client)

    assert result["accepte_les_emails"] is True
    assert result["fournisseur"] == "Google (Gmail / Google Workspace)"
    assert result["jetable"] is False
    assert result["gravatar"] == {
        "nom_affiche": "Jean D.",
        "profil": "https://gravatar.com/jeand",
        "comptes_lies": [{"service": "github", "url": "https://github.com/jeand"}],
    }


async def test_disposable_without_gravatar(monkeypatch, mock_client):
    async def no_mx(domain):
        return []

    monkeypatch.setattr(email_tool, "mx_records", no_mx)
    async with mock_client(lambda request: httpx.Response(404)) as client:
        result = await email_tool.email_lookup("test@yopmail.com", client=client)

    assert result["jetable"] is True
    assert result["accepte_les_emails"] is False
    assert result["fournisseur"] is None
    assert result["gravatar"] is None
