import { useEffect, useState } from "react";

import LoginScreen from "./components/auth/LoginScreen";
import RegisterScreen from "./components/auth/RegisterScreen";
import ChatScreen from "./components/chat/ChatScreen";

import { getCurrentUser } from "./api/auth";
import {
  clearSession,
  getAccessToken,
  getStoredUser,
} from "./utils/session";

export default function App() {
  const [screen, setScreen] = useState(() =>
    getAccessToken() ? "loading" : "login"
  );

  const [user, setUser] = useState(() =>
    getStoredUser()
  );

  useEffect(() => {
    const token = getAccessToken();

    if (!token) {
      clearSession();
      setUser(null);
      setScreen("login");
      return;
    }

    let active = true;

    const validateSession = async () => {
      try {
        const currentUser = await getCurrentUser();

        if (!active) return;

        const storedUser = getStoredUser();

        setUser({
          ...storedUser,
          ...currentUser,
        });

        setScreen("chat");
      } catch (error) {
        console.warn(
          "La sesión no es válida o expiró:",
          error
        );

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
     * LoginScreen/RegisterScreen ya llaman api/auth.js.
     * Ese archivo guarda access_token y user.
     *
     * No vuelvas a llamar saveSession(userData) aquí,
     * porque faltaría el token.
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