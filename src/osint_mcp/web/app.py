"""L'application web (FastAPI).

FastAPI transforme des fonctions Python en adresses web (une "API") :
- GET  /                         → la page web (fichiers du dossier static/)
- GET  /api/outils               → la liste des outils disponibles
- POST /api/outils/{outil}       → lance un outil avec la valeur saisie
- POST /api/image                → analyse une photo envoyée depuis le navigateur
- GET  /api/historique           → les dernières recherches
- GET  /api/historique/{numéro}  → le résultat d'une ancienne recherche
- DELETE /api/historique         → vide l'historique

La page web (static/app.js) appelle ces adresses et affiche les résultats.
Les fonctions OSINT sont exactement les mêmes que celles du serveur MCP.
"""

import tempfile
import webbrowser
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Timer
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..tools.breaches import email_breaches
from ..tools.domain import domain_lookup
from ..tools.email import email_lookup
from ..tools.email_accounts import email_accounts
from ..tools.image import image_metadata
from ..tools.ip import ip_lookup
from ..tools.subdomains import subdomain_search
from ..tools.username import username_search
from . import history

STATIC_DIR = Path(__file__).parent / "static"
MAX_IMAGE_SIZE = 25 * 1024 * 1024  # 25 Mo


@dataclass(frozen=True)
class WebTool:
    label: str
    description: str
    placeholder: str
    run: Callable[[str], Awaitable[dict[str, Any]]]
    categorie: str


# Les outils proposés dans la page. L'outil image est à part car il reçoit un fichier.
TOOLS: dict[str, WebTool] = {
    "recherche_domaine": WebTool(
        "Domaine", "DNS et WHOIS d'un nom de domaine", "exemple.fr", domain_lookup, "Domaine et réseau"
    ),
    "sous_domaines": WebTool(
        "Sous-domaines", "Sous-domaines trouvés dans les certificats HTTPS (crt.sh)",
        "exemple.fr", subdomain_search, "Domaine et réseau",
    ),
    "analyse_ip": WebTool(
        "Adresse IP", "Localisation, propriétaire, ports ouverts (Shodan)", "8.8.8.8",
        ip_lookup, "Domaine et réseau",
    ),
    "recherche_pseudo": WebTool(
        "Pseudo", "Comptes portant ce pseudo sur 16 sites", "pseudo", username_search, "Personne"
    ),
    "analyse_email": WebTool(
        "E-mail", "Fournisseur, adresse jetable, profil Gravatar", "nom@exemple.fr",
        email_lookup, "Personne",
    ),
    "comptes_email": WebTool(
        "Comptes d'un e-mail", "Sites où l'adresse a un compte (holehe, ~30 s)",
        "nom@exemple.fr", email_accounts, "Personne",
    ),
    "fuites_email": WebTool(
        "Fuites de données", "Fuites contenant l'adresse (Have I Been Pwned, clé requise)",
        "nom@exemple.fr", email_breaches, "Personne",
    ),
}

app = FastAPI(title="osint-mcp", description="Boîte à outils OSINT", docs_url="/api/docs")


class Query(BaseModel):
    valeur: str


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/outils")
async def list_tools() -> list[dict[str, str]]:
    tools = [
        {"id": tool_id, "label": t.label, "description": t.description,
         "placeholder": t.placeholder, "categorie": t.categorie, "type": "texte"}
        for tool_id, t in TOOLS.items()
    ]
    tools.append({
        "id": "metadonnees_image", "label": "Photo", "categorie": "Fichier", "type": "fichier",
        "description": "Métadonnées EXIF et position GPS d'une photo", "placeholder": "",
    })
    return tools


@app.post("/api/outils/{tool_id}")
async def run_tool(tool_id: str, query: Query) -> dict[str, Any]:
    tool = TOOLS.get(tool_id)
    if tool is None:
        raise HTTPException(404, f"Outil inconnu : {tool_id}")
    valeur = query.valeur.strip()
    try:
        result = await tool.run(valeur)
    except ValueError as exc:  # saisie invalide (domaine, e-mail, IP...)
        raise HTTPException(400, str(exc)) from None
    search_id = history.add(tool_id, valeur, result)
    return {"id": search_id, "outil": tool_id, "valeur": valeur, "resultat": result}


@app.post("/api/image")
async def analyse_image(fichier: UploadFile) -> dict[str, Any]:
    data = await fichier.read(MAX_IMAGE_SIZE + 1)
    if len(data) > MAX_IMAGE_SIZE:
        raise HTTPException(413, "Image trop lourde (25 Mo maximum).")
    name = Path(fichier.filename or "image").name
    # On écrit l'image dans un dossier temporaire, supprimé juste après l'analyse.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / name
        path.write_bytes(data)
        try:
            result = image_metadata(str(path))
        except Exception as exc:  # noqa: BLE001 - fichier qui n'est pas une image, etc.
            raise HTTPException(400, f"Impossible de lire cette image : {exc}") from None
    result["fichier"] = name  # on ne montre pas le chemin temporaire
    search_id = history.add("metadonnees_image", name, result)
    return {"id": search_id, "outil": "metadonnees_image", "valeur": name, "resultat": result}


@app.get("/api/historique")
async def get_history() -> list[dict[str, Any]]:
    return history.latest()


@app.get("/api/historique/{search_id}")
async def get_search(search_id: int) -> dict[str, Any]:
    item = history.get(search_id)
    if item is None:
        raise HTTPException(404, "Recherche introuvable")
    return item


@app.delete("/api/historique", status_code=204)
async def clear_history() -> None:
    history.clear()


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main() -> None:
    """Lance l'interface web (commande `osint-web`) et ouvre le navigateur."""
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Interface web de osint-mcp")
    parser.add_argument("--port", type=int, default=8000, help="port web (8000 par défaut)")
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="adresse d'écoute (127.0.0.1 par défaut ; 0.0.0.0 dans Docker)",
    )
    parser.add_argument("--sans-navigateur", action="store_true", help="ne pas ouvrir le navigateur")
    args = parser.parse_args()

    url = f"http://127.0.0.1:{args.port}"
    print(f"Interface OSINT disponible sur {url}  (Ctrl+C pour arrêter)")
    if not args.sans_navigateur:
        Timer(1.5, webbrowser.open, args=[url]).start()
    # 127.0.0.1 = accessible uniquement depuis ton ordinateur, pas depuis le réseau.
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
