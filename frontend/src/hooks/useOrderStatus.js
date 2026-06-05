// src/hooks/useOrderStatus.js
// Hook de React para hacer polling del estado del pedido.
// Úsalo en el componente de chat justo después de que el usuario confirme su pedido.
//
// Ejemplo de uso:
//   const { status, label, isDone } = useOrderStatus(orderId);
//   <p>Estado: {label}</p>

import { useState, useEffect, useRef } from "react";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// Intervalo de polling en milisegundos
const POLL_INTERVAL = 5000;

// Estados que detienen el polling (finales)
const FINAL_STATUSES = new Set(["en camino", "cancelado"]);

// Mapa de estado → etiqueta amigable para el cliente
export const STATUS_LABELS = {
  pendiente:  "📦 Pendiente",
  confirmado: "✅ Confirmado — ¡tu pedido fue aceptado!",
  preparando: "🍕 En preparación — los cocineros ya trabajan en él",
  "en camino":"🛵 En camino — el repartidor ya salió",
  cancelado:  "❌ Cancelado — comunícate con nosotros si tienes dudas",
  desconocido:"❓ Estado desconocido",
};

/**
 * @param {string|null} orderId  - ID del pedido a monitorear. Pasa null para no hacer nada.
 * @returns {{ status: string, label: string, isDone: boolean }}
 */
export function useOrderStatus(orderId) {
  const [status, setStatus]   = useState("pendiente");
  const intervalRef           = useRef(null);

  useEffect(() => {
    if (!orderId) return;

    const fetchStatus = async () => {
      try {
        const res  = await fetch(`${API_BASE}/order/${orderId}/status`);
        const data = await res.json();
        const newStatus = data.status ?? "desconocido";
        setStatus(newStatus);

        // Detener polling si llegamos a un estado final
        if (FINAL_STATUSES.has(newStatus)) {
          clearInterval(intervalRef.current);
        }
      } catch (err) {
        console.error("[useOrderStatus] Error en polling:", err);
      }
    };

    // Primera consulta inmediata
    fetchStatus();

    // Polling periódico
    intervalRef.current = setInterval(fetchStatus, POLL_INTERVAL);

    // Limpiar al desmontar o cambiar orderId
    return () => clearInterval(intervalRef.current);
  }, [orderId]);

  return {
    status,
    label:  STATUS_LABELS[status] ?? status,
    isDone: FINAL_STATUSES.has(status),
  };
}