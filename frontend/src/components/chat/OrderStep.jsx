import { useState, useEffect } from "react";
import { s } from "../../styles/theme";

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
    <div style={s.orderCard}>
      <div style={s.orderLabel}>{step.label}</div>

      {step.type === "select" ? (
        <div style={s.selectRow}>
          {step.options.map((opt) => (
            <button
              key={opt}
              onClick={() => onSubmit(opt)}
              style={{ ...s.optBtn, ...(val === opt ? s.optBtnActive : {}) }}
            >
              {opt === "efectivo" ? "💵 Efectivo" : "💳 Tarjeta"}
            </button>
          ))}
        </div>
      ) : (
        <div style={s.orderInputRow}>
          <input
            autoFocus
            type={step.type}
            value={val}
            onChange={(e) => setVal(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handle(); }}
            style={s.orderInput}
            placeholder={step.label}
          />
          <button onClick={handle} disabled={!val.trim()} style={s.orderSubmit}>
            →
          </button>
        </div>
      )}
    </div>
  );
}
