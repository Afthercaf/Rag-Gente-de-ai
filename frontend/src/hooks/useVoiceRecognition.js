// hooks/useVoiceRecognition.js
// Grabación con MediaRecorder → transcripción vía Whisper en FastAPI
// Sin dependencia de Google Speech API — funciona en Brave, Firefox, cualquier navegador

import { useState, useCallback, useRef } from "react";
import api from "../api/client";

export const useVoiceRecognition = ({
  onResult,
  onError,
  language = "es-MX",
} = {}) => {
  const [isListening, setIsListening] = useState(false);
  const [isSupported] = useState(
    () => !!(navigator.mediaDevices?.getUserMedia && window.MediaRecorder)
  );
  const [transcript, setTranscript] = useState("");
  // interimTranscript siempre vacío (Whisper procesa offline, no hay interim)
  const interimTranscript = "";

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const audioCtxRef = useRef(null);
  const checkIntervalRef = useRef(null);
  const hasAudioRef = useRef(false);
  const isTranscribingRef = useRef(false);

  // ── Elegir el mejor mimeType disponible ───────────────────────
  const getBestMimeType = () => {
    const types = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/ogg",
      "audio/mp4",
    ];
    return types.find((t) => MediaRecorder.isTypeSupported(t)) || "";
  };

  // ── Limpiar analizador de audio ───────────────────────────────
  const cleanupAudioAnalyser = () => {
    if (checkIntervalRef.current) {
      clearInterval(checkIntervalRef.current);
      checkIntervalRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
  };

  // ── Enviar audio al backend Whisper ───────────────────────────
  const transcribeAudio = useCallback(
    async (blob) => {
      if (isTranscribingRef.current) return;
      isTranscribingRef.current = true;

      try {
        const formData = new FormData();
        formData.append("audio", blob, "recording.webm");
        formData.append("language", language);

        // ✅ H-07 FIX: Usar cliente autenticado (cookie HttpOnly + withCredentials).
        const response = await api.post("/voice/transcribe", formData, {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        });

        if (response.status >= 400) {
          const err = response.data || {};
          throw new Error(err.detail || `HTTP ${response.status}`);
        }

        const data = response.data;

        if (data.success && data.text?.trim()) {
          setTranscript(data.text.trim());
          onResult?.(data.text.trim());
        } else {
          onError?.(data.error || "No se detectó voz, intenta de nuevo");
        }
      } catch {
        onError?.("Error al procesar el audio, intenta de nuevo");
      } finally {
        isTranscribingRef.current = false;
      }
    },
    [language, onResult, onError]
  );

  // ── Iniciar grabación ─────────────────────────────────────────
  const startListening = useCallback(async () => {
    if (isListening) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      streamRef.current = stream;
      chunksRef.current = [];
      hasAudioRef.current = false;

      // ── Detector de volumen para verificar señal real ─────────
      try {
        const audioCtx = new AudioContext();
        audioCtxRef.current = audioCtx;
        const source = audioCtx.createMediaStreamSource(stream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        const dataArray = new Uint8Array(analyser.frequencyBinCount);

        checkIntervalRef.current = setInterval(() => {
          analyser.getByteFrequencyData(dataArray);
          const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
          if (avg > 2) {
            hasAudioRef.current = true;
          }
        }, 200);
      } catch {
        // Si AudioContext falla, igual intentamos grabar
        hasAudioRef.current = true; // asumir que hay audio
      }

      const mimeType = getBestMimeType();
      const options = mimeType ? { mimeType } : {};
      const mediaRecorder = new MediaRecorder(stream, options);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        // Limpiar analizador
        cleanupAudioAnalyser();

        // Liberar micrófono
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;

        if (chunksRef.current.length === 0) {
          onError?.("No se capturó audio, intenta de nuevo");
          return;
        }

        // Verificar que hubo señal real
        if (!hasAudioRef.current) {
          onError?.("No se detectó audio. Verifica que el micrófono correcto esté seleccionado en Brave.");
          return;
        }

        const blob = new Blob(chunksRef.current, {
          type: mimeType || "audio/webm",
        });
        chunksRef.current = [];

        await transcribeAudio(blob);
      };

      mediaRecorder.start();
      setIsListening(true);
      setTranscript("");

    } catch (err) {
      cleanupAudioAnalyser();
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        onError?.("Permiso denegado para usar el micrófono");
      } else if (err.name === "NotFoundError") {
        onError?.("No se encontró micrófono en este dispositivo");
      } else {
        onError?.("No se pudo acceder al micrófono");
      }
    }
  }, [isListening, transcribeAudio, onError]);

  // ── Detener grabación (dispara transcripción) ─────────────────
  const stopListening = useCallback(() => {
    if (!isListening) return;

    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state === "recording"
    ) {
      mediaRecorderRef.current.stop(); // dispara onstop → transcribeAudio
    } else {
      cleanupAudioAnalyser();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }

    setIsListening(false);
  }, [isListening]);

  // ── Toggle ────────────────────────────────────────────────────
  const toggleListening = useCallback(() => {
    if (isListening) stopListening();
    else startListening();
  }, [isListening, startListening, stopListening]);

  return {
    isListening,
    isSupported,
    transcript,
    interimTranscript,
    startListening,
    stopListening,
    toggleListening,
  };
};
