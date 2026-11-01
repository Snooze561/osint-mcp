import pytest

from osint_mcp.tools.validation import normalize_domain, normalize_email


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Exemple.FR", "exemple.fr"),
        ("https://www.exemple.fr/page?x=1", "www.exemple.fr"),
        ("exemple.fr.", "exemple.fr"),
        ("http://sous.domaine.co.uk:8080", "sous.domaine.co.uk"),
    ],
)
def test_normalize_domain(value, expected):
    assert normalize_domain(value) == expected


@pytest.mark.parametrize("value", ["", "localhost", "-bad.com", "a b.com", "exemple.f"])
def test_normalize_domain_rejects(value):
    with pytest.raises(ValueError):
        normalize_domain(value)


def test_normalize_email():
    assert normalize_email("  Jean.Dupont@Exemple.FR ") == "jean.dupont@exemple.fr"


@pytest.mark.parametrize("value", ["pas-un-email", "a@b@c.fr", "jean@", "jean@localhost"])
def test_normalize_email_rejects(value):
    with pytest.raises(ValueError):
        normalize_email(value)
