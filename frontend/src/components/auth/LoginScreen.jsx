import { useState } from "react";

import { login } from "../../api/auth";
import {
  AuthBtn,
  AuthShell,
  AuthSwitch,
  ErrorMsg,
  Field,
} from "./AuthCommon";

/**
 * @param {{ onLogin: (user: object) => void, onGo: () => void }} props
 */
export default function LoginScreen({
  onLogin,
  onGo,
}) {
  const [gmail, setGmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (loading) return;

    if (!gmail.trim() || !password) {
      setError("Completa todos los campos.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      /*
       * api/auth.js guarda access_token + user y devuelve
       * directamente el usuario autenticado.
       */
      const user = await login(
        gmail.trim(),
        password
      );

      onLogin(user);
    } catch (err) {
      setError(
        err?.message || "No se pudo iniciar sesión."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      title="Bienvenido"
      subtitle="Inicia sesión para continuar"
    >
      <Field
        label="Correo electrónico"
        name="gmail"
        type="email"
        value={gmail}
        onChange={setGmail}
        placeholder="usuario@gmail.com"
        autoComplete="email"
        disabled={loading}
        required
      />

      <Field
        label="Contraseña"
        name="password"
        type="password"
        value={password}
        onChange={setPassword}
        placeholder="••••••••••"
        autoComplete="current-password"
        onEnter={submit}
        disabled={loading}
        required
      />

      {error && <ErrorMsg>{error}</ErrorMsg>}

      <AuthBtn
        onClick={submit}
        loading={loading}
      >
        Entrar
      </AuthBtn>

      <AuthSwitch>
        ¿No tienes cuenta?{" "}
        <button
          type="button"
          className="p220-auth-link"
          onClick={onGo}
          disabled={loading}
        >
          Regístrate
        </button>
      </AuthSwitch>
    </AuthShell>
  );
}