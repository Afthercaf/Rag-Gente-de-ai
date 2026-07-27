// import { useState, useRef, useEffect } from "react";
// import { sendChat, placeOrder } from "../../api/chat";
// import { logout } from "../../api/auth";
// import { clearSession } from "../../utils/session";
// import { nextId, getOrderSteps } from "../../utils/orderUtils";
// import { useOrderStatus } from "../../hooks/useOrderStatus.js";
// import { useVoiceRecognition } from "../../hooks/useVoiceRecognition";
// import { s } from "../../styles/theme";
// import { MessageBubble } from "./MessageBubble";
// import OrderStep from "./OrderStep";
// import { TypingIndicator, SendIcon } from "./ChatUIElements";
// import LocationPicker from "./LocationPicker";

// export default function ChatScreen({ user, onLogout }) {
//   const [messages, setMessages] = useState([
//     {
//       id: nextId(),
//       role: "bot",
//       text: `¡Hola ${user?.nombre || ""}! 🍕 Soy el asistente de **Pizzería 220**. Puedo ayudarte con el menú, promociones y pedidos. ¿En qué te ayudo?`,
//     },
//   ]);
//   const [input, setInput] = useState("");
//   const [loading, setLoading] = useState(false);
//   const [orderForm, setOrderForm] = useState(null);
//   const [showLocationPicker, setShowLocationPicker] = useState(false);
//   const [pendingOrderData, setPendingOrderData] = useState(null);
//   const [activeOrderId, setActiveOrderId] = useState(null);
//   const [isSubmittingOrder, setIsSubmittingOrder] = useState(false);
//   const [voiceError, setVoiceError] = useState(null);
//   const lastReportedStatus = useRef(null);
//   const bottomRef = useRef(null);
//   const inputRef = useRef(null);
//   const sendTimeoutRef = useRef(null);

//   // ── Voice Recognition Hook ──────────────────────────────────────────────────
//   const {
//     isListening,
//     isSupported,
//     transcript,
//     interimTranscript,
//     toggleListening,
//     stopListening,
//   } = useVoiceRecognition({
//     onResult: (text) => {
//       if (text.trim()) {
//         setInput(text);
//         if (sendTimeoutRef.current) clearTimeout(sendTimeoutRef.current);
//         sendTimeoutRef.current = setTimeout(() => {
//           if (text.trim() && !loading && !isSubmittingOrder && !orderForm) {
//             sendMessage(text.trim());
//           }
//           sendTimeoutRef.current = null;
//         }, 500);
//       }
//     },
//     onError: (errorMsg) => {
//       setVoiceError(errorMsg);
//       addMsg("bot", `🎤 ${errorMsg}`);
//       setTimeout(() => {
//         setVoiceError(null);
//         setMessages((prev) => prev.filter((m) => m.text !== `🎤 ${errorMsg}`));
//       }, 4000);
//     },
//     language: "es-ES",
//   });

//   // Actualizar input con transcripción en tiempo real
//   useEffect(() => {
//     if (isListening && transcript) setInput(transcript);
//   }, [transcript, isListening]);

//   // Limpiar timeout al desmontar
//   useEffect(() => {
//     return () => {
//       if (sendTimeoutRef.current) clearTimeout(sendTimeoutRef.current);
//     };
//   }, []);

//   const addMsg = (role, text, requiresAction = false) => {
//     const newMsg = { id: nextId(), role, text };
//     if (requiresAction && role === "bot") newMsg.requiresLocation = true;
//     setMessages((m) => [...m, newMsg]);
//   };

//   const { status: orderStatus, label: orderLabel, isDone } = useOrderStatus(activeOrderId);

//   useEffect(() => {
//     if (!activeOrderId) return;
//     if (orderStatus === lastReportedStatus.current) return;
//     lastReportedStatus.current = orderStatus;
//     if (orderStatus !== "pendiente") addMsg("bot", `🔔 Actualización de tu pedido:\n${orderLabel}`);
//   }, [orderStatus, activeOrderId, orderLabel]);

//   useEffect(() => { if (isDone) setActiveOrderId(null); }, [isDone]);

//   useEffect(() => {
//     bottomRef.current?.scrollIntoView({ behavior: "smooth" });
//   }, [messages, orderForm]);

//   const ORDER_STEPS = orderForm
//     ? getOrderSteps({
//         cliente_nombre: user?.nombre,
//         telefono: user?.telefono,
//         gmail: user?.gmail,
//         direccion: user?.direccion,
//       })
//     : [];

//   const sendMessage = async (text) => {
//     if (!text.trim()) return;
//     if (isListening) stopListening();
//     addMsg("user", text);
//     setInput("");
//     setLoading(true);
//     try {
//       const data = await sendChat(text, user.id);
//       addMsg("bot", data.reply);
//       if (data.is_order) {
//         const orderText = data.order_details?.raw || text;
//         const orderTotal = data.order_details?.total || null;
//         const missingFields = [];
//         if (!user?.nombre)    missingFields.push("cliente_nombre");
//         if (!user?.telefono)  missingFields.push("telefono");
//         if (!user?.gmail)     missingFields.push("gmail");
//         if (!user?.direccion) missingFields.push("direccion");
//         setPendingOrderData({
//           pedido: orderText,
//           data: {
//             cliente_nombre: user?.nombre || "",
//             telefono: user?.telefono || "",
//             gmail: user?.gmail || "",
//             direccion: user?.direccion || "",
//             total: orderTotal,
//             payment_method: "efectivo",
//           },
//         });
//         if (missingFields.length > 0) {
//           setOrderForm({
//             pedido: orderText, step: 0,
//             data: { cliente_nombre: user?.nombre || "", telefono: user?.telefono || "", gmail: user?.gmail || "", direccion: user?.direccion || "", total: orderTotal },
//           });
//           addMsg("bot", "🛵 Necesito algunos datos para completar tu pedido.");
//         } else {
//           addMsg("bot", "📍 Comparte tu ubicación para confirmar el pedido.", true);
//         }
//       }
//     } catch (err) {
//       addMsg("bot", `❌ ${err.message}`);
//     } finally {
//       setLoading(false);
//     }
//   };

