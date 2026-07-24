import { useState, useEffect } from "react";

// Etiquetas visibles para cada valor real de payment_method.
// Si se agrega un nuevo método de pago, solo hay que añadirlo aquí.
const PAYMENT_LABELS = {
  efectivo: "💵 Efectivo",
  mercado_pago: "💳 Mercado Pago",
};

/**
 * Muestra un paso del flujo de pedido: input de texto o selector de opciones.
 *
 * @param {{ step: object, onSubmit: (value: string) => void }} props
 */
export default function OrderStep({ step, onSubmit }) {
  const [val, setVal] = useState(step.options ? step.options[0] : "");

  // Resetea el valor cuando cambia el paso
  useEffect(() => {
    setVal(step.options ? step.options[0] : "");
  }, [step]);

  const handle = () => {
    if (val.trim()) onSubmit(val.trim());
  };

  return (
    <div className="p220-order-card">
      <div className="p220-order-label">{step.label}</div>

      {step.type === "select" ? (
        <div className="p220-select-row">
          {step.options.map((opt) => (
            <button
              key={opt}
              className={`p220-opt-btn${val === opt ? " is-active" : ""}`}
              onClick={() => onSubmit(opt)}
            >
              {PAYMENT_LABELS[opt] || opt}
            </button>
          ))}
        </div>
      ) : (
        <div className="p220-order-input-row">
          <input
            autoFocus
            type={step.type}
            value={val}
            onChange={(e) => setVal(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handle(); }}
            className="p220-order-input"
            placeholder={step.label}
          />
          <button onClick={handle} disabled={!val.trim()} className="p220-order-submit">
            →
          </button>
        </div>
      )}
    </div>
  );
}