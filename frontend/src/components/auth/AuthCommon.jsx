import { s, MUTED } from "../../styles/theme";

/** Contenedor centrado con logo para las pantallas de auth */
export function AuthShell({ title, subtitle, children }) {
  return (
    <div style={s.root}>
      <div style={s.bgPattern} />
      <div style={s.authWrap}>
        <div style={s.authLogo}>
          <span style={{ fontSize: 48 }}>🍕</span>
          <div style={s.logoName}>Pizzería 220</div>
          <div style={{ ...s.logoSub, textAlign: "center" }}>{subtitle}</div>
        </div>
        <div style={s.authCard}>
          <div style={s.authTitle}>{title}</div>
          {children}
        </div>
      </div>
    </div>
  );
}

/** Input con etiqueta */
export function Field({ label, type = "text", value, onChange, placeholder, onEnter }) {
  return (
    <div style={s.fieldWrap}>
      <label style={s.fieldLabel}>{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && onEnter) onEnter(); }}
        placeholder={placeholder}
        style={s.authInput}
      />
    </div>
  );
}

/** Fila de dos columnas */
export function Row({ children }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
      {children}
    </div>
  );
}

/** Botón de submit con estado de carga */
export function AuthBtn({ onClick, loading, children }) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      style={{ ...s.authSubmit, opacity: loading ? 0.6 : 1 }}
    >
      {loading ? "Cargando..." : children}
    </button>
  );
}

/** Enlace de navegación entre Login / Register */
export function AuthSwitch({ children }) {
  return (
    <p style={{ textAlign: "center", fontSize: 13, color: MUTED, marginTop: 14 }}>
      {children}
    </p>
  );
}

/** Caja de error */
export function ErrorMsg({ children }) {
  return <div style={s.errorMsg}>{children}</div>;
}
