// Le JavaScript de la page : il appelle l'API (app.py) et affiche les résultats.
//
// Sécurité : les résultats viennent de sites externes et peuvent contenir du
// texte piégé. On construit donc toujours la page avec createElement et
// textContent, jamais avec innerHTML, pour éviter d'exécuter du code
// injecté (faille XSS).

const state = { tools: [], current: null, lastResult: null };
const $ = (id) => document.getElementById(id);

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "text") node.textContent = value;
    else if (key === "class") node.className = value;
    else node.setAttribute(key, value);
  }
  for (const child of [].concat(children)) if (child) node.append(child);
  return node;
}

// ---------- Appels à l'API ----------

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Erreur HTTP ${response.status}`);
  return data;
}

// ---------- Affichage d'un résultat ----------

const isUrl = (v) => typeof v === "string" && /^https?:\/\/\S+$/.test(v);
const humanize = (key) => {
  const text = key.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
};

function render(value) {
  if (value === null || value === undefined || value === "") return el("span", { class: "empty", text: "—" });
  if (typeof value === "boolean") {
    return el("span", { class: `badge ${value ? "yes" : "no"}`, text: value ? "Oui" : "Non" });
  }
  if (isUrl(value)) {
    const text = value.length > 70 ? `${value.slice(0, 67)}…` : value;
    return el("a", { href: value, target: "_blank", rel: "noopener noreferrer", title: value, text });
  }
  if (typeof value !== "object") return document.createTextNode(String(value));

  if (Array.isArray(value)) {
    if (value.length === 0) return el("span", { class: "empty", text: "aucun" });
    const simple = value.every((v) => v === null || typeof v !== "object");
    if (simple) return el("ul", { class: "chips" }, value.map((v) => el("li", {}, render(v))));
    return el("ul", { class: "cards" }, value.map((v) => el("li", {}, render(v))));
  }

  const rows = Object.entries(value).map(([key, v]) =>
    el("tr", {}, [el("th", { text: humanize(key), scope: "row" }), el("td", {}, render(v))])
  );
  return el("table", { class: "kv" }, el("tbody", {}, rows));
}

function showResult(title, result) {
  state.lastResult = result;
  $("result-panel").hidden = false;
  $("result-title").textContent = title;
  $("result").replaceChildren(render(result));
  $("raw").textContent = JSON.stringify(result, null, 2);
}

function showLoading(message) {
  $("result-panel").hidden = false;
  $("result-title").textContent = "Recherche en cours…";
  $("result").replaceChildren(el("div", { class: "loading" }, [el("span", { class: "spinner" }), message]));
}

function showError(message) {
  $("result-panel").hidden = false;
  $("result-title").textContent = "Erreur";
  $("result").replaceChildren(el("div", { class: "error", text: message }));
  $("raw").textContent = "";
}

// ---------- Choix de l'outil ----------

function selectTool(id) {
  const tool = state.tools.find((t) => t.id === id);
  if (!tool) return;
  state.current = tool;
  document.querySelectorAll(".tool-button").forEach((b) => {
    b.setAttribute("aria-current", String(b.dataset.id === id));
  });
  $("tool-title").textContent = tool.label;
  $("tool-description").textContent = tool.description;
  const isFile = tool.type === "fichier";
  $("text-form").hidden = isFile;
  $("file-form").hidden = !isFile;
  if (!isFile) {
    $("text-input").placeholder = tool.placeholder;
    $("text-input").focus();
  }
  try { localStorage.setItem("outil", id); } catch { /* stockage indisponible */ }
}

function renderToolList() {
  const groups = {};
  for (const tool of state.tools) (groups[tool.categorie] ||= []).push(tool);
  const container = el("div", { class: "tool-list-inner" });
  for (const [name, tools] of Object.entries(groups)) {
    const buttons = tools.map((t) =>
      el("button", { type: "button", class: "tool-button", "data-id": t.id, title: t.description, text: t.label })
    );
    container.append(el("div", { class: "tool-group" }, [el("h3", { text: name }), ...buttons]));
  }
  container.addEventListener("click", (event) => {
    const button = event.target.closest(".tool-button");
    if (button) selectTool(button.dataset.id);
  });
  $("tool-list").replaceChildren(container);
}

// ---------- Historique ----------

const labelOf = (id) => state.tools.find((t) => t.id === id)?.label || id;

async function refreshHistory() {
  const items = await api("/api/historique");
  const list = $("history-list");
  if (items.length === 0) {
    list.replaceChildren(el("li", { class: "empty", text: "Aucune recherche pour l'instant." }));
    return;
  }
  list.replaceChildren(...items.map((item) => {
    const date = new Date(item.date).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
    const button = el("button", { type: "button" }, [
      el("span", { class: "h-value", text: item.valeur }),
      el("span", { class: "h-meta", text: `${labelOf(item.outil)} · ${date}` }),
    ]);
    button.addEventListener("click", async () => {
      const search = await api(`/api/historique/${item.id}`);
      showResult(`${labelOf(search.outil)} : ${search.valeur}`, search.resultat);
    });
    return el("li", {}, button);
  }));
}

// ---------- Lancement d'une recherche ----------

async function runSearch(button, doRequest, label) {
  button.disabled = true;
  showLoading(`${state.current.label} : ${label}`);
  try {
    const data = await doRequest();
    showResult(`${state.current.label} : ${data.valeur}`, data.resultat);
    refreshHistory();
  } catch (error) {
    showError(error.message);
  } finally {
    button.disabled = false;
  }
}

$("text-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const valeur = $("text-input").value.trim();
  if (!valeur || !state.current) return;
  runSearch($("text-submit"), () => api(`/api/outils/${state.current.id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ valeur }),
  }), valeur);
});

