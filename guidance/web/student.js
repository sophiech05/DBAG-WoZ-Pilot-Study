import { byId as $, sessionToken, apiClient, clock, pollEvery } from "./common.js";

const token = sessionToken("student");
const api = apiClient(token);
const clientKey = "guidance-client";
const clientId = sessionStorage.getItem(clientKey) || crypto.randomUUID();
sessionStorage.setItem(clientKey, clientId);
const displayed = new Set();
const chimes = new Set();
let audio;
let newestId;

async function startAudio() {
    audio ??= new AudioContext();
    if (audio.state !== "running") await audio.resume();
}

function unlockAudio() {
    if (audio?.state !== "running") startAudio().catch(() => {});
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

function render(messages) {
    const newest = messages.at(-1);
    if (!newest || newestId === newest.id) return;
    newestId = newest.id;
    $("latest").textContent = newest.text;
    $("time").textContent = `Guidance reçue à ${clock(newest.sent_utc)}`;
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
        item.append(time, text);
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
        for (const message of state.messages) {
            if (message.priority && !chimes.has(message.id) && audio?.state === "running") chime();
            chimes.add(message.id);
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
    document.addEventListener("click", unlockAudio);
    document.addEventListener("keydown", unlockAudio);
    pollEvery(update);
} else {
    $("connection").textContent = "Ouvrez le lien privé du groupe.";
}
