"""Petites fonctions de validation partagées par les outils."""

import re

# Un nom de domaine : des "labels" de 1 à 63 caractères séparés par des points,
# et une extension (TLD) d'au moins 2 lettres.
_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)([a-z0-9-]{1,63}(?<!-)\.)+[a-z]{2,63}$"
)

# Volontairement simple : on vérifie la forme générale "quelquechose@domaine".
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+$")


def normalize_domain(value: str) -> str:
    """Nettoie un domaine saisi par l'utilisateur et vérifie qu'il est valide.

    Accepte aussi une URL complète (https://www.exemple.fr/page) et n'en garde
    que le domaine.
    """
    domain = value.strip().lower()
    domain = re.sub(r"^[a-z]+://", "", domain)  # retire http:// ou https://
    domain = domain.split("/")[0].split(":")[0]  # retire le chemin et le port
    domain = domain.rstrip(".")
    if not _DOMAIN_RE.match(domain):
        raise ValueError(f"Nom de domaine invalide : {value!r}")
    return domain


def normalize_email(value: str) -> str:
    """Nettoie une adresse e-mail et vérifie sa forme."""
    email = value.strip().lower()
    if not _EMAIL_RE.match(email):
        raise ValueError(f"Adresse e-mail invalide : {value!r}")
    domain = email.rsplit("@", 1)[1]
    normalize_domain(domain)  # lève une erreur si le domaine est invalide
    return email
