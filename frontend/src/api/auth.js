/**
 * Auth API — Pizzería 220 AI
 *
 * Responsabilidades:
 * - iniciar sesión;
 * - registrar usuarios;
 * - consultar el usuario actual;
 * - cerrar sesión;
 * - guardar datos básicos del usuario en sessionStorage.
 *
 * ✅ M-01 FIX: El access token viaja en cookie HttpOnly (nombre según ENV),
 * no en sessionStorage.
 */

import {
  getMe,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
} from "./client";

import {
  clearSession,
  saveSession,
} from "../utils/session";

/**
 * Inicia sesión y guarda los datos básicos del usuario.
 */
export async function login(
  gmail,
  password,
) {
  const normalizedGmail =
    String(
      gmail || "",
    )
      .trim()
      .toLowerCase();

  const normalizedPassword =
    String(
      password || "",
    );

  if (!normalizedGmail) {
    throw new Error(
      "El correo electrónico es requerido.",
    );
  }

  if (!normalizedPassword) {
    throw new Error(
      "La contraseña es requerida.",
    );
  }

  const data =
    await apiLogin(
      normalizedGmail,
      normalizedPassword,
    );

  // ✅ M-01 FIX: El access token se recibe en cookie HttpOnly.
  const user =
    data?.user || {
      role:
        data?.role ||
        "cliente",
    };

  saveSession({
    user,
  });

  return user;
}

/**
 * Registra una nueva cuenta.
 */
export async function register(
  form,
) {
  const payload = {
    nombre:
      String(
        form?.nombre || "",
      ).trim(),

    telefono:
      String(
        form?.telefono || "",
      ).trim(),

    gmail:
      String(
        form?.gmail || "",
      )
        .trim()
        .toLowerCase(),

    direccion:
      String(
        form?.direccion || "",
      ).trim(),

    password:
      String(
        form?.password || "",
      ),
  };

  return apiRegister(
    payload,
  );
}

/**
 * Consulta el usuario autenticado.
 *
 * Si falla, devuelve null y deja que la aplicación
 * decida si muestra login.
 */
export async function getCurrentUser() {
  try {
    return await getMe();
  } catch {
    return null;
  }
}

/**
 * Cierra la sesión del backend y limpia sessionStorage.
 */
export async function logout() {
  try {
    await apiLogout();
  } finally {
    clearSession();
  }
}