import { useEffect, useState } from "react";

import LoginScreen from "./components/auth/LoginScreen";
import RegisterScreen from "./components/auth/RegisterScreen";
import ChatScreen from "./components/chat/ChatScreen";

import { getCurrentUser } from "./api/auth";
import {
  clearSession,
} from "./utils/session";

export default function App() {
  const [screen, setScreen] = useState("loading");
  const [user, setUser] = useState(null);

  useEffect(() => {
    let active = true;

    const validateSession = async () => {
      try {
        const currentUser = await getCurrentUser();

        if (!active) return;

        if (!currentUser) {
          clearSession();
          setUser(null);
          setScreen("login");
          return;
        }

        setUser(currentUser);

        setScreen("chat");
      } catch {
        if (!active) return;

        clearSession();
        setUser(null);
        setScreen("login");
      }
    };

    validateSession();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => {
      clearSession();
      setUser(null);
      setScreen("login");
    };

    window.addEventListener(
      "p220:unauthorized",
      handleUnauthorized
    );

    return () => {
      window.removeEventListener(
        "p220:unauthorized",
        handleUnauthorized
      );
    };
  }, []);

  const handleLogin = (userData) => {
    /*
     * ✅ M-01 FIX: El access token viaja en cookie HttpOnly (nombre según ENV).
     * api/auth.js solo guarda datos básicos del usuario.
     */
    setUser(userData);
    setScreen("chat");
  };

  const handleLogout = () => {
    clearSession();
    setUser(null);
    setScreen("login");
  };

  if (screen === "loading") {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
        }}
      >
        Validando sesión…
      </div>
    );
  }

  if (screen === "login") {
    return (
      <LoginScreen
        onLogin={handleLogin}
        onGo={() => setScreen("register")}
      />
    );
  }

  if (screen === "register") {
    return (
      <RegisterScreen
        onLogin={handleLogin}
        onGo={() => setScreen("login")}
      />
    );
  }

  if (!user) {
    return null;
  }

  return (
    <ChatScreen
      user={user}
      onLogout={handleLogout}
    />
  );
}