$("file-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const file = $("file-input").files[0];
  if (!file) return;
  const form = new FormData();
  form.append("fichier", file);
  runSearch($("file-submit"), () => api("/api/image", { method: "POST", body: form }), file.name);
});

$("file-input").addEventListener("change", () => {
  const file = $("file-input").files[0];
  $("file-label").textContent = file ? file.name : "Choisis une photo ou glisse-la ici";
});

// Glisser-déposer d'une photo
const drop = $("file-drop");
["dragenter", "dragover"].forEach((type) => drop.addEventListener(type, (e) => {
  e.preventDefault();
  drop.classList.add("dragging");
}));
["dragleave", "drop"].forEach((type) => drop.addEventListener(type, () => drop.classList.remove("dragging")));
drop.addEventListener("drop", (e) => {
  e.preventDefault();
  if (e.dataTransfer.files.length) {
    $("file-input").files = e.dataTransfer.files;
    $("file-input").dispatchEvent(new Event("change"));
  }
});

$("toggle-raw").addEventListener("click", () => {
  const raw = $("raw");
  raw.hidden = !raw.hidden;
  $("result").hidden = !raw.hidden;
  $("toggle-raw").textContent = raw.hidden ? "JSON brut" : "Vue lisible";
});

$("copy-raw").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("raw").textContent);
    $("copy-raw").textContent = "Copié !";
  } catch {
    $("copy-raw").textContent = "Échec";
  }
  setTimeout(() => { $("copy-raw").textContent = "Copier"; }, 1500);
});

$("clear-history").addEventListener("click", async () => {
  await api("/api/historique", { method: "DELETE" });
  refreshHistory();
});

// ---------- Démarrage ----------

(async function init() {
  try {
    state.tools = await api("/api/outils");
  } catch (error) {
    showError(`Impossible de joindre le serveur : ${error.message}`);
    return;
  }
  renderToolList();
  let saved = null;
  try { saved = localStorage.getItem("outil"); } catch { /* stockage indisponible */ }
  selectTool(state.tools.some((t) => t.id === saved) ? saved : state.tools[0].id);
  refreshHistory();
})();
