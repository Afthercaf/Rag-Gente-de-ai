import { useState, useRef, useEffect } from "react";
import { sendChat, placeOrder } from "../../api/chat";
import { logout } from "../../api/auth";
import { clearSession } from "../../utils/session";
import { nextId, getOrderSteps } from "../../utils/orderUtils";
import { useOrderStatus } from "../../hooks/useOrderStatus.js";
import { s } from "../../styles/theme";
import { MessageBubble } from "./MessageBubble";
import OrderStep from "./OrderStep";
import { TypingIndicator, SendIcon } from "./ChatUIElements";
import LocationPicker from "./LocationPicker";

export default function ChatScreen({ user, onLogout }) {
  const [messages, setMessages] = useState([
    {
      id: nextId(),
      role: "bot",
      text: `¡Hola ${user?.nombre || ""}! 🍕 Soy el asistente de **Pizzería 220**. Puedo ayudarte con el menú, promociones y pedidos. ¿En qué te ayudo?`,
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [orderForm, setOrderForm] = useState(null);
  const [showLocationPicker, setShowLocationPicker] = useState(false);
  const [pendingOrderData, setPendingOrderData] = useState(null);
  const [activeOrderId, setActiveOrderId] = useState(null);
  const [isSubmittingOrder, setIsSubmittingOrder] = useState(false); // Evita doble envío
  const lastReportedStatus = useRef(null);
  const bottomRef = useRef(null);

  const { status: orderStatus, label: orderLabel, isDone } = useOrderStatus(activeOrderId);

// ✅ CORRECTO — notifica cualquier cambio de estado
  useEffect(() => {
   if (!activeOrderId) return;
   if (orderStatus === lastReportedStatus.current) return;

    lastReportedStatus.current = orderStatus;

  // No notificar el estado inicial "pendiente" — ya se mencionó al confirmar el pedido
    if (orderStatus !== "pendiente") {
    addMsg("bot", `🔔 Actualización de tu pedido:\n${orderLabel}`);
    }

    if (isDone) setActiveOrderId(null);
    }, [orderStatus, activeOrderId, isDone, orderLabel]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, orderForm]);

  const ORDER_STEPS = orderForm
    ? getOrderSteps({
        cliente_nombre: user?.nombre,
        telefono: user?.telefono,
        gmail: user?.gmail,
        direccion: user?.direccion,
      })
    : [];

  const addMsg = (role, text, requiresAction = false) => {
    const newMsg = { id: nextId(), role, text };
    if (requiresAction && role === "bot") {
      newMsg.requiresLocation = true;
    }
    setMessages((m) => [...m, newMsg]);
  };

  const sendMessage = async (text) => {
    if (!text.trim()) return;
    addMsg("user", text);
    setInput("");



    setLoading(true);
    try {
const data = await sendChat(
  text,
  user.id
);
      addMsg("bot", data.reply);
      
      // Detectar si el bot sugiere pedido
if (data.is_order) {

  const orderText =
    data.order_details || text;

  const missingFields = [];

  if (!user?.nombre)
    missingFields.push("cliente_nombre");

  if (!user?.telefono)
    missingFields.push("telefono");

  if (!user?.gmail)
    missingFields.push("gmail");

  if (!user?.direccion)
    missingFields.push("direccion");

  setPendingOrderData({
    pedido: orderText,
    data: {
      cliente_nombre: user?.nombre || "",
      telefono: user?.telefono || "",
      gmail: user?.gmail || "",
      direccion: user?.direccion || "",
      payment_method: "efectivo",
    },
  });

  if (missingFields.length > 0) {

    setOrderForm({
      pedido: orderText,
      step: 0,
      data: {
        cliente_nombre: user?.nombre || "",
        telefono: user?.telefono || "",
        gmail: user?.gmail || "",
        direccion: user?.direccion || "",
      },
    });

    addMsg(
      "bot",
      "🛵 Necesito algunos datos para completar tu pedido."
    );

  } else {

    addMsg(
      "bot",
      "📍 Comparte tu ubicación para confirmar el pedido.",
      true
    );

  }
}
      
    } catch (err) {
      addMsg("bot", `❌ ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const extractOrderFromReply = (reply) => {
    const match = reply.match(/📝\s*\*\*PEDIDO:\*\*\s*(.+?)(?:\n|$)/);
    return match ? match[1] : reply;
  };

  const submitOrderStep = async (value) => {
    if (!orderForm || isSubmittingOrder) return;
    
    const step = ORDER_STEPS[orderForm.step];
    const newData = { ...orderForm.data, [step.key]: value };
    addMsg("user", value);

    if (orderForm.step < ORDER_STEPS.length - 1) {
      setOrderForm({ ...orderForm, step: orderForm.step + 1, data: newData });
    } else {
      // Guardar datos y abrir location picker
      setPendingOrderData({
        pedido: orderForm.pedido,
        data: {
          ...newData,
          payment_method: "efectivo"
        }
      });
      setOrderForm(null);
      
      addMsg("bot", "📍 Para completar tu pedido, necesito tu ubicación exacta.", true);
    }
  };

  // CORREGIDO: Con flag para evitar doble envío
  const handleLocationConfirm = async (location) => {
    // Evitar llamadas concurrentes
    if (isSubmittingOrder) {
      console.log("⚠️ Ya hay un pedido en proceso, ignorando...");
      return;
    }
    
    if (!pendingOrderData) {
      console.error("❌ No hay datos del pedido pendiente");
      addMsg("bot", "❌ Error: No se encontraron datos del pedido. Por favor, intenta nuevamente.");
      setShowLocationPicker(false);
      return;
    }
    
    setShowLocationPicker(false);
    setLoading(true);
    setIsSubmittingOrder(true);
    
    try {
      const orderData = pendingOrderData;
      console.log("📦 Enviando pedido:", orderData.pedido);
      console.log("👤 Datos cliente:", orderData.data);
      console.log("📍 Ubicación:", location);
      
      // Usar la función placeOrder del API
const result = await placeOrder(
  user.id,
  orderData.pedido,
  orderData.data,
  location
);
      
      console.log("📬 Respuesta del servidor:", result);
      
      if (result.success) {
        addMsg("bot", `✅ ¡Pedido #${result.order_id} confirmado!\n📍 Ubicación recibida.\n🍕 Te avisaré cuando el estado cambie.`);
        
        lastReportedStatus.current = "pendiente";
        setActiveOrderId(String(result.order_id));
        setPendingOrderData(null);
      } else {
        addMsg("bot", `❌ Error al crear el pedido: ${result.message || "Intenta nuevamente"}`);
      }
    } catch (err) {
      console.error("❌ Error al enviar pedido:", err);
      addMsg("bot", `❌ Error al procesar el pedido: ${err.message}`);
    } finally {
      setLoading(false);
      setIsSubmittingOrder(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    clearSession();
    onLogout();
  };

  return (
    <>
      <div style={s.root}>
        <div style={s.bgPattern} />
        <div style={s.shell}>
          <header style={s.header}>
            <div style={s.logoWrap}>
              <span style={s.logoEmoji}>🍕</span>
              <div>
                <div style={s.logoName}>Pizzería 220</div>
                <div style={s.logoSub}>Asistente IA · Online</div>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div style={s.userBadge}>
                <span style={s.userInitial}>{(user?.nombre || "U")[0].toUpperCase()}</span>
                <span style={s.userName}>{user?.nombre}</span>
                <span style={s.userRole}>{user?.role}</span>
              </div>
              <button onClick={handleLogout} style={s.logoutBtn} title="Cerrar sesión">⎋</button>
              <div style={s.dot} />
            </div>
          </header>

          <div style={s.feed}>
            {messages.map((msg) => (
              <div key={msg.id}>
                <MessageBubble msg={msg} />
{/* ✅ Solo mostrar botón si aún hay un pedido pendiente de ubicación */}
{msg.requiresLocation && !showLocationPicker && !loading && pendingOrderData && (
  <div style={{ marginTop: 8, marginLeft: 50 }}>
    <button
      onClick={() => setShowLocationPicker(true)}
      disabled={isSubmittingOrder}
      style={{
        backgroundColor: "#10b981",
        color: "white",
        padding: "8px 16px",
        borderRadius: 8,
        border: "none",
        cursor: isSubmittingOrder ? "not-allowed" : "pointer",
        fontSize: 14,
        fontWeight: "bold",
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        opacity: isSubmittingOrder ? 0.5 : 1
      }}
    >
      📍 Compartir mi ubicación
    </button>
  </div>
)}
              </div>
            ))}

            {orderForm && ORDER_STEPS[orderForm.step] && (
              <OrderStep step={ORDER_STEPS[orderForm.step]} onSubmit={submitOrderStep} />
            )}

            {loading && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>

          {!orderForm && (
            <div style={s.inputBar}>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage(input);
                  }
                }}
                placeholder="Pregunta sobre el menú, promos o escribe tu pedido…"
                rows={1}
                style={s.textarea}
                disabled={loading || isSubmittingOrder}
              />
              <button
                onClick={() => sendMessage(input)}
                disabled={loading || isSubmittingOrder || !input.trim()}
                style={{ ...s.sendBtn, opacity: loading || isSubmittingOrder || !input.trim() ? 0.4 : 1 }}
              >
                <SendIcon />
              </button>
            </div>
          )}
        </div>
      </div>

      {showLocationPicker && (
        <LocationPicker
          onLocationSelect={handleLocationConfirm}
          onClose={() => setShowLocationPicker(false)}
        />
      )}
    </>
  );
}