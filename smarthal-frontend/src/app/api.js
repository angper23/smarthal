// Thin wrapper around fetch for talking to the Flask backend
// Adds the login token to every request, and if the backend ever answers
// 401 to a request that carried a token (expired, logged out elsewhere,
// backend restarted), tells AuthContext to drop the session — which sends
// the user back to /login via the route guard
export const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;

// Set by AuthContext. Kept here (not read from React state) so every
// request uses the current token without each screen passing it around
let currentToken = null;
let handleUnauthorized = () => {};

/** Set the token apiFetch attaches to requests (null = logged out). Called by AuthContext. */
export function setApiToken(token) {
  currentToken = token;
}

/** Register what happens when the backend answers 401. AuthContext passes its logout-cleanup. */
export function onUnauthorized(handler) {
  handleUnauthorized = handler;
}

// Thrown when the backend can't be reached at all (not running, wrong URL,
// network down) — lets screens show "can't reach the server" instead of
// treating it like a rejected request
export class NetworkError extends Error {
  constructor() {
    super("Can't reach the server");
    this.name = "NetworkError";
  }
}

/**
 * Call the backend, e.g. apiFetch("/status") or apiFetch("/login", { method: "POST", body: {...} }).
 * Adds the login token, sends body as JSON (or as-is if it's FormData, e.g. photo uploads),
 * and returns the normal fetch Response.
 * Throws NetworkError if the backend can't be reached at all.
 */
export async function apiFetch(path, { method = "GET", body, signal } = {}) {
  const headers = {};
  // FormData sets its own multipart Content-Type (with the boundary), so leave it alone
  const isForm = body instanceof FormData;
  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  const sentToken = currentToken;
  if (sentToken) headers.Authorization = `Bearer ${sentToken}`;

  let res;
  try {
    res = await fetch(`${BACKEND_URL}${path}`, {
      method,
      headers,
      body: body === undefined || isForm ? body : JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new NetworkError();
  }

  // Only a request that actually sent a token can mean "your session is
  // gone" — a 401 from /login just means wrong credentials
  if (res.status === 401 && sentToken && sentToken === currentToken) {
    handleUnauthorized();
  }
  return res;
}