//   const normalizeOrderText = (pedido) => {
//     if (typeof pedido === "string") return pedido.trim();
//     if (pedido && typeof pedido.raw === "string") return pedido.raw.trim();
//     if (pedido) return JSON.stringify(pedido).trim();
//     return "";
//   };

//   const submitOrderStep = async (value) => {
//     if (!orderForm || isSubmittingOrder) return;
//     const step = ORDER_STEPS[orderForm.step];
//     const newData = { ...orderForm.data, [step.key]: value };
//     addMsg("user", value);
//     if (orderForm.step < ORDER_STEPS.length - 1) {
//       setOrderForm({ ...orderForm, step: orderForm.step + 1, data: newData });
//     } else {
//       setPendingOrderData({ pedido: normalizeOrderText(orderForm.pedido), data: { ...newData, payment_method: "efectivo" } });
//       setOrderForm(null);
//       addMsg("bot", "📍 Para completar tu pedido, necesito tu ubicación exacta.", true);
//     }
//   };

//   const handleLocationConfirm = async (location) => {
//     if (isSubmittingOrder) return;
//     if (!pendingOrderData) {
//       addMsg("bot", "❌ Error: No se encontraron datos del pedido. Por favor, intenta nuevamente.");
//       setShowLocationPicker(false);
//       return;
//     }
//     setShowLocationPicker(false);
//     setLoading(true);
//     setIsSubmittingOrder(true);
//     try {
//       const orderData = pendingOrderData;
//       const pedidoText = normalizeOrderText(orderData.pedido);
//       const result = await placeOrder(pedidoText, orderData.data, location);
//       if (result.success) {
//         addMsg("bot", `✅ ¡Pedido #${result.order_id} confirmado!${result.total ? `\n💰 Total: ${result.total}` : ""}\n📍 Ubicación recibida.\n🍕 Te avisaré cuando el estado cambie.`);
//         lastReportedStatus.current = "pendiente";
//         setActiveOrderId(String(result.order_id));
//         setPendingOrderData(null);
//       } else {
//         addMsg("bot", `❌ Error al crear el pedido: ${result.message || "Intenta nuevamente"}`);
//       }
//     } catch (err) {
//       addMsg("bot", `❌ Error al procesar el pedido: ${err.message}`);
//     } finally {
//       setLoading(false);
//       setIsSubmittingOrder(false);
//     }
//   };

//   const handleLogout = async () => { await logout(); clearSession(); onLogout(); };

//   const handleVoiceClick = () => {
//     if (isListening) {
//       stopListening();
//     } else {
//       if (input) setInput("");
//       toggleListening();
//     }
//   };

//   // ── Estilo dinámico del textarea ────────────────────────────────────────────
//   const textareaStyle = {
//     ...s.textarea,
//     ...(isListening ? s.textareaListening : {}),
//   };

//   // ── Estilo dinámico del mic button ─────────────────────────────────────────
//   const micBtnStyle = {
//     ...s.micBtn,
//     ...(isListening ? s.micBtnActive : {}),
//   };

//   return (
//     <>
//       <div style={s.root}>
//         <div style={s.bgPattern} />
//         <div style={s.shell}>

//           {/* ── Header ────────────────────────────────────────────────────────── */}
//           <header style={s.header}>
//             <div style={s.logoWrap}>
//               <span style={s.logoEmoji}>🍕</span>
//               <div>
//                 <div style={s.logoName}>Pizzería 220</div>
//                 <div style={s.logoSub}>
//                   <span style={s.logoSubDot} />
//                   Asistente IA · Online
//                 </div>
//               </div>
//             </div>
//             <div style={{ display:"flex", alignItems:"center", gap:10 }}>
//               <div style={s.userBadge}>
//                 <span style={s.userInitial}>{(user?.nombre || "U")[0].toUpperCase()}</span>
//                 <span style={s.userName}>{user?.nombre}</span>
//                 <span style={s.userRole}>{user?.role}</span>
//               </div>
//               <button onClick={handleLogout} style={s.logoutBtn} title="Cerrar sesión">⎋</button>
//               <div style={s.dot} />
//             </div>
//           </header>

//           {/* ── Feed ──────────────────────────────────────────────────────────── */}
//           <div style={s.feed}>
//             {messages.map((msg) => (
//               <div key={msg.id}>
//                 <MessageBubble msg={msg} />
//                 {msg.requiresLocation && !showLocationPicker && !loading && pendingOrderData && (
//                   <div style={{ marginTop:8, marginLeft:50 }}>
//                     <button
//                       onClick={() => setShowLocationPicker(true)}
//                       disabled={isSubmittingOrder}
//                       style={{
//                         backgroundColor:"#10b981", color:"white",
//                         padding:"8px 16px", borderRadius:8, border:"none",
//                         cursor: isSubmittingOrder ? "not-allowed" : "pointer",
//                         fontSize:14, fontWeight:"bold",
//                         display:"inline-flex", alignItems:"center", gap:8,
//                         opacity: isSubmittingOrder ? 0.5 : 1,
//                         boxShadow:"0 2px 10px rgba(16,185,129,.25)",
//                       }}
//                     >
//                       📍 Compartir mi ubicación
//                     </button>
//                   </div>
//                 )}
//               </div>
//             ))}

//             {orderForm && ORDER_STEPS[orderForm.step] && (
//               <OrderStep step={ORDER_STEPS[orderForm.step]} onSubmit={submitOrderStep} />
//             )}

//             {loading && <TypingIndicator />}
//             <div ref={bottomRef} />
//           </div>

//           {/* ── Input bar ─────────────────────────────────────────────────────── */}
//           {!orderForm && (
//             <div style={s.inputBar}>

