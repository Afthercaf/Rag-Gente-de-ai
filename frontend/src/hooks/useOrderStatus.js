import { useState, useEffect, useRef } from "react";


const API_BASE =
  import.meta.env.VITE_API_URL;

const POLL_INTERVAL = 5000;

const FINAL_STATUSES = new Set([
  "entregado",
  "cancelado",
]);

export const STATUS_LABELS = {
  pendiente: "📦 Pendiente — recibimos tu pedido",
  confirmado: "✅ Confirmado — ¡tu pedido fue aceptado!",
  preparando: "🍕 En preparación — los cocineros ya trabajan en él",
  "en camino": "🛵 En camino — el repartidor ya salió",
  entregado: "🎉 Entregado — ¡buen provecho!",
  cancelado: "❌ Cancelado — comunícate con nosotros si tienes dudas",
  desconocido: "❓ Estado desconocido",
};

export function useOrderStatus(orderId) {
  const [status, setStatus] = useState("pendiente");

  const intervalRef = useRef(null);

  useEffect(() => {
    if (!orderId) return;

    const fetchStatus = async () => {
      try {
        const res = await fetch(
          `${API_BASE}/order/${orderId}/status`
        );

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }

        const data = await res.json();

        console.log(
          "[ORDER STATUS]",
          orderId,
          data
        );

        const newStatus =
          data.status ||
          data.estado ||
          "desconocido";

        setStatus(newStatus);

        if (FINAL_STATUSES.has(newStatus)) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      } catch (err) {
        console.error(
          "[useOrderStatus]",
          err
        );
      }
    };

    fetchStatus();

    intervalRef.current = setInterval(
      fetchStatus,
      POLL_INTERVAL
    );

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [orderId]);

  return {
    status,
    label: STATUS_LABELS[status] || status,
    isDone: FINAL_STATUSES.has(status),
  };
}