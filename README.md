# osint-mcp

Une boîte à outils **OSINT** (renseignement en sources ouvertes) exposée via un
serveur **MCP**, pour apprendre l'investigation en ligne avec Claude.

Une fois branché à Claude Desktop, tu peux simplement demander :

> « Que peux-tu me dire sur le domaine exemple.fr ? »
> « Cherche les comptes associés au pseudo snooze561. »
> « Analyse les métadonnées de la photo C:/Users/moi/Images/vacances.jpg. »

et Claude appelle tout seul le bon outil.

> ⚖️ **Usage responsable.** N'utilise ces outils que sur toi-même, sur des
> personnes ou organisations qui ont donné leur accord, ou dans un cadre
> autorisé (CTF, audit, exercice). En France, collecter des données
> personnelles sur quelqu'un à son insu peut tomber sous le coup du RGPD et du
> Code pénal.

## Les outils

| Outil MCP | Ce qu'il fait | Clé API |
|---|---|---|
| `recherche_domaine` | Enregistrements DNS (A, AAAA, MX, NS, TXT, SOA) et WHOIS (registrar, dates, organisation) | Non |
| `recherche_pseudo` | Cherche un pseudo sur 16 sites (GitHub, GitLab, Reddit, Telegram, Steam, Bluesky, Mastodon, Chess.com...) | Non |
| `analyse_email` | Serveurs MX, fournisseur de messagerie, adresse jetable, profil Gravatar public | Non |
| `metadonnees_image` | Métadonnées EXIF d'une photo : appareil, date, logiciel, **coordonnées GPS** | Non |

## Installation

Il te faut **Git** et **[uv](https://docs.astral.sh/uv/)**, un gestionnaire de
projets Python moderne et rapide. Pas besoin d'installer Python toi-même :
uv le télécharge si nécessaire.

### Windows (PowerShell)

```powershell
# 1. Installer Git et uv (une seule fois), puis fermer et rouvrir PowerShell
winget install --id Git.Git -e
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Récupérer le projet
cd $HOME
git clone https://github.com/Snooze561/osint-mcp.git
cd osint-mcp

# 3. Installer les dépendances (uv crée l'environnement virtuel tout seul)
uv sync --extra dev

# 4. Vérifier que tout marche
uv run pytest
```

Si `winget` n'est pas disponible, installe Git depuis https://git-scm.com/download/win.

### macOS / Linux

```bash
# 1. Installer uv (une seule fois). Git est souvent déjà installé (commande `git --version`).
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2 à 4 : identiques
git clone https://github.com/Snooze561/osint-mcp.git
cd osint-mcp
uv sync --extra dev
uv run pytest
```

## Brancher le serveur sur Claude Desktop

1. Ouvre Claude Desktop, puis **Paramètres → Développeur → Modifier la config**.
   Cela ouvre le fichier `claude_desktop_config.json`.
2. Ajoute le serveur (remplace le chemin par celui de ton dossier `osint-mcp`) :

```json
{
  "mcpServers": {
    "osint": {
      "command": "uv",
      "args": ["--directory", "C:/chemin/vers/osint-mcp", "run", "osint-mcp"]
    }
  }
}
```

3. Redémarre Claude Desktop. Les 4 outils apparaissent dans le menu des outils
   (icône de prise ou de marteau) de la zone de saisie.

> Astuce : si Claude Desktop ne trouve pas `uv`, remplace `"uv"` par son chemin
> complet (commande `where uv` sous Windows, `which uv` sous macOS/Linux).

### Tester sans Claude : l'inspecteur MCP

L'inspecteur officiel ouvre une page web où l'on peut appeler chaque outil à la main
(il faut [Node.js](https://nodejs.org)) :

```bash
npx @modelcontextprotocol/inspector uv run osint-mcp
```

## Comment c'est organisé

```
src/osint_mcp/
├── server.py           ← le serveur MCP : déclare les 4 outils pour Claude
└── tools/              ← la logique OSINT, en Python "normal" (sans MCP)
    ├── domain.py       ← DNS + WHOIS
    ├── username.py     ← recherche de pseudo (liste des sites + règles)
    ├── email.py        ← MX, fournisseur, jetable, Gravatar
    ├── image.py        ← EXIF et GPS
    └── validation.py   ← nettoyage des domaines et e-mails saisis
tests/                  ← tests automatiques (aucun accès réseau réel)
```

Pourquoi séparer `server.py` et `tools/` ? Parce que les fonctions de `tools/`
ne dépendent pas de MCP : la future interface web pourra les réutiliser telles
quelles.

### Ce qu'il faut retenir sur MCP

- Un **serveur MCP** est un programme qui propose des **outils** à une IA.
- Chaque fonction décorée par `@mcp.tool()` devient un outil. Ses **paramètres
  typés** deviennent le schéma d'entrée, et sa **docstring** devient la
  description que Claude lit pour décider quand l'utiliser.
- Ici le serveur parle en **stdio** : Claude Desktop le lance comme un
  programme et échange des messages JSON par l'entrée et la sortie standard.

### Exercice : ajouter un site à la recherche de pseudo

Ouvre `src/osint_mcp/tools/username.py` et regarde la liste `SITES`. Pour
ajouter un site, il faut trouver une adresse dont la réponse change selon que
le compte existe ou non :

1. Ouvre le profil d'un compte qui existe, puis celui d'un pseudo inventé.
2. Compare : code HTTP différent (200 / 404) ? Texte « introuvable » dans la page ?
3. Ajoute une ligne, par exemple :
   `Site("MonSite", "https://monsite.com/{}")`
   ou, si la page répond toujours 200 :
   `Site("MonSite", "https://monsite.com/{}", text_means_absent("Page introuvable"))`

## Feuille de route

- [x] **Étape 1** : serveur MCP avec 4 outils sans clé API
- [ ] **Étape 2** : plus d'outils (sous-domaines via crt.sh, géolocalisation d'IP,
      theHarvester, holehe, Shodan et Have I Been Pwned avec clés API dans `.env`)
- [ ] **Étape 3** : interface web locale (FastAPI)
- [ ] **Étape 4** : image Docker pour tout lancer en une commande

## Limites connues

- Certains sites (Instagram, X, TikTok, LinkedIn, Facebook) bloquent les
  vérifications automatiques : ils ne sont pas dans la liste.
- Un site peut changer son fonctionnement du jour au lendemain : un résultat
  « incertain » signifie souvent qu'il bloque les requêtes ou qu'une règle est
  à mettre à jour.
- Le WHOIS des domaines en `.fr` et de beaucoup de particuliers est anonymisé (RGPD).
