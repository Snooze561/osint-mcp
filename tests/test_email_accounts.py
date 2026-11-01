from osint_mcp.tools.email_accounts import (
    PASSWORD_RECOVERY_MODULES,
    email_accounts,
    load_modules,
)


async def site_avec_compte(email, client, out):
    out.append({"name": "site_avec_compte", "domain": "a.com", "exists": True,
                "rateLimit": False, "emailrecovery": "j***@gmail.com", "phoneNumber": None})


async def site_sans_compte(email, client, out):
    out.append({"name": "site_sans_compte", "domain": "b.com", "exists": False, "rateLimit": False})


async def site_bloque(email, client, out):
    out.append({"name": "site_bloque", "domain": "c.com", "exists": None, "rateLimit": True})


async def site_casse(email, client, out):
    raise RuntimeError("le formulaire a changé")


async def test_email_accounts():
    modules = (site_avec_compte, site_sans_compte, site_bloque, site_casse)
    result = await email_accounts("Jean@Exemple.fr", modules=modules)

    assert result["email"] == "jean@exemple.fr"
    assert result["sites_verifies"] == 4
    assert result["comptes_trouves"] == [{"site": "a.com", "email_de_secours_masque": "j***@gmail.com"}]
    assert result["non_verifiables"] == ["c.com", "site_casse"]


def test_password_recovery_modules_are_excluded():
    names = {module.__name__ for module in load_modules()}
    assert len(names) > 100
    assert "github" in names
    assert not names & PASSWORD_RECOVERY_MODULES
