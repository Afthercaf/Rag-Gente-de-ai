import { useState } from "react";
import {
  login,
  register,
} from "../../api/auth";
import {
  AuthBtn,
  AuthShell,
  AuthSwitch,
  ErrorMsg,
  Field,
  Row,
} from "./AuthCommon";

/**
 * @param {{ onLogin: (user: object) => void, onGo: () => void }} props
 */
export default function RegisterScreen({
  onLogin,
  onGo,
}) {
  const [form, setForm] = useState({
    nombre: "",
    telefono: "",
    gmail: "",
    direccion: "",
    password: "",
    confirm: "",
  });

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const set = (key) => (value) => {
    setForm((current) => ({
      ...current,
      [key]: value,
    }));
  };

  const submit = async () => {
    if (loading) return;

    const {
      nombre,
      telefono,
      gmail,
      direccion,
      password,
      confirm,
    } = form;

    if (
      !nombre.trim() ||
      !telefono.trim() ||
      !gmail.trim() ||
      !direccion.trim() ||
      !password
    ) {
      setError("Completa todos los campos.");
      return;
    }

    if (password.length < 10) {
      setError(
        "La contraseña debe tener al menos 10 caracteres."
      );
      return;
    }

    if (!/[A-Z]/.test(password)) {
      setError(
        "La contraseña debe incluir una letra mayúscula."
      );
      return;
    }

    if (!/[a-z]/.test(password)) {
      setError(
        "La contraseña debe incluir una letra minúscula."
      );
      return;
    }

    if (!/\d/.test(password)) {
      setError(
        "La contraseña debe incluir al menos un número."
      );
      return;
    }

    if (password !== confirm) {
      setError("Las contraseñas no coinciden.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const registration = await register({
        nombre,
        telefono,
        gmail,
        direccion,
        password,
      });

      if (registration?.success === false) {
        throw new Error(
          registration.message || "No se pudo crear la cuenta."
        );
      }

      /*
       * El registro no debe guardar una sesión por sí solo si todavía
       * no existe un access_token. Iniciamos sesión después del registro
       * para obtener el JWT firmado y persistirlo mediante api/auth.js.
       */
      const user = await login(gmail, password);
      onLogin(user);
    } catch (err) {
      setError(
        err?.message || "No se pudo completar el registro."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      title="Crear cuenta"
      subtitle="Regístrate para hacer pedidos"
    >
      <Row>
        <Field
          label="Nombre completo"
          name="nombre"
          value={form.nombre}
          onChange={set("nombre")}
          placeholder="Juan Pérez"
          autoComplete="name"
          disabled={loading}
          required
        />

        <Field
          label="Teléfono"
          name="telefono"
          type="tel"
          value={form.telefono}
          onChange={set("telefono")}
          placeholder="+52 999 000 0000"
          autoComplete="tel"
          inputMode="tel"
          disabled={loading}
          required
        />
      </Row>

      <Field
        label="Correo electrónico"
        name="gmail"
        type="email"
        value={form.gmail}
        onChange={set("gmail")}
        placeholder="usuario@gmail.com"
        autoComplete="email"
        disabled={loading}
        required
      />

      <Field
        label="Dirección"
        name="direccion"
        value={form.direccion}
        onChange={set("direccion")}
        placeholder="Calle, número y colonia"
        autoComplete="street-address"
        disabled={loading}
        required
      />

      <Row>
        <Field
          label="Contraseña"
          name="password"
          type="password"
          value={form.password}
          onChange={set("password")}
          placeholder="••••••••••"
          autoComplete="new-password"
          disabled={loading}
          required
        />

        <Field
          label="Confirmar contraseña"
          name="confirm"
          type="password"
          value={form.confirm}
          onChange={set("confirm")}
          placeholder="••••••••••"
          autoComplete="new-password"
          onEnter={submit}
          disabled={loading}
          required
        />
      </Row>

      {error && <ErrorMsg>{error}</ErrorMsg>}

      <AuthBtn
        onClick={submit}
        loading={loading}
      >
        Crear cuenta
      </AuthBtn>

      <AuthSwitch>
        ¿Ya tienes cuenta?{" "}
        <button
          type="button"
          className="p220-auth-link"
          onClick={onGo}
          disabled={loading}
        >
          Inicia sesión
        </button>
      </AuthSwitch>
    </AuthShell>
  );
}