const ACCESS_TOKEN_KEY = "p220_access_token";
const USER_KEY = "p220_user";

export function saveSession({ accessToken, user }) {
  if (!accessToken || typeof accessToken !== "string") {
    throw new Error("El servidor no devolvió un token válido.");
  }

  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(USER_KEY, JSON.stringify(user ?? null));
}

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getStoredUser() {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw);
  } catch {
    clearSession();
    return null;
  }
}

export function clearSession() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function hasSession() {
  return Boolean(getAccessToken());
}
