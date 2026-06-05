import { useState } from "react";
import { loadSession, saveSession, clearSession, isSessionValid } from "./utils/session";
import LoginScreen    from "./components/auth/LoginScreen";
import RegisterScreen from "./components/auth/RegisterScreen";
import ChatScreen     from "./components/chat/ChatScreen";

const savedSession  = loadSession();
const initialUser   = isSessionValid(savedSession) ? savedSession : null;
const initialScreen = initialUser ? "chat" : "login";

export default function App() {
  const [screen, setScreen] = useState(initialScreen);
  const [user,   setUser]   = useState(initialUser);

  const handleLogin = (userData) => {
    saveSession(userData);   // persiste al recargar
    setUser(userData);
    setScreen("chat");
  };

  const handleLogout = () => {
    clearSession();          // limpia al cerrar sesión
    setUser(null);
    setScreen("login");
  };

  if (screen === "login")
    return <LoginScreen    onLogin={handleLogin} onGo={() => setScreen("register")} />;

  if (screen === "register")
    return <RegisterScreen onLogin={handleLogin} onGo={() => setScreen("login")} />;

  return <ChatScreen user={user} onLogout={handleLogout} />;
}