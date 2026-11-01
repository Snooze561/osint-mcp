from datetime import datetime

from osint_mcp.tools import domain as domain_tool


async def test_domain_lookup(monkeypatch):
    async def fake_dns(domain):
        return {"A": ["93.184.215.14"], "MX": ["10 mail.exemple.fr."]}

    def fake_whois(domain):
        return {
            "registrar": "OVH",
            # Les registrars renvoient souvent la même date en double.
            "creation_date": [datetime(2001, 5, 3), datetime(2001, 5, 3)],
            "name_servers": ["NS1.OVH.NET", "ns1.ovh.net", "ns2.ovh.net"],
            "emails": None,
        }

    monkeypatch.setattr(domain_tool, "dns_records", fake_dns)
    monkeypatch.setattr(domain_tool.whois, "whois", fake_whois)

    result = await domain_tool.domain_lookup("https://Exemple.fr/")

    assert result["domaine"] == "exemple.fr"
    assert result["dns"]["A"] == ["93.184.215.14"]
    assert result["whois"] == {
        "registrar": "OVH",
        "creation_date": "2001-05-03T00:00:00",
        "name_servers": ["NS1.OVH.NET", "ns2.ovh.net"],
    }


async def test_whois_failure_is_reported(monkeypatch):
    def broken(domain):
        raise ConnectionError("quota dépassé")

    monkeypatch.setattr(domain_tool.whois, "whois", broken)
    result = await domain_tool.whois_info("exemple.fr")
    assert "quota dépassé" in result["erreur"]
