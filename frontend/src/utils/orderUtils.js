export const ORDER_KEYWORDS = [
  "quiero pedir", "pedido", "ordenar", "comprar", "pizza",
  "mandame", "envía", "quiero una", "quisiera",
];

/**
 * Devuelve true si el texto parece un pedido.
 * @param {string} text
 */
export const isOrderQuery = (text) =>
  ORDER_KEYWORDS.some((k) => text.toLowerCase().includes(k));

/** Genera IDs únicos simples para mensajes. */
let uid = 0;
export const nextId = () => ++uid;

/**
 * Pasos que se solicitan al hacer un pedido.
 * Los campos ya presentes en el perfil del usuario se omiten en el flujo
 * (excepto payment_method, que siempre se pide).
 */
export const ALL_ORDER_STEPS = [
  { key: "cliente_nombre", label: "👤 Nombre completo",    type: "text"   },
  { key: "telefono",       label: "📞 Teléfono",           type: "tel"    },
  { key: "gmail",          label: "📧 Correo Gmail",       type: "email"  },
  { key: "direccion",      label: "📍 Dirección completa", type: "text"   },
  {
    key: "payment_method",
    label: "💳 Método de pago",
    type: "select",
    options: ["efectivo", "tarjeta"],
  },
];

/**
 * Filtra los pasos que ya están cubiertos por los datos del usuario logueado.
 * @param {{ cliente_nombre?, telefono?, gmail?, direccion? }} prefilled
 */
export const getOrderSteps = (prefilled = {}) =>
  ALL_ORDER_STEPS.filter(
    (st) => st.key === "payment_method" || !prefilled[st.key]
  );
