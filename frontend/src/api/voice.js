import { apiRequest } from "./client";

export function transcribeAudio(audioBlob, language = "es-ES") {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.webm");
  formData.append("language", language);

  // No enviar user_id; el backend lo obtiene del token.
  return apiRequest("/voice/transcribe", {
    method: "POST",
    body: formData,
  });
}

export function getVoiceHistory(limit = 10) {
  const safeLimit = Math.max(1, Math.min(Number(limit) || 10, 50));
  return apiRequest(`/voice/history?limit=${safeLimit}`);
}
