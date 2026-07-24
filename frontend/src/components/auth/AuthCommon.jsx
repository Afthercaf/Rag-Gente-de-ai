import '../../styles/theme.css';

/** Contenedor centrado con logo para las pantallas de auth */
export function AuthShell({ title, subtitle, children }) {
  return (
    <div className="p220-auth-shell">
      <div className="p220-bg-pattern" />
      <div className="p220-auth-wrap">
        <div className="p220-auth-logo">
          <span style={{ fontSize: 48 }}>🍕</span>
          <div className="p220-logo-name">Pizzería 220</div>
          <div className="p220-logo-sub" style={{ textAlign: "center" }}>{subtitle}</div>
        </div>
        <div className="p220-auth-card">
          <div className="p220-auth-title">{title}</div>
          {children}
        </div>
      </div>
    </div>
  );
}

/** Input con etiqueta */
export function Field({ label, type = "text", value, onChange, placeholder, onEnter }) {
  return (
    <div className="p220-field-wrap">
      <label className="p220-field-label">{label}</label>
      <input
        className="p220-auth-input"
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && onEnter) onEnter(); }}
        placeholder={placeholder}
      />
    </div>
  );
}

/** Fila de dos columnas */
export function Row({ children }) {
  return (
    <div className="p220-row-2col">
      {children}
    </div>
  );
}

/** Botón de submit con estado de carga */
export function AuthBtn({ onClick, loading, children }) {
  return (
    <button
      className="p220-auth-submit"
      onClick={onClick}
      disabled={loading}
    >
      {loading ? "Cargando..." : children}
    </button>
  );
}

/** Enlace de navegación entre Login / Register */
export function AuthSwitch({ children }) {
  return (
    <p className="p220-auth-switch">
      {children}
    </p>
  );
}

/** Caja de error */
export function ErrorMsg({ children }) {
  return <div className="p220-error-msg">{children}</div>;
}