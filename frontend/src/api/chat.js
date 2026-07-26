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
  const safeLimit = Math.max(
    1,
    Math.min(Number(limit) || 50, 100),
  );

  return apiRequest(
    `/chat/history?limit=${safeLimit}`,
  );
}

export function deleteChatHistory() {
  return apiRequest("/chat/history", {
    method: "DELETE",
  });
}

export function placeOrder(
  pedido,
  data,
  ubicacion,
) {
  return apiRequest("/order", {
    method: "POST",
    body: {
      pedido,
      cliente_nombre: data.cliente_nombre,
      telefono: data.telefono,
      gmail: data.gmail,
      direccion: data.direccion,
      payment_method: data.payment_method,
      ubicacion: ubicacion ?? null,
    },
  });
}

export function getOrderStatus(orderId) {
  return apiRequest(
    `/order/${encodeURIComponent(orderId)}/status`,
  );
}

export function cancelOrder(
  orderId,
  reason = "",
) {
  const query = reason
    ? `?reason=${encodeURIComponent(reason)}`
    : "";

  return apiRequest(
    `/order/${encodeURIComponent(orderId)}/cancel${query}`,
    {
      method: "POST",
      body: {},
    },
  );
}