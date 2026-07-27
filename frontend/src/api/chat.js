import { apiRequest } from "./client";

/**
 * Envía un mensaje al asistente.
 *
 * El usuario no se envía desde el frontend.
 * El backend obtiene el usuario desde el JWT.
 */
export function sendChat(
  message,
  options = {},
) {
  const normalizedMessage = String(
    message || "",
  ).trim();

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

/**
 * Obtiene el historial del usuario autenticado.
 */
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

/**
 * Elimina el historial del usuario autenticado.
 */
export function deleteChatHistory() {
  return apiRequest("/chat/history", {
    method: "DELETE",
  });
}

/**
 * Normaliza y valida la ubicación antes de enviarla.
 */
function normalizeLocation(
  location,
) {
  if (!location) {
    return null;
  }

  const lat = Number(
    location.lat,
  );

  const lng = Number(
    location.lng,
  );

  if (
    !Number.isFinite(lat) ||
    lat < -90 ||
    lat > 90
  ) {
    throw new Error(
      "La latitud de la ubicación no es válida.",
    );
  }

  if (
    !Number.isFinite(lng) ||
    lng < -180 ||
    lng > 180
  ) {
    throw new Error(
      "La longitud de la ubicación no es válida.",
    );
  }

  const fullAddress = String(
    location.direccion_completa || "",
  ).trim();

  const timestamp = String(
    location.timestamp ||
      new Date().toISOString(),
  ).trim();

  return {
    lat,
    lng,
    direccion_completa:
      fullAddress || null,
    timestamp:
      timestamp || null,
  };
}

/**
 * Normaliza los datos principales del pedido.
 */
function normalizeOrderData(
  pedido,
  data,
  location,
) {
  const normalizedLocation =
    normalizeLocation(location);

  const normalizedPedido =
    String(pedido || "").trim();

  const clienteNombre =
    String(
      data?.cliente_nombre || "",
    ).trim();

  const telefono =
    String(
      data?.telefono || "",
    ).trim();

  const gmail =
    String(
      data?.gmail || "",
    )
      .trim()
      .toLowerCase();

  const direccion =
    String(
      data?.direccion ||
        normalizedLocation
          ?.direccion_completa ||
        "",
    ).trim();

  const paymentMethod =
    data?.payment_method ===
    "mercado_pago"
      ? "mercado_pago"
      : "efectivo";

  return {
    pedido:
      normalizedPedido,
    cliente_nombre:
      clienteNombre,
    telefono,
    gmail,
    direccion,
    payment_method:
      paymentMethod,
    ubicacion:
      normalizedLocation,
  };
}

/**
 * Valida el payload antes de enviarlo al backend.
 *
 * Esto evita solicitudes 422 por campos vacíos o inválidos.
 */
function validateOrderPayload(
  payload,
) {
  const errors = [];

  if (
    !payload.pedido ||
    payload.pedido.length < 1
  ) {
    errors.push(
      "El pedido está vacío",
    );
  }

  if (
    !payload.cliente_nombre ||
    payload.cliente_nombre.length < 2
  ) {
    errors.push(
      "El nombre debe tener al menos 2 caracteres",
    );
  }

  const phoneDigits =
    payload.telefono.replace(
      /\D/g,
      "",
    );

  if (
    phoneDigits.length < 8 ||
    phoneDigits.length > 15
  ) {
    errors.push(
      "El teléfono debe contener entre 8 y 15 dígitos",
    );
  }

  if (
    !payload.gmail ||
    !payload.gmail.includes("@") ||
    payload.gmail.startsWith("@") ||
    payload.gmail.endsWith("@")
  ) {
    errors.push(
      "El correo electrónico no es válido",
    );
  }

  if (
    !payload.direccion ||
    payload.direccion.length < 3
  ) {
    errors.push(
      "La dirección debe tener al menos 3 caracteres",
    );
  }

  if (
    ![
      "efectivo",
      "mercado_pago",
    ].includes(
      payload.payment_method,
    )
  ) {
    errors.push(
      "El método de pago no es válido",
    );
  }

  if (!payload.ubicacion) {
    errors.push(
      "La ubicación es requerida",
    );
  }

  if (errors.length > 0) {
    throw new Error(
      errors.join("\n"),
    );
  }
}

/**
 * Crea una orden.
 *
 * Importante:
 * - no envía user_id;
 * - no envía total;
 * - no envía role;
 * - no envía status;
 * - el usuario se obtiene del JWT en el backend;
 * - el total debe calcularse en el servidor.
 */
export function placeOrder(
  pedido,
  data,
  location,
) {
  const payload =
    normalizeOrderData(
      pedido,
      data,
      location,
    );

  validateOrderPayload(
    payload,
  );

  /*
   * Log temporal de diagnóstico.
   *
   * Puedes eliminarlo después de resolver el 422.
   * No contiene JWT ni contraseñas.
   */
  console.log(
    "PAYLOAD /order:",
    JSON.stringify(
      payload,
      null,
      2,
    ),
  );

  return apiRequest("/order", {
    method: "POST",
    body: payload,
  });
}

/**
 * Consulta el estado de una orden.
 */
export function getOrderStatus(
  orderId,
) {
  const normalizedOrderId =
    String(orderId || "").trim();

  if (!normalizedOrderId) {
    throw new Error(
      "El identificador de la orden es requerido.",
    );
  }

  return apiRequest(
    `/order/${encodeURIComponent(
      normalizedOrderId,
    )}/status`,
  );
}

/**
 * Cancela una orden del usuario autenticado.
 */
export function cancelOrder(
  orderId,
  reason = "",
) {
  const normalizedOrderId =
    String(orderId || "").trim();

  if (!normalizedOrderId) {
    throw new Error(
      "El identificador de la orden es requerido.",
    );
  }

  const normalizedReason =
    String(reason || "").trim();

  const query =
    normalizedReason
      ? `?reason=${encodeURIComponent(
          normalizedReason,
        )}`
      : "";

  return apiRequest(
    `/order/${encodeURIComponent(
      normalizedOrderId,
    )}/cancel${query}`,
    {
      method: "POST",
      body: {},
    },
  );
}