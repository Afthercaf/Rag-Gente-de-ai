/**
 * Auth API — Pizzería 220 AI
 *
 * Responsabilidades:
 * - iniciar sesión;
 * - registrar usuarios;
 * - consultar el usuario actual;
 * - cerrar sesión;
 * - guardar el access token en sessionStorage.
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
 * Inicia sesión y guarda el access token.
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

  const accessToken =
    data?.access_token ||
    data?.token;

  if (!accessToken) {
    throw new Error(
      "El servidor no devolvió un access token.",
    );
  }

  const user =
    data?.user || {
      nombre:
        data?.nombre || "",

      gmail:
        normalizedGmail,

      telefono:
        data?.telefono || "",

      direccion:
        data?.direccion || "",

      role:
        data?.role ||
        "cliente",
    };

  saveSession({
    accessToken,
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