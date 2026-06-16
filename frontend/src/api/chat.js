import client from "./axiosClient";

/**
 * Envía un mensaje al chatbot.
 * @returns {{ reply: string, is_order?: boolean }}
 */
export async function sendChat(message, userId) {
  const { data } = await client.post("/chat", {
    user_id: userId,
    message,
  });

  return data;
}

/**
 * Registra un pedido completo.
 * @param {string} pedido  - texto original del usuario
 * @param {object} form    - { cliente_nombre, telefono, gmail, direccion, payment_method }
 * @param {object} ubicacion - { lat, lng, direccion_completa, ... } (opcional)
 * @returns {{ success, order_id, message }}
 */
function extractTotalFromText(text) {
  if (!text || typeof text !== "string") return null;
  const normalized = text.replace(/,/g, ".");

  // Buscar un total explícito o un precio marcado.
  const explicitTotal = normalized.match(/\b(?:total|importe|precio total|monto|subtotal)\b\s*[:=]?\s*(?:\$|USD|MXN)?\s*([0-9]+(?:\.[0-9]{1,2})?)/i);
  if (explicitTotal) return explicitTotal[1];

  const explicitPrice = normalized.match(/\b(?:precio|costo|coste|valor)\b\s*[:=]?\s*(?:\$|USD|MXN)?\s*([0-9]+(?:\.[0-9]{1,2})?)/i);
  if (explicitPrice) return explicitPrice[1];

  // Si el texto contiene un valor monetario con símbolo, use el último valor encontrado.
  const currencyValues = Array.from(normalized.matchAll(/(?:\$|USD|MXN)\s*([0-9]+(?:\.[0-9]{1,2})?)/gi), (m) => m[1]);
  if (currencyValues.length > 0) {
    return currencyValues[currencyValues.length - 1];
  }

  return null;
}

export async function placeOrder(user_id, pedido, form, ubicacion = null) {
  // Validaciones básicas
  if (!pedido || typeof pedido !== 'string') {
    throw new Error("El pedido es requerido");
  }
  
  if (!form || !form.cliente_nombre) {
    throw new Error("Los datos del cliente son requeridos");
  }
  
  const extractedTotal = extractTotalFromText(pedido);
  const payload = {
    user_id,
    pedido: pedido.trim(),
    cliente_nombre: form.cliente_nombre.trim(),
    telefono: form.telefono || "",
    gmail: form.gmail || "",
    direccion: form.direccion || "",
    total: form.total || extractedTotal || null,
    payment_method: form.payment_method || "efectivo",
  };
  
  // Agregar ubicación si existe
  if (ubicacion && ubicacion.lat && ubicacion.lng) {
    payload.ubicacion = {
      lat: ubicacion.lat,
      lng: ubicacion.lng,
      direccion_completa: ubicacion.direccion_completa || "",
      timestamp: ubicacion.timestamp || new Date().toISOString()
    };
  }
  
  console.log("📤 Enviando pedido al servidor:", payload);
  
  const { data } = await client.post("/order", payload);
  return data;
}

/**
 * Obtiene el estado actual de un pedido
 * @param {string} orderId
 * @returns {{ order_id: string, status: string }}
 */
export async function getOrderStatus(orderId) {
  if (!orderId) throw new Error("Order ID es requerido");
  const { data } = await client.get(`/order/${orderId}/status`);
  return data;
}

/**
 * Actualiza el estado de un pedido (solo para admin/staff)
 * @param {string} orderId
 * @param {string} status
 */
export async function updateOrderStatus(orderId, status) {
  if (!orderId || !status) throw new Error("Order ID y status son requeridos");
  const { data } = await client.patch(`/order/${orderId}/status`, { status });
  return data;
}