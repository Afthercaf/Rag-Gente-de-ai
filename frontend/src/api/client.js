/**
 * API Client — Pizzería 220 AI
 * 
 * Cliente HTTP con manejo automático de refresh tokens.
 * 
 * Características:
 * - Interceptor de respuestas 401 → refresh automático
 * - Cookies HttpOnly para tokens (no localStorage)
 * - Cola de requests pendientes durante refresh
 * - Manejo de concurrencia
 */

import axios from 'axios';

// ============================================================================
// CONFIGURACIÓN
// ============================================================================

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  withCredentials: true,  // Importante: envía cookies HttpOnly
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
});

// ============================================================================
// ESTADO DE REFRESH
// ============================================================================

let isRefreshing = false;
let failedQueue = [];

function processQueue(error, token = null) {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
}

// ============================================================================
// INTERCEPTOR DE RESPUESTAS
// ============================================================================

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Solo intentar refresh si:
    // 1. Es error 401
    // 2. No es una request de refresh
    // 3. No se ha reintentado ya
    if (
      error.response?.status !== 401 ||
      originalRequest.url?.includes('/auth/refresh') ||
      originalRequest._retry
    ) {
      return Promise.reject(error);
    }

    // Si ya se está refrescando, encolar la request
    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      }).then(() => {
        return api(originalRequest);
      });
    }

    originalRequest._retry = true;
    isRefreshing = true;

    try {
      // Intentar refresh con cookie HttpOnly
      await api.post('/auth/refresh');
      
      // Procesar cola de requests pendientes
      processQueue(null);
      
      // Reintentar request original
      return api(originalRequest);
    } catch (refreshError) {
      // Si falla el refresh, rechazar todas las requests pendientes
      processQueue(refreshError);
      
      // Redirigir al login
      window.location.href = '/login';
      
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  }
);

// ============================================================================
// FUNCIONES DE AUTENTICACIÓN
// ============================================================================

export async function login(gmail, password) {
  const response = await api.post('/auth/login', { gmail, password });
  return response.data;
}

export async function register(userData) {
  const response = await api.post('/auth/register', userData);
  return response.data;
}

export async function logout() {
  try {
    await api.post('/auth/logout');
  } finally {
    window.location.href = '/login';
  }
}

export async function getMe() {
  const response = await api.get('/auth/me');
  return response.data;
}

export async function refreshToken() {
  const response = await api.post('/auth/refresh');
  return response.data;
}

// ============================================================================
// FUNCIONES DE CHAT
// ============================================================================

export async function sendMessage(message, options = {}) {
  const response = await api.post('/chat', {
    message,
    use_cache: options.useCache ?? true,
    save_history: options.saveHistory ?? true,
  });
  return response.data;
}

export async function getChatHistory(limit = 50) {
  const response = await api.get('/chat/history', { params: { limit } });
  return response.data;
}

export async function deleteChatHistory() {
  const response = await api.delete('/chat/history');
  return response.data;
}

// ============================================================================
// FUNCIONES DE ÓRDENES
// ============================================================================

export async function createOrder(orderData) {
  const response = await api.post('/order', orderData);
  return response.data;
}

export async function getOrderStatus(orderId) {
  const response = await api.get(`/order/${orderId}/status`);
  return response.data;
}

export async function cancelOrder(orderId) {
  const response = await api.post(`/order/${orderId}/cancel`);
  return response.data;
}

// ============================================================================
// FUNCIONES DE VOZ
// ============================================================================

export async function transcribeAudio(audioBlob, language = 'es') {
  const formData = new FormData();
  formData.append('audio', audioBlob, 'recording.webm');
  formData.append('language', language);
  
  const response = await api.post('/voice/transcribe', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  });
  return response.data;
}

export async function getVoiceHistory(limit = 10) {
  const response = await api.get('/voice/history', { params: { limit } });
  return response.data;
}

// ============================================================================
// FUNCIONES DE MAPAS
// ============================================================================

export async function reverseGeocode(lat, lng) {
  const response = await api.get('/maps/reverse', { params: { lat, lng } });
  return response.data;
}

export async function searchAddress(query) {
  const response = await api.get('/maps/search', { params: { q: query } });
  return response.data;
}

export async function getStaticMap(lat, lng, zoom = 16) {
  const response = await api.get('/maps/static', {
    params: { lat, lng, zoom },
    responseType: 'blob',
  });
  return response.data;
}

// ============================================================================
// FUNCIONES DE CACHÉ
// ============================================================================

export async function getCacheStats() {
  const response = await api.get('/cache/stats');
  return response.data;
}

export async function clearCache() {
  const response = await api.post('/cache/clear');
  return response.data;
}

// ============================================================================
// FUNCIONES DE SALUD
// ============================================================================

export async function healthCheck() {
  const response = await api.get('/health');
  return response.data;
}

export default api;