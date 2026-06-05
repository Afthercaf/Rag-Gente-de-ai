import { useState } from "react";
import { register } from "../../api/auth";
import { saveSession } from "../../utils/session";
import { s } from "../../styles/theme";
import { AuthShell, Field, Row, AuthBtn, AuthSwitch, ErrorMsg } from "./AuthCommon";

/**
 * @param {{ onLogin: (user) => void, onGo: () => void }} props
 */
export default function RegisterScreen({ onLogin, onGo }) {
  const [form, setForm] = useState({
    nombre: "", telefono: "", gmail: "",
    direccion: "", role: "cliente",
    password: "", confirm: "",
  });
  const [error,   setError]   = useState("");
  const [loading, setLoading] = useState(false);

  const set = (key) => (value) => setForm((f) => ({ ...f, [key]: value }));

  const submit = async () => {
    const { nombre, telefono, gmail, direccion, password, confirm } = form;
    if (!nombre || !telefono || !gmail || !direccion || !password)
      return setError("Completa todos los campos.");
    if (password !== confirm)
      return setError("Las contraseñas no coinciden.");

    setLoading(true);
    setError("");
    try {
      const data = await register(form);
      if (data.success) {
        saveSession(data.user);   // persiste en cookie
        onLogin(data.user);
      } else {
        setError(data.message || "Error al registrar.");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell title="Crear cuenta" subtitle="Regístrate para hacer pedidos">
      <Row>
        <Field label="Nombre completo" value={form.nombre}   onChange={set("nombre")}   placeholder="Juan Pérez" />
        <Field label="Teléfono"        value={form.telefono} onChange={set("telefono")} placeholder="+52 999 000 0000" type="tel" />
      </Row>
      <Field label="Correo Gmail" type="email" value={form.gmail}    onChange={set("gmail")}    placeholder="usuario@gmail.com" />
      <Field label="Dirección"                 value={form.direccion} onChange={set("direccion")} placeholder="Calle, Número, Colonia" />

      <div style={s.fieldWrap}>
        <label style={s.fieldLabel}>Rol</label>
        <select value={form.role} onChange={(e) => set("role")(e.target.value)} style={s.select}>
          <option value="cliente">Cliente</option>
          <option value="admin">Administrador</option>
          <option value="repartidor">Repartidor</option>
        </select>
      </div>

      <Row>
        <Field label="Contraseña"           type="password" value={form.password} onChange={set("password")} placeholder="••••••••" />
        <Field label="Confirmar contraseña" type="password" value={form.confirm}  onChange={set("confirm")}  placeholder="••••••••" onEnter={submit} />
      </Row>

      {error && <ErrorMsg>{error}</ErrorMsg>}
      <AuthBtn onClick={submit} loading={loading}>Crear cuenta</AuthBtn>
      <AuthSwitch>
        ¿Ya tienes cuenta?{" "}
        <span onClick={onGo} style={s.authLink}>Inicia sesión</span>
      </AuthSwitch>
    </AuthShell>
  );
}
