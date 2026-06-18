import { useState, useRef, useEffect } from "react";
import { sendChat, placeOrder } from "../../api/chat";
import { logout } from "../../api/auth";
import { clearSession } from "../../utils/session";
import { nextId, getOrderSteps } from "../../utils/orderUtils";
import { useOrderStatus } from "../../hooks/useOrderStatus.js";
import { useVoiceRecognition } from "../../hooks/useVoiceRecognition";
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
  const [isSubmittingOrder, setIsSubmittingOrder] = useState(false);
  const [voiceError, setVoiceError] = useState(null);
  const lastReportedStatus = useRef(null);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const sendTimeoutRef = useRef(null);

  // ── Voice Recognition Hook ──────────────────────────────────────────────────
  const {
    isListening,
    isSupported,
    transcript,
    interimTranscript,
    toggleListening,
    stopListening,
  } = useVoiceRecognition({
    onResult: (text) => {
      if (text.trim()) {
        setInput(text);
        if (sendTimeoutRef.current) clearTimeout(sendTimeoutRef.current);
        sendTimeoutRef.current = setTimeout(() => {
          if (text.trim() && !loading && !isSubmittingOrder && !orderForm) {
            sendMessage(text.trim());
          }
          sendTimeoutRef.current = null;
        }, 500);
      }
    },
    onError: (errorMsg) => {
      setVoiceError(errorMsg);
      addMsg("bot", `🎤 ${errorMsg}`);
      setTimeout(() => {
        setVoiceError(null);
        setMessages((prev) => prev.filter((m) => m.text !== `🎤 ${errorMsg}`));
      }, 4000);
    },
    language: "es-ES",
  });

  // Actualizar input con transcripción en tiempo real
  useEffect(() => {
    if (isListening && transcript) setInput(transcript);
  }, [transcript, isListening]);

  // Limpiar timeout al desmontar
  useEffect(() => {
    return () => {
      if (sendTimeoutRef.current) clearTimeout(sendTimeoutRef.current);
    };
  }, []);

  const addMsg = (role, text, requiresAction = false) => {
    const newMsg = { id: nextId(), role, text };
    if (requiresAction && role === "bot") newMsg.requiresLocation = true;
    setMessages((m) => [...m, newMsg]);
  };

  const { status: orderStatus, label: orderLabel, isDone } = useOrderStatus(activeOrderId);

  useEffect(() => {
    if (!activeOrderId) return;
    if (orderStatus === lastReportedStatus.current) return;
    lastReportedStatus.current = orderStatus;
    if (orderStatus !== "pendiente") addMsg("bot", `🔔 Actualización de tu pedido:\n${orderLabel}`);
  }, [orderStatus, activeOrderId, orderLabel]);

  useEffect(() => { if (isDone) setActiveOrderId(null); }, [isDone]);

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

  const sendMessage = async (text) => {
    if (!text.trim()) return;
    if (isListening) stopListening();
    addMsg("user", text);
    setInput("");
    setLoading(true);
    try {
      const data = await sendChat(text, user.id);
      addMsg("bot", data.reply);
      if (data.is_order) {
        const orderText = data.order_details?.raw || text;
        const orderTotal = data.order_details?.total || null;
        const missingFields = [];
        if (!user?.nombre)    missingFields.push("cliente_nombre");
        if (!user?.telefono)  missingFields.push("telefono");
        if (!user?.gmail)     missingFields.push("gmail");
        if (!user?.direccion) missingFields.push("direccion");
        setPendingOrderData({
          pedido: orderText,
          data: {
            cliente_nombre: user?.nombre || "",
            telefono: user?.telefono || "",
            gmail: user?.gmail || "",
            direccion: user?.direccion || "",
            total: orderTotal,
            payment_method: "efectivo",
          },
        });
        if (missingFields.length > 0) {
          setOrderForm({
            pedido: orderText, step: 0,
            data: { cliente_nombre: user?.nombre || "", telefono: user?.telefono || "", gmail: user?.gmail || "", direccion: user?.direccion || "", total: orderTotal },
          });
          addMsg("bot", "🛵 Necesito algunos datos para completar tu pedido.");
        } else {
          addMsg("bot", "📍 Comparte tu ubicación para confirmar el pedido.", true);
        }
      }
    } catch (err) {
      addMsg("bot", `❌ ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const normalizeOrderText = (pedido) => {
    if (typeof pedido === "string") return pedido.trim();
    if (pedido && typeof pedido.raw === "string") return pedido.raw.trim();
    if (pedido) return JSON.stringify(pedido).trim();
    return "";
  };

  const submitOrderStep = async (value) => {
    if (!orderForm || isSubmittingOrder) return;
    const step = ORDER_STEPS[orderForm.step];
    const newData = { ...orderForm.data, [step.key]: value };
    addMsg("user", value);
    if (orderForm.step < ORDER_STEPS.length - 1) {
      setOrderForm({ ...orderForm, step: orderForm.step + 1, data: newData });
    } else {
      setPendingOrderData({ pedido: normalizeOrderText(orderForm.pedido), data: { ...newData, payment_method: "efectivo" } });
      setOrderForm(null);
      addMsg("bot", "📍 Para completar tu pedido, necesito tu ubicación exacta.", true);
    }
  };

  const handleLocationConfirm = async (location) => {
    if (isSubmittingOrder) return;
    if (!pendingOrderData) {
      addMsg("bot", "❌ Error: No se encontraron datos del pedido. Por favor, intenta nuevamente.");
      setShowLocationPicker(false);
      return;
    }
    setShowLocationPicker(false);
    setLoading(true);
    setIsSubmittingOrder(true);
    try {
      const orderData = pendingOrderData;
      const pedidoText = normalizeOrderText(orderData.pedido);
      const result = await placeOrder(user.id, pedidoText, orderData.data, location);
      if (result.success) {
        addMsg("bot", `✅ ¡Pedido #${result.order_id} confirmado!${result.total ? `\n💰 Total: ${result.total}` : ""}\n📍 Ubicación recibida.\n🍕 Te avisaré cuando el estado cambie.`);
        lastReportedStatus.current = "pendiente";
        setActiveOrderId(String(result.order_id));
        setPendingOrderData(null);
      } else {
        addMsg("bot", `❌ Error al crear el pedido: ${result.message || "Intenta nuevamente"}`);
      }
    } catch (err) {
      addMsg("bot", `❌ Error al procesar el pedido: ${err.message}`);
    } finally {
      setLoading(false);
      setIsSubmittingOrder(false);
    }
  };

  const handleLogout = async () => { await logout(); clearSession(); onLogout(); };

  const handleVoiceClick = () => {
    if (isListening) {
      stopListening();
    } else {
      if (input) setInput("");
      toggleListening();
    }
  };

  // ── Estilo dinámico del textarea ────────────────────────────────────────────
  const textareaStyle = {
    ...s.textarea,
    ...(isListening ? s.textareaListening : {}),
  };

  // ── Estilo dinámico del mic button ─────────────────────────────────────────
  const micBtnStyle = {
    ...s.micBtn,
    ...(isListening ? s.micBtnActive : {}),
  };

  return (
    <>
      <div style={s.root}>
        <div style={s.bgPattern} />
        <div style={s.shell}>

          {/* ── Header ────────────────────────────────────────────────────────── */}
          <header style={s.header}>
            <div style={s.logoWrap}>
              <span style={s.logoEmoji}>🍕</span>
              <div>
                <div style={s.logoName}>Pizzería 220</div>
                <div style={s.logoSub}>
                  <span style={s.logoSubDot} />
                  Asistente IA · Online
                </div>
              </div>
            </div>
            <div style={{ display:"flex", alignItems:"center", gap:10 }}>
              <div style={s.userBadge}>
                <span style={s.userInitial}>{(user?.nombre || "U")[0].toUpperCase()}</span>
                <span style={s.userName}>{user?.nombre}</span>
                <span style={s.userRole}>{user?.role}</span>
              </div>
              <button onClick={handleLogout} style={s.logoutBtn} title="Cerrar sesión">⎋</button>
              <div style={s.dot} />
            </div>
          </header>

          {/* ── Feed ──────────────────────────────────────────────────────────── */}
          <div style={s.feed}>
            {messages.map((msg) => (
              <div key={msg.id}>
                <MessageBubble msg={msg} />
                {msg.requiresLocation && !showLocationPicker && !loading && pendingOrderData && (
                  <div style={{ marginTop:8, marginLeft:50 }}>
                    <button
                      onClick={() => setShowLocationPicker(true)}
                      disabled={isSubmittingOrder}
                      style={{
                        backgroundColor:"#10b981", color:"white",
                        padding:"8px 16px", borderRadius:8, border:"none",
                        cursor: isSubmittingOrder ? "not-allowed" : "pointer",
                        fontSize:14, fontWeight:"bold",
                        display:"inline-flex", alignItems:"center", gap:8,
                        opacity: isSubmittingOrder ? 0.5 : 1,
                        boxShadow:"0 2px 10px rgba(16,185,129,.25)",
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

          {/* ── Input bar ─────────────────────────────────────────────────────── */}
          {!orderForm && (
            <div style={s.inputBar}>

              {/* Botón de voz */}
              {isSupported && (
                <button
                  onClick={handleVoiceClick}
                  disabled={loading || isSubmittingOrder}
                  style={micBtnStyle}
                  title={isListening ? "Detener grabación" : "Activar voz"}
                >
                  {/* Ripples — solo visibles mientras escucha */}
                  {isListening && (
                    <>
                      <span style={s.micRipple} />
                      <span style={s.micRipple2} />
                    </>
                  )}

                  {/* Ícono o barras de onda */}
                  {isListening ? (
                    <span style={s.micWave}>
                      {[s.micWaveBar1, s.micWaveBar2, s.micWaveBar3, s.micWaveBar4, s.micWaveBar5].map((anim, i) => (
                        <span key={i} style={{ ...s.micWaveBar, ...anim }} />
                      ))}
                    </span>
                  ) : (
                    <span style={{ fontSize:17 }}>🎤</span>
                  )}
                </button>
              )}

              <textarea
                ref={inputRef}
                value={isListening ? `${transcript || ""} ${interimTranscript || ""}`.trim() : input}
                onChange={(e) => { if (!isListening) setInput(e.target.value); }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey && !isListening) {
                    e.preventDefault();
                    sendMessage(input);
                  }
                }}
                placeholder={isListening ? "🎤 Habla ahora..." : "Pregunta sobre el menú, promos o escribe tu pedido…"}
                rows={1}
                style={textareaStyle}
                disabled={loading || isSubmittingOrder || isListening}
              />

              <button
                onClick={() => sendMessage(input)}
                disabled={loading || isSubmittingOrder || !input.trim() || isListening}
                style={{ ...s.sendBtn, opacity: (loading || isSubmittingOrder || !input.trim() || isListening) ? 0.35 : 1 }}
              >
                <SendIcon />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ── Toast flotante de escucha ──────────────────────────────────────────── */}
      {isListening && (
        <div style={s.listenToast}>
          <span style={s.listenDot} />
          <span>Escuchando...</span>
          {interimTranscript && (
            <span style={s.listenInterim}>"{interimTranscript}"</span>
          )}
          <button
            style={s.cancelBtn}
            onClick={() => {
              stopListening();
              setInput("");
              if (sendTimeoutRef.current) {
                clearTimeout(sendTimeoutRef.current);
                sendTimeoutRef.current = null;
              }
            }}
          >
            Cancelar
          </button>
        </div>
      )}

      {/* ── Voz no soportada ──────────────────────────────────────────────────── */}
      {!isSupported && (
        <div style={{
          position:"fixed", bottom:100, left:"50%", transform:"translateX(-50%)",
          background:"rgba(239,68,68,.9)", color:"#fff",
          padding:"10px 20px", borderRadius:12, fontSize:13, zIndex:1000,
          backdropFilter:"blur(10px)",
        }}>
          ⚠️ Tu navegador no soporta reconocimiento de voz. Usa Chrome o Edge.
        </div>
      )}

      {/* ── Location Picker ───────────────────────────────────────────────────── */}
      {showLocationPicker && (
        <LocationPicker
          onLocationSelect={handleLocationConfirm}
          onClose={() => setShowLocationPicker(false)}
        />
      )}
    </>
  );
}