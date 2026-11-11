import { byId as $, sessionToken, apiClient, clock, pollEvery } from "./common.js";

const token = sessionToken("student");
const api = apiClient(token);
const clientKey = "guidance-client";
const clientId = sessionStorage.getItem(clientKey) || crypto.randomUUID();
sessionStorage.setItem(clientKey, clientId);
const displayed = new Set();
const chimes = new Set();
const queuedPriority = new Set();
let initialMessagesLoaded = false;
let audio;
let newestId;

async function startAudio() {
    audio ??= new AudioContext();
    if (audio.state !== "running") await audio.resume();
    if (audio.state === "running") playPendingNotifications();
}

function unlockAudio() {
    if (audio?.state !== "running") startAudio().catch(() => {});
    else playPendingNotifications();
}

function playPendingNotifications() {
    if (audio?.state !== "running" || !queuedPriority.size) return;
    // A single chime signals outstanding priority guidance without a burst of tones.
    chime();
    for (const id of queuedPriority) chimes.add(id);
    queuedPriority.clear();
}

$("sound").onclick = async () => {
    try {
        await startAudio();
        chime();
    } catch (error) {
        console.error("Impossible de jouer le son de test.", error);
    }
};

function chime() {
    const tone = audio.createOscillator();
    const gain = audio.createGain();
    const now = audio.currentTime;
    tone.frequency.value = 660;
    gain.gain.setValueAtTime(0.12, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
    tone.connect(gain).connect(audio.destination);
    tone.start(now);
    tone.stop(now + 0.25);
}

// Student-side priority indicator (independent of browser audio permissions).
function priorityLabel(priority) {
    const label = document.createElement("span");
    label.className = "guidance-priority-label";
    label.textContent = priority ? "Prioritaire" : "Non prioritaire";
    label.style.cssText = priority
        ? "display:inline-block;margin-left:10px;padding:4px 9px;border-radius:999px;background:#f8dfdf;color:#762b2b;font-size:12px;font-weight:700;vertical-align:middle;"
        : "display:inline-block;margin-left:10px;padding:4px 9px;border-radius:999px;background:#d9efdf;color:#185331;font-size:12px;font-weight:700;vertical-align:middle;";
    return label;
}

function render(messages) {
    const newest = messages.at(-1);
    if (!newest || newestId === newest.id) return;
    newestId = newest.id;
    $("latest").textContent = newest.text;
    $("time").textContent = `Guidance reçue à ${clock(newest.sent_utc)}`;
    $("card").querySelector(".guidance-priority-label")?.remove();
    $("time").after(priorityLabel(newest.priority));
    $("card").classList.remove("new");
    void $("card").offsetWidth;
    $("card").classList.add("new");
    $("history").replaceChildren();
    if (messages.length === 1) $("history").textContent = "Aucun message précédent.";
    for (const message of messages.slice(0, -1).reverse()) {
        const item = document.createElement("div");
        item.className = "message";
        const time = document.createElement("small");
        time.textContent = clock(message.sent_utc);
        const text = document.createElement("p");
        text.textContent = message.text;
        item.append(time, priorityLabel(message.priority), text);
        $("history").append(item);
    }
}

async function update() {
    try {
        const response = await api(`/api/student?client_id=${encodeURIComponent(clientId)}`);
        const state = await response.json();
        $("connection").textContent = state.active ? `Groupe ${state.group} · Connecté` : "Session terminée";
        render(state.messages);
        const newest = state.messages.at(-1);
        if (!initialMessagesLoaded) {
            // Do not play notifications for messages that predate opening this page.
            for (const message of state.messages) chimes.add(message.id);
            initialMessagesLoaded = true;
        } else {
            for (const message of state.messages) {
                if (!message.priority || chimes.has(message.id) || queuedPriority.has(message.id)) continue;
                queuedPriority.add(message.id);
            }
            playPendingNotifications();
        }
        if (!newest || displayed.has(newest.id) || document.hidden) return;
        await new Promise((resolve) => requestAnimationFrame(() => setTimeout(resolve, 0)));
        if (document.hidden) return;
        await api("/api/displayed", { client_id: clientId, message_id: newest.id });
        displayed.add(newest.id);
    } catch (error) {
        $("connection").textContent = error.message;
    }
}

if (token) {
    unlockAudio();
    document.addEventListener("pointerdown", unlockAudio, { capture: true });
    document.addEventListener("keydown", unlockAudio, { capture: true });
    pollEvery(update);
} else {
    $("connection").textContent = "Ouvrez le lien privé du groupe.";
}