//               {/* Botón de voz */}
//               {isSupported && (
//                 <button
//                   onClick={handleVoiceClick}
//                   disabled={loading || isSubmittingOrder}
//                   style={micBtnStyle}
//                   title={isListening ? "Detener grabación" : "Activar voz"}
//                 >
//                   {/* Ripples — solo visibles mientras escucha */}
//                   {isListening && (
//                     <>
//                       <span style={s.micRipple} />
//                       <span style={s.micRipple2} />
//                     </>
//                   )}

//                   {/* Ícono o barras de onda */}
//                   {isListening ? (
//                     <span style={s.micWave}>
//                       {[s.micWaveBar1, s.micWaveBar2, s.micWaveBar3, s.micWaveBar4, s.micWaveBar5].map((anim, i) => (
//                         <span key={i} style={{ ...s.micWaveBar, ...anim }} />
//                       ))}
//                     </span>
//                   ) : (
//                     <span style={{ fontSize:17 }}>🎤</span>
//                   )}
//                 </button>
//               )}

//               <textarea
//                 ref={inputRef}
//                 value={isListening ? `${transcript || ""} ${interimTranscript || ""}`.trim() : input}
//                 onChange={(e) => { if (!isListening) setInput(e.target.value); }}
//                 onKeyDown={(e) => {
//                   if (e.key === "Enter" && !e.shiftKey && !isListening) {
//                     e.preventDefault();
//                     sendMessage(input);
//                   }
//                 }}
//                 placeholder={isListening ? "🎤 Habla ahora..." : "Pregunta sobre el menú, promos o escribe tu pedido…"}
//                 rows={1}
//                 style={textareaStyle}
//                 disabled={loading || isSubmittingOrder || isListening}
//               />

//               <button
//                 onClick={() => sendMessage(input)}
//                 disabled={loading || isSubmittingOrder || !input.trim() || isListening}
//                 style={{ ...s.sendBtn, opacity: (loading || isSubmittingOrder || !input.trim() || isListening) ? 0.35 : 1 }}
//               >
//                 <SendIcon />
//               </button>
//             </div>
//           )}
//         </div>
//       </div>

//       {/* ── Toast flotante de escucha ──────────────────────────────────────────── */}
//       {isListening && (
//         <div style={s.listenToast}>
//           <span style={s.listenDot} />
//           <span>Escuchando...</span>
//           {interimTranscript && (
//             <span style={s.listenInterim}>"{interimTranscript}"</span>
//           )}
//           <button
//             style={s.cancelBtn}
//             onClick={() => {
//               stopListening();
//               setInput("");
//               if (sendTimeoutRef.current) {
//                 clearTimeout(sendTimeoutRef.current);
//                 sendTimeoutRef.current = null;
//               }
//             }}
//           >
//             Cancelar
//           </button>
//         </div>
//       )}

//       {/* ── Voz no soportada ──────────────────────────────────────────────────── */}
//       {!isSupported && (
//         <div style={{
//           position:"fixed", bottom:100, left:"50%", transform:"translateX(-50%)",
//           background:"rgba(239,68,68,.9)", color:"#fff",
//           padding:"10px 20px", borderRadius:12, fontSize:13, zIndex:1000,
//           backdropFilter:"blur(10px)",
//         }}>
//           ⚠️ Tu navegador no soporta reconocimiento de voz. Usa Chrome o Edge.
//         </div>
//       )}

//       {/* ── Location Picker ───────────────────────────────────────────────────── */}
//       {showLocationPicker && (
//         <LocationPicker
//           onLocationSelect={handleLocationConfirm}
//           onClose={() => setShowLocationPicker(false)}
//         />
//       )}
//     </>
//   );
// }







import { useState, useRef, useEffect } from "react";
import { sendChat, placeOrder } from "../../api/chat";
import { logout } from "../../api/auth";
import { clearSession } from "../../utils/session";
import { nextId, getOrderSteps } from "../../utils/orderUtils";
import { useOrderStatus } from "../../hooks/useOrderStatus.js";
import { useVoiceRecognition } from "../../hooks/useVoiceRecognition";
import "../../styles/theme.css";
import { MessageBubble } from "./MessageBubble";
import OrderStep from "./OrderStep";
import { TypingIndicator, SendIcon } from "./ChatUIElements";
import LocationPicker from "./LocationPicker";

