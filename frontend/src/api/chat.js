import { apiRequest } from "./client";

export function sendChat(
  message,
  options = {},
) {
  const normalizedMessage =
    String(message || "").trim();

  if (!normalizedMessage) {
    throw new Error(
      "Escribe un mensaje antes de enviarlo.",
    );
  }

  return apiRequest("/chat", {
    method: "POST",
    body: {
      message: normalizedMessage,
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

function normalizeLocation(ubicacion) {
  if (!ubicacion) {
    return null;
  }

  const lat = Number(ubicacion.lat);
  const lng = Number(ubicacion.lng);

  if (
    !Number.isFinite(lat) ||
    !Number.isFinite(lng)
  ) {
    throw new Error(
      "La ubicación seleccionada no es válida.",
    );
  }

  return {
    lat,
    lng,
    direccion_completa:
      String(
        ubicacion.direccion_completa || "",
      ).trim() || null,
    timestamp:
      ubicacion.timestamp || null,
  };
}

export function placeOrder(
  pedido,
  data,
  ubicacion,
) {
  const normalizedPedido =
    String(pedido || "").trim();

  const payload = {
    pedido: normalizedPedido,
    cliente_nombre:
      String(
        data?.cliente_nombre || "",
      ).trim(),
    telefono:
      String(
        data?.telefono || "",
      ).trim(),
    gmail:
      String(
        data?.gmail || "",
      )
        .trim()
        .toLowerCase(),
    direccion:
      String(
        data?.direccion ||
        ubicacion?.direccion_completa ||
        "",
      ).trim(),
    payment_method:
      data?.payment_method ===
      "mercado_pago"
        ? "mercado_pago"
        : "efectivo",
    ubicacion:
      normalizeLocation(ubicacion),
  };

  return apiRequest("/order", {
    method: "POST",
    body: payload,
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
    ? `?reason=${encodeURIComponent(
        reason,
      )}`
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
