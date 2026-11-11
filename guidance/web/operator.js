import { byId as $, sessionToken, apiClient, clock, pollEvery } from "./common.js";

// Guidance suggestions are optional and never send messages automatically.
// Provenance describes the operator's use of a draft, not its pedagogical quality.
let selectedIdea = null;
for (const button of document.querySelectorAll(".use-idea")) {
    button.addEventListener("click", () => {
        const field = $("text");
        const suggestion = button.dataset.idea;
        if (field.value.trim() && field.value.trim() !== suggestion &&
            !window.confirm("Remplacer le brouillon actuel par cette suggestion ?")) return;
        selectedIdea = { id: button.dataset.ideaId, original: suggestion };
        field.value = suggestion;
        field.dispatchEvent(new Event("input", { bubbles: true }));
        field.focus();
        field.setSelectionRange(field.value.length, field.value.length);
        $("idea-copy-status").textContent = "Brouillon inséré : adaptez-le librement avant l’envoi.";
    });
}

const token = sessionToken("operator");
const api = apiClient(token);
const sendButtons = document.querySelectorAll("#compose button[type=submit]");
let state;
let pending;
let sending = false;
let revision;

function updateButtons() {
    for (const button of sendButtons) button.disabled = sending || !state?.active;
}

function renderHistory(messages) {
    $("history").replaceChildren();
    if (!messages.length) $("history").textContent = "Aucune guidance envoyée.";
    for (const message of [...messages].reverse()) {
        const item = document.createElement("div");
        item.className = "message";
        const time = document.createElement("small");
        time.textContent = [clock(message.sent_utc), message.priority ? "Prioritaire" : "Sans son"].join(" · ");
        const text = document.createElement("p");
        text.textContent = message.text;
        const status = document.createElement("div");
        status.className = "status";
        status.textContent = message.deliveries.length
            ? `Affiché à ${clock(message.deliveries[0].displayed_utc)}`
            : "En attente de confirmation d’affichage";
        item.append(time, text, status);
        if (message.operator_note) {
            const note = document.createElement("p");
            note.className = "muted";
            note.textContent = `Votre note · ${message.operator_note}`;
            item.append(note);
        }
        $("history").append(item);
    }
}

async function update() {
    try {
        state = await (await api("/api/operator")).json();
        $("session").textContent = `Groupe ${state.group} · Session ${state.session_id}`;
        $("connection").textContent = state.active ? `Écrans connectés · ${state.online_clients}` : "Session terminée";
        $("link").textContent = state.student_url;
        $("backup").textContent = state.csv_saved ? "Récapitulatif enregistré sur le Mac hôte."
            : "Mise à jour du CSV impossible. Le journal des messages reste disponible.";
        const nextRevision = JSON.stringify(state.messages);
        if (nextRevision !== revision) {
            renderHistory(state.messages);
            revision = nextRevision;
        }
    } catch (error) {
        state = undefined;
        $("connection").textContent = error.message;
    }
    updateButtons();
}

function updateLength() {
    $("length").textContent = `${$("text").value.length} / 2000`;
}

$("text").addEventListener("input", () => {
    updateLength();
    // Deleting a suggestion completely returns the message to free composition.
    if (!$("text").value.trim()) selectedIdea = null;
});
$("compose").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (sending || !state?.active) return;
    const text = $("text").value.trim();
    if (!pending && !text) return;
    pending ??= {
        request_id: crypto.randomUUID(),
        text,
        category: "unspecified",
        operator_note: $("note").value.trim(),
        guidance_source: selectedIdea ? "suggestion" : "free",
        suggestion_id: selectedIdea?.id ?? "",
        suggestion_edited: selectedIdea ? text !== selectedIdea.original : false,
        priority: event.submitter?.value === "priority",
    };
    sending = true;
    for (const id of ["text", "note"]) $(id).disabled = true;
    updateButtons();
    $("notice").textContent = "Envoi…";
    try {
        await api("/api/send", pending);
        pending = undefined;
        selectedIdea = null;
        $("text").value = "";
        $("note").value = "";
        updateLength();
        $("notice").textContent = "Message enregistré et envoyé.";
    } catch (error) {
        $("notice").textContent = `${error.message} Cliquez de nouveau pour réessayer le même envoi.`;
    } finally {
        sending = false;
        for (const id of ["text", "note"]) $(id).disabled = Boolean(pending);
        updateButtons();
    }
});

$("copy").onclick = async () => {
    if (!state) return;
    try {
        await navigator.clipboard.writeText(state.student_url);
        $("notice").textContent = "Lien copié.";
    } catch {
        $("notice").textContent = "Sélectionnez et copiez le lien affiché.";
    }
};
$("preview").onclick = () => {
    if (state) window.open(state.student_url, "_blank", "noopener");
};
$("export").onclick = async () => {
    try {
        const response = await api("/api/export");
        const url = URL.createObjectURL(await response.blob());
        const link = document.createElement("a");
        link.href = url;
        link.download = "guidance_recap.csv";
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
        $("notice").textContent = error.message;
    }
};

if (token) pollEvery(update);
else $("connection").textContent = "Ouvrez le lien privé de l’opérateur.";

// DBAG_PANEL_EQUAL_HEIGHT: keep ideas scrollable beside the editor.
const editorPanel = document.querySelector('.operator-guidance-layout > section.card');
const ideasPanel = document.getElementById('guidance-ideas');
if (editorPanel && ideasPanel) {
    const syncIdeasHeight = () => {
        ideasPanel.style.height = `${editorPanel.getBoundingClientRect().height}px`;
    };
    new ResizeObserver(syncIdeasHeight).observe(editorPanel);
    syncIdeasHeight();
}
