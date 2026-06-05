import { useState } from "react";
import { login } from "../../api/auth";
import { s } from "../../styles/theme";
import {
  AuthShell,
  Field,
  AuthBtn,
  AuthSwitch,
  ErrorMsg,
} from "./AuthCommon";

/**
 * @param {{ onLogin: (user) => void, onGo: () => void }} props
 */
export default function LoginScreen({ onLogin, onGo }) {
  const [gmail, setGmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!gmail.trim() || !password.trim()) {
      setError("Completa todos los campos.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const data = await login(gmail, password);

      if (data.success) {
        // La cookie ya la guarda el backend
        onLogin(data.user);
      } else {
        setError(data.message || "Credenciales incorrectas.");
      }
    } catch (err) {
      setError(err?.message || "Error al iniciar sesión");
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
        label="Correo Gmail"
        type="email"
        value={gmail}
        onChange={setGmail}
        placeholder="usuario@gmail.com"
      />

      <Field
        label="Contraseña"
        type="password"
        value={password}
        onChange={setPassword}
        placeholder="••••••••"
        onEnter={submit}
      />

      {error && <ErrorMsg>{error}</ErrorMsg>}

      <AuthBtn onClick={submit} loading={loading}>
        Entrar
      </AuthBtn>

      <AuthSwitch>
        ¿No tienes cuenta?{" "}
        <span onClick={onGo} style={s.authLink}>
          Regístrate
        </span>
      </AuthSwitch>
    </AuthShell>
  );
}