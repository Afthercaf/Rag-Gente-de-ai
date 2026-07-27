import {
  getVoiceHistory as apiGetVoiceHistory,
  transcribeAudio as apiTranscribeAudio,
} from "./client";

/**
 * Transcribe un audio usando el cliente HTTP central.
 *
 * El backend obtiene el usuario desde la cookie HttpOnly.
 */
export function transcribeAudio(
  audioBlob,
  language = "es-ES",
) {
  return apiTranscribeAudio(
    audioBlob,
    language,
  );
}

/**
 * Obtiene el historial de voz del usuario autenticado.
 */
export function getVoiceHistory(
  limit = 10,
) {
  const safeLimit = Math.max(
    1,
    Math.min(
      Number(limit) || 10,
      50,
    ),
  );

  return apiGetVoiceHistory(
    safeLimit,
  );
}