import "../../styles/theme.css";

/**
 * Contenedor centrado con logo para las pantallas de autenticación.
 */
export function AuthShell({
  title,
  subtitle,
  children,
}) {
  return (
    <div className="p220-auth-shell">
      <div
        className="p220-bg-pattern"
        aria-hidden="true"
      />

      <div className="p220-auth-wrap">
        <div className="p220-auth-logo">
          <span
            style={{ fontSize: 48 }}
            aria-hidden="true"
          >
            🍕
          </span>

          <div className="p220-logo-name">
            Pizzería 220
          </div>

          <div
            className="p220-logo-sub"
            style={{ textAlign: "center" }}
          >
            {subtitle}
          </div>
        </div>

        <div className="p220-auth-card">
          <h1 className="p220-auth-title">
            {title}
          </h1>

          {children}
        </div>
      </div>
    </div>
  );
}

/**
 * Input con etiqueta y atributos accesibles.
 */
export function Field({
  label,
  name,
  type = "text",
  value,
  onChange,
  placeholder,
  onEnter,
  autoComplete,
  inputMode,
  disabled = false,
  required = false,
  minLength,
  maxLength,
}) {
  const inputId = `p220-${name || label
    .toLowerCase()
    .replace(/\s+/g, "-")}`;

  return (
    <div className="p220-field-wrap">
      <label
        className="p220-field-label"
        htmlFor={inputId}
      >
        {label}
      </label>

      <input
        id={inputId}
        name={name}
        className="p220-auth-input"
        type={type}
        value={value}
        onChange={(event) =>
          onChange(event.target.value)
        }
        onKeyDown={(event) => {
          if (
            event.key === "Enter" &&
            onEnter &&
            !disabled
          ) {
            event.preventDefault();
            onEnter();
          }
        }}
        placeholder={placeholder}
        autoComplete={autoComplete}
        inputMode={inputMode}
        disabled={disabled}
        required={required}
        minLength={minLength}
        maxLength={maxLength}
      />
    </div>
  );
}

/**
 * Fila responsive de dos columnas.
 */
export function Row({ children }) {
  return (
    <div className="p220-row-2col">
      {children}
    </div>
  );
}

/**
 * Botón principal con estado de carga.
 */
export function AuthBtn({
  onClick,
  loading,
  children,
}) {
  return (
    <button
      type="button"
      className="p220-auth-submit"
      onClick={onClick}
      disabled={loading}
      aria-busy={loading}
    >
      {loading ? "Cargando…" : children}
    </button>
  );
}

/**
 * Navegación entre login y registro.
 */
export function AuthSwitch({ children }) {
  return (
    <p className="p220-auth-switch">
      {children}
    </p>
  );
}

/**
 * Mensaje accesible de error.
 */
export function ErrorMsg({ children }) {
  return (
    <div
      className="p220-error-msg"
      role="alert"
      aria-live="polite"
    >
      {children}
    </div>
  );
}