const AVAILABLE_EXTRAS = [
  { name: "Queso extra", price: "$45.00 MXN" },
  { name: "Orilla de queso", price: "$50.00 MXN" },
  { name: "Pepperoni", price: "$45.00 MXN" },
  { name: "Pimiento", price: "$45.00 MXN" },
  { name: "Cebolla", price: "$45.00 MXN" },
  { name: "Aceitunas y atún", price: "$45.00 MXN" },
];

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
  const [extrasPrompt, setExtrasPrompt] = useState(null);
  const [extrasInput, setExtrasInput] = useState("");
  const [selectedExtras, setSelectedExtras] = useState([]);
  const [beverageQuantity, setBeverageQuantity] = useState(1);
  const [inputHint, setInputHint] = useState("");
  const [handledActionMessages, setHandledActionMessages] = useState([]);
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

  // El cliente API emite este evento cuando el servidor responde 401.
  useEffect(() => {
    const handleUnauthorized = () => {
      clearSession();
      onLogout();
    };

    window.addEventListener("p220:unauthorized", handleUnauthorized);

    return () => {
      window.removeEventListener(
        "p220:unauthorized",
        handleUnauthorized
      );
    };
  }, [onLogout]);

  // Reinicia la selección de extras cada vez que aparece un nuevo prompt.
  useEffect(() => {
    setSelectedExtras([]);
  }, [extrasPrompt?.messageId]);

  const addMsg = (role, text, requiresAction = false, extra = {}) => {
    const newMsg = { id: nextId(), role, text, ...extra };
    if (requiresAction && role === "bot") newMsg.requiresLocation = true;
    setMessages((m) => [...m, newMsg]);
    return newMsg;
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

  const isPaymentPrompt = (reply = "") => {
    const normalized = reply
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");

    return (
      normalized.includes("como deseas pagar") ||
      normalized.includes("como vas a pagar") ||
      normalized.includes("metodo de pago") ||
      normalized.includes("elige tu metodo de pago")
    );
  };

  const isLocationPrompt = (reply = "", data = {}) => {
    if (
      data.location_required === true ||
      data.awaiting_location === true ||
      data.requires_location === true
    ) {
      return true;
    }

    const normalized = String(reply || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");

    return (
      normalized.includes("necesito tu ubicacion exacta") ||
      normalized.includes("comparte tu ubicacion exacta") ||
      normalized.includes("compartir mi ubicacion") ||
      (
        normalized.includes("para completar tu pedido") &&
        normalized.includes("ubicacion")
      )
    );
  };

  const isOrderDraft = (reply = "") => {
    const normalized = reply
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");

    return normalized.includes("confirmas tu pedido");
  };

  const isExtrasDecisionPrompt = (reply = "") => {
    const normalized = String(reply || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");

    return (
      normalized.includes("deseas agregar extras a alguna de las pizzas") ||
      normalized.includes("deseas agregar extras a esta pizza") ||
      (
        (
          normalized.includes("selecciona si") ||
          normalized.includes("responde si")
        ) &&
        normalized.includes("continuar sin extras")
      )
    );
  };

  const isTargetedExtrasPrompt = (reply = "") => {
    const normalized = String(reply || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");

    return (
      normalized.includes("indica a cuales pizzas deseas agregar extras") &&
      normalized.includes("cuantas unidades") &&
      normalized.includes("cuales extras")
    );
  };

  const extractRegisteredProducts = (reply = "") => {
    const products = [];
    const regex = /[•\-]\s*(\d+)\s*[×x]\s*Pizza\s+([^\n]+)/gi;
    let match;

    while ((match = regex.exec(reply)) !== null) {
      products.push({
        quantity: Number(match[1]),
        name: match[2].trim(),
      });
    }

    return products;
  };

  const markActionHandled = (messageId) => {
    setHandledActionMessages((current) =>
      current.includes(messageId)
        ? current
        : [...current, messageId]
    );
  };

  const handleExtrasDecision = (decision, msg) => {
    markActionHandled(msg.id);
    setExtrasPrompt(null);
    setExtrasInput("");
    setSelectedExtras([]);
    setInputHint("");

    // El backend debe recibir la decisión para pasar a
    // awaiting_targeted_extras.
    sendMessage(decision === "si" ? "sí" : "no");
  };

  const getExtrasPromptTotal = (prompt) =>
    (prompt?.products || []).reduce(
      (total, product) => total + Number(product.quantity || 0),
      0
    );

  const isSinglePizzaExtrasPrompt = (prompt) =>
    getExtrasPromptTotal(prompt) === 1 &&
    (prompt?.products || []).length === 1;

  const addBeveragesDuringExtras = () => {
    const quantity = Math.max(
      1,
      Math.min(20, Number(beverageQuantity) || 1)
    );

    if (loading) return;

    setBeverageQuantity(quantity);
    sendMessage(`agrega ${quantity} refresco${quantity === 1 ? "" : "s"}`);
  };

  const applySinglePizzaAllExtras = () => {
    if (!extrasPrompt || loading) return;

    const product = extrasPrompt.products?.[0];
    if (!product) return;

    setExtrasPrompt(null);
    setExtrasInput("");
    setSelectedExtras([]);
    setInputHint("");
    sendMessage(`1 ${product.name} con todo`);
  };

  const toggleExtra = (extraName) => {
    setSelectedExtras((current) =>
      current.includes(extraName)
        ? current.filter((e) => e !== extraName)
        : [...current, extraName]
    );
  };

  const confirmSinglePizzaExtras = () => {
    if (!extrasPrompt || loading || selectedExtras.length === 0) return;

    const product = extrasPrompt.products?.[0];
    if (!product) return;

    const command = `1 ${product.name} con ${selectedExtras
      .join(" y ")
      .toLowerCase()}`;

    setExtrasPrompt(null);
    setExtrasInput("");
    setSelectedExtras([]);
    setInputHint("");
    sendMessage(command);
  };

  const submitExtrasDescription = () => {
    const value = extrasInput
      .trim()
      .replace(/\bPizza\s+/gi, "")
      .replace(/\s+/g, " ");

    if (!value || loading) return;

    setExtrasPrompt(null);
    setExtrasInput("");
    setInputHint("");
    sendMessage(value);
  };

  const handleOrderConfirmation = (decision, msg) => {
    markActionHandled(msg.id);

    if (decision === "si") {
      setInputHint("");
      sendMessage("confirmar");
      return;
    }

    setInputHint(
      "Escribe qué deseas agregar o cambiar. Ej. Agrega 2 refrescos o cambia una Pepperoni por Margarita."
    );

    requestAnimationFrame(() => {
      inputRef.current?.focus();
    });
  };

  const sendMessage = async (text) => {
    if (!text.trim()) return;

    setInputHint("");

    if (isListening) stopListening();

    addMsg("user", text);
    setInput("");
    setLoading(true);

    try {
      const data = await sendChat(text);

      const locationPrompt = isLocationPrompt(data.reply, data);
      const extrasDecisionPrompt = isExtrasDecisionPrompt(data.reply);
      const targetedExtrasPrompt = isTargetedExtrasPrompt(data.reply);
      const extrasProducts =
        extrasDecisionPrompt || targetedExtrasPrompt
          ? extractRegisteredProducts(data.reply)
          : [];
      const orderConfirmationPrompt =
        data.is_order === true && isOrderDraft(data.reply);

      // Agregamos metadatos de acciones para mostrar botones en el frontend.
      const botMessage = addMsg("bot", data.reply, locationPrompt, {
        requiresExtrasDecision: extrasDecisionPrompt,
        extrasProducts,
        requiresOrderConfirmation: orderConfirmationPrompt,
      });

      if (targetedExtrasPrompt) {
        setExtrasPrompt({
          messageId: botMessage?.id || Date.now(),
          products: extrasProducts,
        });
        setExtrasInput("");
      }

      const paymentPrompt =
        data.payment_required === true ||
        data.awaiting_payment === true ||
        isPaymentPrompt(data.reply);

      const orderDraft = data.is_order && isOrderDraft(data.reply);

      /*
       * 1. Cuando llega el resumen del pedido, solo guardamos sus datos.
       *    NO abrimos todavía los métodos de pago.
       */
      if (data.is_order && data.order_details) {
        const orderText = data.order_details.raw || text;
        const orderTotal = data.order_details.total || null;

        const nextPendingOrder = {
          pedido: orderText,
          data: {
            cliente_nombre: user?.nombre || "",
            telefono: user?.telefono || "",
            gmail: user?.gmail || "",
            direccion: user?.direccion || "",
            total: orderTotal,
            payment_method:
              data.payment_method ||
              pendingOrderData?.data?.payment_method ||
              "",
          },
        };

        setPendingOrderData(nextPendingOrder);
      }

      /*
       * 2. Si el backend solicita ubicación, cerramos el selector de pago
       *    y conservamos los datos del pedido para enviarlos cuando el
       *    usuario confirme su ubicación.
       */
      if (locationPrompt) {
        setOrderForm(null);

        setPendingOrderData((current) => {
          if (!current) {
            return current;
          }

          const paymentMethod =
            data.payment_method ||
            current.data?.payment_method ||
            "efectivo";

          const updated = {
            ...current,
            data: {
              ...current.data,
              payment_method: paymentMethod,
            },
          };

          return updated;
        });
      }

      /*
       * 3. El formulario se abre únicamente cuando el backend ya confirmó
       *    el pedido y solicita el método de pago.
       *
       *    El mensaje del backend ya pregunta cómo pagar, por eso NO
       *    agregamos otro mensaje "¿Cómo vas a pagar?" desde el frontend.
       */
      else if (paymentPrompt) {
        const storedOrder = pendingOrderData;

        const orderText =
          data.order_details?.raw ||
          storedOrder?.pedido ||
          text;

        const orderTotal =
          data.order_details?.total ||
          storedOrder?.data?.total ||
          null;

        const formSetup = {
          pedido: orderText,
          step: 0,
          data: {
            cliente_nombre: user?.nombre || "",
            telefono: user?.telefono || "",
            gmail: user?.gmail || "",
            direccion: user?.direccion || "",
            total: orderTotal,
          },
        };

        setPendingOrderData(formSetup);
        setOrderForm(formSetup);
      } else if (orderDraft) {
        /*
         * El resumen todavía espera confirmación.
         * Aseguramos que no quede abierto un formulario viejo.
         */
        setOrderForm(null);
      }
    } catch (err) {
      let message = "Error al procesar el pedido";

      if (err?.message) {
        message = err.message;
      } else if (typeof err === "string") {
        message = err;
      }

      addMsg("bot", `❌ ${message}`);
    } finally {
      setLoading(false);
    }
  };


  const normalizeOrderText = (pedido) => {
    let result = "";
    if (typeof pedido === "string") result = pedido.trim();
    else if (pedido && typeof pedido.raw === "string") result = pedido.raw.trim();
    else if (pedido) result = JSON.stringify(pedido).trim();
    
    return result;
  };

  const submitOrderStep = async (value) => {
    if (!orderForm || isSubmittingOrder) return;
    const step = ORDER_STEPS[orderForm.step];
    const newData = { ...orderForm.data, [step.key]: value };
    
    addMsg("user", value);

    if (orderForm.step < ORDER_STEPS.length - 1) {
      const nextFormState = { ...orderForm, step: orderForm.step + 1, data: newData };
      setOrderForm(nextFormState);
    } else {
      const finalPendingData = {
        pedido: normalizeOrderText(orderForm.pedido),
        data: {
          ...newData,
          payment_method:
            newData.payment_method ||
            orderForm.data?.payment_method ||
            "efectivo",
        },
      };

      setPendingOrderData(finalPendingData);
      setOrderForm(null);

      addMsg(
        "bot",
        "📍 Para completar tu pedido, necesito tu ubicación exacta.",
        true
      );
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

      const normalizedOrderData = {
        cliente_nombre: String(
          orderData.data?.cliente_nombre ||
          user?.nombre ||
          ""
        ).trim(),
        telefono: String(
          orderData.data?.telefono ||
          user?.telefono ||
          ""
        ).trim(),
        gmail: String(
          orderData.data?.gmail ||
          user?.gmail ||
          ""
        )
          .trim()
          .toLowerCase(),
        direccion: String(
          orderData.data?.direccion ||
          user?.direccion ||
          location?.direccion_completa ||
          ""
        ).trim(),
        payment_method:
          orderData.data?.payment_method === "mercado_pago"
            ? "mercado_pago"
            : "efectivo",
      };

      const missingFields = [];

      if (!pedidoText) {
        missingFields.push("pedido");
      }

      if (normalizedOrderData.cliente_nombre.length < 2) {
        missingFields.push("nombre");
      }

      if (
        normalizedOrderData.telefono.replace(/\D/g, "").length < 8
      ) {
        missingFields.push("teléfono");
      }

      if (!normalizedOrderData.gmail.includes("@")) {
        missingFields.push("correo");
      }

      if (normalizedOrderData.direccion.length < 3) {
        missingFields.push("dirección");
      }

      if (
        !location ||
        !Number.isFinite(Number(location.lat)) ||
        !Number.isFinite(Number(location.lng))
      ) {
        missingFields.push("ubicación");
      }

      if (missingFields.length > 0) {
        throw new Error(
          `Faltan datos válidos: ${missingFields.join(", ")}`
        );
      }

      const result = await placeOrder(
        pedidoText,
        normalizedOrderData,
        location
      );

      if (result.success) {
        // Mensaje de confirmación base
        let confirmMsg = `✅ ¡Pedido #${result.order_id} confirmado!`;
        if (result.total) {
          confirmMsg += `\n💰 Total: ${result.total}`;
        }
        confirmMsg += `\n📍 Ubicación recibida.\n🍕 Te avisaré cuando el estado cambie.`;
        
        addMsg("bot", confirmMsg);
        lastReportedStatus.current = "pendiente";
        setActiveOrderId(String(result.order_id));
        setPendingOrderData(null);

        // ─────────────────────────────────────────────────────────────
        // MANEJO DE PAGO CON MERCADO PAGO
        // ─────────────────────────────────────────────────────────────
        const payment = result.payment;

        if (payment && payment.method === "mercadopago") {
          // 1. QR Code (para pagos presenciales)
          if (payment.qr_code_base64) {
            addMsg(
              "bot",
              `💳 Escanea este código QR con tu app de Mercado Pago para pagar.${
                payment.is_sandbox ? " (modo de prueba)" : ""
              }`,
              false,
              { qrCodeBase64: payment.qr_code_base64 }
            );
          }

          // 2. Link de pago (para pagos online) - PRIORIDAD ALTA
          else if (payment.url) {
            // Mostrar mensaje con el link
            const paymentMsg = `💳 Tu pedido está listo para pagar.

📲 Haz clic en el botón para completar tu pago con Mercado Pago.

${
  payment.is_sandbox
    ? "🔬 Este es un pago de prueba (modo sandbox)."
    : ""
}

⏰ El enlace expira en 30 minutos.`;

            addMsg(
              "bot",
              paymentMsg,
              false,
              { 
                paymentUrl: payment.url,
                paymentStatus: payment.status,
                isSandbox: payment.is_sandbox,
              }
            );

            // Opcional: Abrir automáticamente en nueva pestaña
            // Descomenta la línea siguiente si quieres que se abra automáticamente
            // window.open(payment.url, "_blank");
          }

          // 3. Error en el pago
          else if (payment.success === false) {
            addMsg(
              "bot",
              `⚠️ Tu pedido fue confirmado, pero no pude generar el pago automáticamente (${payment.error || "error desconocido"}). Por favor avísanos para coordinar el cobro.`
            );
          }

          // 4. Fallback: Pago en proceso
          else {
            addMsg(
              "bot",
              "💳 Pago con Mercado Pago en proceso. Te avisaremos cuando esté listo."
            );
          }
        }
      } else {
        addMsg("bot", `❌ Error al crear el pedido: ${result.message || "Intenta nuevamente"}`);
      }
    } catch (err) {
      let message = "Error al procesar el pedido";

      if (err?.message) {
        if (typeof err.message === "string") {
          message = err.message;
        } else if (Array.isArray(err.message)) {
          const parts = err.message
            .map((item) => {
              if (typeof item === "string") return item;
              if (typeof item === "object" && item !== null) {
                if (item.msg) return String(item.msg);
                if (item.message) return String(item.message);
              }
              return null;
            })
            .filter(Boolean);

          if (parts.length > 0) {
            message = parts.join(", ");
          } else {
            message = "Error de validación. Por favor, revisa los datos del pedido.";
          }
        } else if (typeof err.message === "object" && err.message !== null) {
          if (err.message.msg) {
            message = String(err.message.msg);
          } else if (err.message.message) {
            message = String(err.message.message);
          } else {
            message = "Error de validación. Por favor, revisa los datos del pedido.";
          }
        }
      } else if (typeof err === "string") {
        message = err;
      } else if (Array.isArray(err)) {
        const parts = err
          .map((item) => {
            if (typeof item === "string") return item;
            if (typeof item === "object" && item !== null) {
              if (item.msg) return String(item.msg);
              if (item.message) return String(item.message);
            }
            return null;
          })
          .filter(Boolean);

        if (parts.length > 0) {
          message = parts.join(", ");
        } else {
          message = "Error de validación. Por favor, revisa los datos del pedido.";
        }
      }

      addMsg("bot", `❌ ${message}`);
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

  const handleVoiceClick = () => {
    if (isListening) {
      stopListening();
    } else {
      if (input) setInput("");
      toggleListening();
    }
  };

  return (
    <>
      <div className="p220-shell-root">
        <div className="p220-bg-pattern" />
        <div className="p220-chat-shell">

          {/* ── Header ────────────────────────────────────────────────────────── */}
          <header className="p220-chat-header">
            <div className="p220-logo-wrap">
              <span className="p220-logo-emoji">🍕</span>
              <div>
                <div className="p220-logo-name">Pizzería 220</div>
                <div className="p220-logo-sub-line">
                  <span className="p220-logo-sub-dot" />
                  Asistente IA · Online
                </div>
              </div>
            </div>
            <div className="p220-header-right">
              <div className="p220-user-badge">
                <span className="p220-user-initial">{(user?.nombre || "U")[0].toUpperCase()}</span>
                <span className="p220-user-name">{user?.nombre}</span>
                <span className="p220-user-role">{user?.role}</span>
              </div>
              <button className="p220-logout-btn" onClick={handleLogout} title="Cerrar sesión">⎋</button>
              <div className="p220-status-dot" />
            </div>
          </header>

          {/* ── Feed ──────────────────────────────────────────────────────────── */}
          <div className="p220-chat-messages">
            {messages.map((msg) => (
              <div key={msg.id}>
                <MessageBubble msg={msg} />

                {/* QR Code */}
                {msg.qrCodeBase64 && (
                  <div className="p220-qr-wrap">
                    <img
                      src={`data:image/png;base64,${msg.qrCodeBase64}`}
                      alt="Código QR de Mercado Pago"
                      className="p220-qr-img"
                    />
                  </div>
                )}

                {/* Botón de pago Mercado Pago */}
                {msg.paymentUrl && (
                  <div className="p220-pay-wrap">
                    <a
                      href={msg.paymentUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p220-pay-link"
                    >
                      <span style={{ marginRight: 8 }}>💳</span>
                      Pagar con Mercado Pago
                    </a>
                    {msg.isSandbox && (
                      <div className="p220-pay-note p220-pay-note-warn">
                        🔬 Modo de prueba (sandbox)
                      </div>
                    )}
                    {msg.paymentStatus === "pending" && (
                      <div className="p220-pay-note p220-pay-note-muted">
                        ⏰ El enlace expira en 30 minutos
                      </div>
                    )}
                  </div>
                )}

                {msg.requiresLocation && !showLocationPicker && !loading && pendingOrderData && (
                  <div className="p220-msg-action">
                    <button
                      className="p220-share-loc-btn"
                      onClick={() => {
                        setShowLocationPicker(true);
                      }}
                      disabled={isSubmittingOrder}
                    >
                      📍 Compartir mi ubicación
                    </button>
                  </div>
                )}

                {msg.requiresExtrasDecision &&
                  !loading &&
                  !handledActionMessages.includes(msg.id) && (
                    <div
                      className="p220-msg-action"
                      style={{ display: "flex", gap: 10 }}
                    >
                      <button
                        type="button"
                        className="p220-opt-btn is-active"
                        onClick={() => handleExtrasDecision("si", msg)}
                      >
                        Sí
                      </button>

                      <button
                        type="button"
                        className="p220-opt-btn"
                        onClick={() => handleExtrasDecision("no", msg)}
                      >
                        No
                      </button>
                    </div>
                  )}

                {msg.requiresOrderConfirmation &&
                  !loading &&
                  !handledActionMessages.includes(msg.id) && (
                    <div
                      className="p220-msg-action"
                      style={{ display: "flex", gap: 10 }}
                    >
                      <button
                        type="button"
                        className="p220-opt-btn is-active"
                        onClick={() => handleOrderConfirmation("si", msg)}
                      >
                        Sí, confirmar
                      </button>

                      <button
                        type="button"
                        className="p220-opt-btn"
                        onClick={() => handleOrderConfirmation("no", msg)}
                      >
                        No, modificar
                      </button>
                    </div>
                  )}
              </div>
            ))}

            {extrasPrompt && (
              isSinglePizzaExtrasPrompt(extrasPrompt) ? (
                <div className="p220-msg-row">
                  <span className="p220-avatar">🍕</span>
                  <div
                    className="p220-bubble p220-bubble-bot"
                    style={{ display: "flex", flexDirection: "column", gap: 10, minWidth: 260 }}
                  >
                    <div>¿Le agregas algún extra a tu {extrasPrompt.products[0].name}?</div>

                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                      {AVAILABLE_EXTRAS.map((extra) => (
                        <button
                          key={extra.name}
                          type="button"
                          className={`p220-opt-btn${selectedExtras.includes(extra.name) ? " is-active" : ""}`}
                          disabled={loading}
                          onClick={() => toggleExtra(extra.name)}
                          style={{ padding: "6px 10px", fontSize: 13 }}
                        >
                          {selectedExtras.includes(extra.name) ? "✓ " : ""}
                          {extra.name}
                        </button>
                      ))}
                    </div>

                    <div style={{ display: "flex", gap: 6 }}>
                      <button
                        type="button"
                        className="p220-opt-btn"
                        disabled={loading}
                        onClick={applySinglePizzaAllExtras}
                        style={{ flex: 1, padding: "6px 10px", fontSize: 13 }}
                      >
                        Con todo
                      </button>

                      <button
                        type="button"
                        className="p220-opt-btn is-active"
                        disabled={loading || selectedExtras.length === 0}
                        onClick={confirmSinglePizzaExtras}
                        style={{
                          flex: 1,
                          padding: "6px 10px",
                          fontSize: 13,
                          opacity: selectedExtras.length === 0 ? 0.5 : 1,
                        }}
                      >
                        Agregar seleccionados
                      </button>
                    </div>

                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        paddingTop: 8,
                        borderTop: "1px solid rgba(0,0,0,0.08)",
                      }}
                    >
                      <input
                        type="number"
                        min="1"
                        max="20"
                        inputMode="numeric"
                        value={beverageQuantity}
                        onChange={(event) => setBeverageQuantity(event.target.value)}
                        className="p220-order-input"
                        style={{ width: 60, minWidth: 60, padding: "6px 8px", fontSize: 13 }}
                        aria-label="Cantidad de refrescos"
                        disabled={loading}
                      />

                      <button
                        type="button"
                        className="p220-opt-btn"
                        disabled={loading}
                        onClick={addBeveragesDuringExtras}
                        style={{ flex: 1, padding: "6px 10px", fontSize: 13 }}
                      >
                        🥤 Agregar Coca-Cola — $45.00 c/u
                      </button>
                    </div>

                    <button
                      type="button"
                      className="p220-opt-btn"
                      disabled={loading}
                      onClick={() =>
                        handleExtrasDecision("no", { id: extrasPrompt.messageId })
                      }
                      style={{ padding: "6px 10px", fontSize: 13 }}
                    >
                      Sin extras
                    </button>
                  </div>
                </div>
              ) : (
                <div
                  className="p220-order-card"
                  style={{
                    padding: 14,
                    borderRadius: 16,
                    boxShadow: "0 8px 24px rgba(0, 0, 0, 0.08)",
                  }}
                >
                  <div
                    className="p220-order-label"
                    style={{ marginBottom: 8 }}
                  >
                    Configura los extras
                  </div>

                  {extrasPrompt.products.length > 0 && (
                    <div
                      style={{
                        marginBottom: 10,
                        padding: 10,
                        borderRadius: 10,
                        background: "rgba(0, 0, 0, 0.035)",
                        fontSize: 13,
                      }}
                    >
                      {extrasPrompt.products.map((product) => (
                        <div key={product.name}>
                          • {product.quantity} × Pizza {product.name}
                        </div>
                      ))}
                    </div>
                  )}

                  <div style={{ marginBottom: 10, fontSize: 13 }}>
                    Escribe la pizza, la cantidad y los extras.
                  </div>

                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns:
                        "repeat(auto-fit, minmax(145px, 1fr))",
                      gap: 7,
                      marginBottom: 12,
                    }}
                  >
                    {AVAILABLE_EXTRAS.map((extra) => (
                      <div
                        key={extra.name}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          gap: 8,
                          padding: "8px 10px",
                          borderRadius: 9,
                          background: "rgba(0, 0, 0, 0.035)",
                          fontSize: 12,
                        }}
                      >
                        <span>{extra.name}</span>
                        <strong style={{ whiteSpace: "nowrap" }}>
                          {extra.price}
                        </strong>
                      </div>
                    ))}
                  </div>

                  <div
                    style={{
                      marginBottom: 12,
                      padding: 10,
                      borderRadius: 10,
                      background: "rgba(0, 0, 0, 0.035)",
                    }}
                  >
                    <div
                      style={{
                        marginBottom: 8,
                        fontSize: 13,
                        fontWeight: 700,
                      }}
                    >
                      Agregar refrescos al pedido
                    </div>

                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <input
                        type="number"
                        min="1"
                        max="20"
                        inputMode="numeric"
                        value={beverageQuantity}
                        onChange={(event) =>
                          setBeverageQuantity(event.target.value)
                        }
                        className="p220-order-input"
                        style={{ width: 76, minWidth: 76 }}
                        aria-label="Cantidad de refrescos"
                      />

                      <button
                        type="button"
                        className="p220-opt-btn"
                        disabled={loading}
                        onClick={addBeveragesDuringExtras}
                        style={{ flex: 1 }}
                      >
                        Agregar Coca-Cola — $45.00 c/u
                      </button>
                    </div>
                  </div>

                  <div className="p220-order-input-row">
                    <input
                      autoFocus
                      type="text"
                      value={extrasInput}
                      onChange={(event) =>
                        setExtrasInput(event.target.value)
                      }
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          submitExtrasDescription();
                        }
                      }}
                      className="p220-order-input"
                      placeholder="Ej. 2 Pepperoni con queso extra"
                    />

                    <button
                      type="button"
                      onClick={submitExtrasDescription}
                      disabled={!extrasInput.trim() || loading}
                      className="p220-order-submit"
                      aria-label="Enviar configuración de extras"
                    >
                      →
                    </button>
                  </div>

                  <button
                    type="button"
                    className="p220-opt-btn"
                    disabled={loading}
                    style={{
                      width: "100%",
                      marginTop: 10,
                    }}
                    onClick={() =>
                      handleExtrasDecision("no", {
                        id: extrasPrompt.messageId,
                      })
                    }
                  >
                    Continuar sin extras
                  </button>
                </div>
              )
            )}

            {orderForm && ORDER_STEPS[orderForm.step] && (
              <OrderStep step={ORDER_STEPS[orderForm.step]} onSubmit={submitOrderStep} />
            )}

            {loading && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>

          {/* ── Input bar ─────────────────────────────────────────────────────── */}
          {!orderForm && (
            <>
              {inputHint && (
                <div
                  className="p220-order-card"
                  style={{ margin: "0 16px 10px" }}
                >
                  <div className="p220-order-label">
                    Modifica tu pedido
                  </div>
                  <div style={{ fontSize: 13 }}>
                    {inputHint}
                  </div>
                </div>
              )}

              <div className="p220-chat-footer">

              {/* Botón de voz */}
              {isSupported && (
                <button
                  className={`p220-mic-btn${isListening ? " is-listening" : ""}`}
                  onClick={handleVoiceClick}
                  disabled={loading || isSubmittingOrder}
                  title={isListening ? "Detener grabación" : "Activar voz"}
                >
                  {/* Ripples — solo visibles mientras escucha */}
                  {isListening && (
                    <>
                      <span className="p220-mic-ripple" />
                      <span className="p220-mic-ripple p220-mic-ripple-2" />
                    </>
                  )}

                  {/* Ícono o barras de onda */}
                  {isListening ? (
                    <span className="p220-mic-wave">
                      {[0, 1, 2, 3, 4].map((i) => (
                        <span key={i} className={`p220-mic-wave-bar p220-mic-wave-bar-${i + 1}`} />
                      ))}
                    </span>
                  ) : (
                    <span style={{ fontSize: 17 }}>🎤</span>
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
                className={`p220-chat-textarea${isListening ? " is-listening" : ""}`}
                disabled={loading || isSubmittingOrder || isListening}
              />

              <button
                className="p220-send-btn"
                onClick={() => sendMessage(input)}
                disabled={loading || isSubmittingOrder || !input.trim() || isListening}
              >
                <SendIcon />
              </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Toast flotante de escucha ──────────────────────────────────────────── */}
      {isListening && (
        <div className="p220-listen-toast">
          <span className="p220-listen-dot" />
          <span>Escuchando...</span>
          {interimTranscript && (
            <span className="p220-listen-interim">"{interimTranscript}"</span>
          )}
          <button
            className="p220-cancel-btn"
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
        <div className="p220-voice-unsupported">
          ⚠️ Tu navegador no soporta reconocimiento de voz. Usa Chrome o Edge.
        </div>
      )}

      {/* ── Location Picker ───────────────────────────────────────────────────── */}
      {showLocationPicker && (
        <LocationPicker
          onLocationSelect={handleLocationConfirm}
          onClose={() => {
            setShowLocationPicker(false);
          }}
        />
      )}
    </>
  );
}