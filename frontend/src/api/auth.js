import client from "./axiosClient";
import { sha256 } from "../utils/crypto";

/**
 * Iniciar sesión
 * @param {string} gmail
 * @param {string} password
 * @returns {Promise<{success:boolean,user?:object,message?:string}>}
 */
export async function login(gmail, password) {
  try {
    const email = gmail.trim().toLowerCase();
    const hash = await sha256(password);

    console.log("Login email:", email);
    console.log("Login hash:", hash);

    const { data } = await client.post("/auth/login", {
      gmail: email,
      password: hash,
    });

    return data;
  } catch (error) {
    console.error(
      "Error login:",
      error?.response?.data || error?.message || error
    );

    // Mantiene la causa original para ESLint
    throw new Error(
      error?.response?.data?.message || "Error al iniciar sesión",
      { cause: error }
    );
  }
}

/**
 * Registrar usuario
 * @param {Object} fields
 * @returns {Promise<{success:boolean,user?:object,message?:string}>}
 */
export async function register(fields) {
  try {
    const hash = await sha256(fields.password);

    const payload = {
      ...fields,
      gmail: fields.gmail.trim().toLowerCase(),
      password: hash,
    };

    const { data } = await client.post("/auth/register", payload);

    return data;
  } catch (error) {
    console.error(
      "Error registro:",
      error?.response?.data || error?.message || error
    );

    throw new Error(
      error?.response?.data?.message || "Error al registrar usuario",
      { cause: error }
    );
  }
}

/**
 * Cerrar sesión
 */
export async function logout() {
  try {
    await client.post("/auth/logout");
  } catch (error) {
    console.error(
      "Error logout:",
      error?.response?.data || error?.message || error
    );

    throw new Error(
      error?.response?.data?.message || "Error al cerrar sesión",
      { cause: error }
    );
  }
}