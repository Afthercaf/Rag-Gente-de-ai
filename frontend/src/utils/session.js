const SESSION_KEY = 'rag_session';

export const saveSession = (sessionData) => {
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify(sessionData));
  } catch (error) {
    console.error('Error saving session:', error);
  }
};

export const loadSession = () => {
  try {
    const session = localStorage.getItem(SESSION_KEY);
    return session ? JSON.parse(session) : null;
  } catch (error) {
    console.error('Error loading session:', error);
    return null;
  }
};

export const clearSession = () => {
  try {
    localStorage.removeItem(SESSION_KEY);
  } catch (error) {
    console.error('Error clearing session:', error);
  }
};

export const isSessionValid = (session) => {
  if (!session) return false;
  // Solo necesita tener id y gmail (lo que devuelve el backend)
  if (!session.id || !session.gmail) return false;

  // Si hay expiración, verificar que no haya expirado
  if (session.expiresAt) {
    return new Date(session.expiresAt) > new Date();
  }

  return true;
};

export const updateSession = (updates) => {
  try {
    const current = loadSession();
    if (!current) return;
    const updated = { ...current, ...updates };
    saveSession(updated);
  } catch (error) {
    console.error('Error updating session:', error);
  }
};