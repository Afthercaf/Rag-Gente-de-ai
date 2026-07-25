import { apiRequest } from "./client";

export function sendChat(message, options = {}) {
  return apiRequest("/chat", {
    method: "POST",
    body: {
      message: message.trim(),
      use_cache: options.useCache ?? false,
      save_history: options.saveHistory ?? true,
    },
  });
}

export function getChatHistory(limit = 50) {
  const safeLimit = Math.max(1, Math.min(Number(limit) || 50, 100));
  return apiRequest(`/chat/history?limit=${safeLimit}`);
}

export function deleteChatHistory() {
  return apiRequest("/chat/history", {
    method: "DELETE",
  });
}

export function placeOrder(pedido, userData, location) {
  return apiRequest("/order", {
    method: "POST",
    body: {
      pedido: String(pedido || "").trim(),
      cliente_nombre: String(userData?.cliente_nombre || "").trim(),
      telefono: String(userData?.telefono || "").trim(),
      gmail: String(userData?.gmail || "").trim(),
      direccion: String(userData?.direccion || "").trim(),
      payment_method: String(
        userData?.payment_method || "efectivo"
      ).trim(),
      ubicacion: location || null,

      // No se envían user_id ni total.
      // Ambos deben obtenerse/calcularse en el servidor.
    },
  });
}

export function getOrderStatus(orderId) {
  return apiRequest(`/order/${encodeURIComponent(orderId)}/status`);
}

export function cancelOrder(orderId, reason = "") {
  const query = reason
    ? `?reason=${encodeURIComponent(reason)}`
    : "";

  return apiRequest(
    `/order/${encodeURIComponent(orderId)}/cancel${query}`,
    {
      method: "POST",
      body: {},
    }
  );
}
