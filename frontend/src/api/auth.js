/**
 * Auth API — Pizzería 220 AI
 * 
 * Funciones de autenticación usando el cliente HTTP con cookies HttpOnly.
 * 
 * Flujo:
 * 1. login() → Backend setea cookies HttpOnly (access_token + refresh_token)
 * 2. register() → Registro de nuevo usuario
 * 3. getCurrentUser() → Obtiene datos del usuario autenticado
 * 4. logout() → Backend elimina cookies y revoca tokens
 */

import { login as apiLogin, register as apiRegister, getMe, logout as apiLogout } from "./client";
import {
  clearSession,
  saveSession,
} from "../utils/session";

export async function login(gmail, password) {
  const data = await apiLogin(gmail, password);

  // Guardar solo metadata del usuario (NO el token, está en cookie HttpOnly)
  saveSession({
    accessToken: data.access_token || data.token,
    user: data.user || { nombre: data.nombre, gmail, role: "cliente" },
  });

  return data.user || data;
}

export async function register(form) {
  return apiRegister({
    nombre: form.nombre.trim(),
    telefono: form.telefono.trim(),
    gmail: form.gmail.trim(),
    direccion: form.direccion.trim(),
    password: form.password,
  });
}

export async function getCurrentUser() {
  try {
    const data = await getMe();
    return data;
  } catch {
    return null;
  }
}

export async function logout() {
  try {
    await apiLogout();
  } finally {
    clearSession();
  }
}