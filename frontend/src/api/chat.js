import { apiRequest } from "./client";

export function sendChat(
  message,
  options = {},
) {
  return apiRequest("/chat", {
    method: "POST",
    body: {
      message: message.trim(),
      use_cache:
        options.useCache ?? false,
      save_history:
        options.saveHistory ?? true,
    },
  });
}

export function getChatHistory(
  limit = 50,
) {
  const safeLimit = Math.max(
    1,
    Math.min(
      Number(limit) || 50,
      100,
    ),
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
  const normalizedPedido =
    typeof pedido === "string"
      ? pedido.trim()
      : "";

  const paymentMethod =
    data?.payment_method === "mercado_pago"
      ? "mercado_pago"
      : "efectivo";

  return apiRequest("/order", {
    method: "POST",
    body: {
      pedido: normalizedPedido,
      cliente_nombre:
        String(data?.cliente_nombre || "").trim(),
      telefono:
        String(data?.telefono || "").trim(),
      gmail:
        String(data?.gmail || "")
          .trim()
          .toLowerCase(),
      direccion:
        String(data?.direccion || "").trim(),
      payment_method: paymentMethod,
      ubicacion: ubicacion
        ? {
            lat: Number(ubicacion.lat),
            lng: Number(ubicacion.lng),
            direccion_completa:
              String(
                ubicacion.direccion_completa ||
                "",
              ).trim() || null,
            timestamp:
              ubicacion.timestamp || null,
          }
        : null,
    },
  });
}

export function getOrderStatus(
  orderId,
) {
  return apiRequest(
    `/order/${encodeURIComponent(
      orderId,
    )}/status`,
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
    `/order/${encodeURIComponent(
      orderId,
    )}/cancel${query}`,
    {
      method: "POST",
      body: {},
    },
  );
}
