import axios from "axios";

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://pizzeria-backend-1.tail29c8ce.ts.net:8000" ,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 60000,
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.message ||
      (error.code === "ECONNABORTED"
        ? "Tiempo de espera agotado."
        : "No se pudo conectar con el servidor.");

    error.message = message;

    return Promise.reject(error);
  }
);

export default client;
