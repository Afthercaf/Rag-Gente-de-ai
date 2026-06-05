/**
 * Genera un hash SHA-256 del texto dado (igual que el backend).
 * @param {string} text
 * @returns {Promise<string>} hex string
 */
export async function sha256(text) {
  const buf = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(text)
  );
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
