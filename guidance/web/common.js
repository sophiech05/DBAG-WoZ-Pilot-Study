export const byId = (id) => document.getElementById(id);

export function sessionToken(role) {
    const key = `guidance-${role}-token`;
    const token = new URLSearchParams(location.hash.slice(1)).get("token");
    if (token) {
        sessionStorage.setItem(key, token);
        history.replaceState(null, "", location.pathname);
    }
    return sessionStorage.getItem(key);
}

export function apiClient(token) {
    return async (path, data) => {
        const headers = { Authorization: `Bearer ${token}` };
        const options = { headers, cache: "no-store", signal: AbortSignal.timeout(8000) };
        if (data !== undefined) {
            headers["Content-Type"] = "application/json";
            options.method = "POST";
            options.body = JSON.stringify(data);
        }
        const response = await fetch(path, options);
        if (response.status === 403) throw new Error("Ouvrez le lien privé de votre session.");
        if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            throw new Error(payload.error || "Connexion interrompue.");
        }
        return response;
    };
}

export function clock(timestamp) {
    return new Date(timestamp).toLocaleTimeString("fr-CH");
}

export async function pollEvery(update) {
    try {
        await update();
    } finally {
        setTimeout(() => pollEvery(update), 750);
    }
}
