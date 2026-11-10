import { byId as $, sessionToken, apiClient, clock, pollEvery } from "./common.js";

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
        const category = [...$("category").options].find((option) => option.value === message.category);
        time.textContent = [clock(message.sent_utc), category?.text, message.priority ? "Prioritaire" : "Sans son"].join(" · ");
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

$("text").addEventListener("input", updateLength);
$("compose").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (sending || !state?.active) return;
    const text = $("text").value.trim();
    if (!pending && !text) return;
    pending ??= {
        request_id: crypto.randomUUID(),
        text,
        category: $("category").value,
        operator_note: $("note").value.trim(),
        priority: event.submitter?.value === "priority",
    };
    sending = true;
    for (const id of ["text", "note", "category"]) $(id).disabled = true;
    updateButtons();
    $("notice").textContent = "Envoi…";
    try {
        await api("/api/send", pending);
        pending = undefined;
        $("text").value = "";
        $("note").value = "";
        updateLength();
        $("notice").textContent = "Message enregistré et envoyé.";
    } catch (error) {
        $("notice").textContent = `${error.message} Cliquez de nouveau pour réessayer le même envoi.`;
    } finally {
        sending = false;
        for (const id of ["text", "note", "category"]) $(id).disabled = Boolean(pending);
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
