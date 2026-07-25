import { apiRequest } from "./client";
import {
  clearSession,
  saveSession,
} from "../utils/session";

export async function login(gmail, password) {
  const data = await apiRequest("/auth/login", {
    method: "POST",
    authenticated: false,
    body: {
      gmail: gmail.trim(),
      password,
    },
  });

  saveSession({
    accessToken: data.access_token,
    user: data.user,
  });

  return data.user;
}

export async function register(form) {
  return apiRequest("/auth/register", {
    method: "POST",
    authenticated: false,
    body: {
      nombre: form.nombre.trim(),
      telefono: form.telefono.trim(),
      gmail: form.gmail.trim(),
      direccion: form.direccion.trim(),
      password: form.password,
    },
  });
}

export async function getCurrentUser() {
  return apiRequest("/auth/me");
}

export async function logout() {
  try {
    await apiRequest("/auth/logout", {
      method: "POST",
      body: {},
    });
  } finally {
    clearSession();
  }
}
