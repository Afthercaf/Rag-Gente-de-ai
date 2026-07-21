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
//       const result = await placeOrder(user.id, pedidoText, orderData.data, location);
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
import { s, CLS } from "../../styles/theme";
import { MessageBubble } from "./MessageBubble";
import OrderStep from "./OrderStep";
import { TypingIndicator, SendIcon } from "./ChatUIElements";
import LocationPicker from "./LocationPicker";

export default function ChatScreen({ user, onLogout }) {
  // LOG INICIAL: Para ver qué usuario está cargando la pantalla
  console.log("👤 [ChatScreen] Render - User prop:", user);

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
      console.log("🎤 [Voice Hook] onResult:", text);
      if (text.trim()) {
        setInput(text);
        if (sendTimeoutRef.current) clearTimeout(sendTimeoutRef.current);
        sendTimeoutRef.current = setTimeout(() => {
          if (text.trim() && !loading && !isSubmittingOrder && !orderForm) {
            console.log("🎤 [Voice Hook] Auto-enviando mensaje por voz...");
            sendMessage(text.trim());
          }
          sendTimeoutRef.current = null;
        }, 500);
      }
    },
    onError: (errorMsg) => {
      console.error("🎤 [Voice Hook] Error:", errorMsg);
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

  const addMsg = (role, text, requiresAction = false, extra = {}) => {
    console.log(`💬 [addMsg] Agregando mensaje - Rol: ${role} | Texto:`, text);
    const newMsg = { id: nextId(), role, text, ...extra };
    if (requiresAction && role === "bot") newMsg.requiresLocation = true;
    setMessages((m) => [...m, newMsg]);
  };

  const { status: orderStatus, label: orderLabel, isDone } = useOrderStatus(activeOrderId);

  useEffect(() => {
    if (!activeOrderId) return;
    console.log(`🔔 [useOrderStatus] ID: ${activeOrderId} | Status actual: ${orderStatus}`);
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

  const isOrderDraft = (reply = "") => {
    const normalized = reply
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");

    return normalized.includes("confirmas tu pedido");
  };

  const sendMessage = async (text) => {
    if (!text.trim()) return;

    console.log("📤 [sendMessage] Iniciando envío de texto:", text);

    if (isListening) stopListening();

    addMsg("user", text);
    setInput("");
    setLoading(true);

    try {
      console.log(
        `🌐 [API sendChat] Solicitando con - text: "${text}", userId: ${user?.id}`
      );

      const data = await sendChat(text, user.id);
      console.log("📥 [API sendChat] Respuesta recibida:", data);

      addMsg("bot", data.reply);

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
          },
        };

        setPendingOrderData(nextPendingOrder);
        console.log(
          "💾 [sendMessage] Pedido guardado a la espera de confirmación:",
          nextPendingOrder
        );
      }

      /*
       * 2. El formulario se abre únicamente cuando el backend ya confirmó
       *    el pedido y solicita el método de pago.
       *
       *    El mensaje del backend ya pregunta cómo pagar, por eso NO
       *    agregamos otro mensaje "¿Cómo vas a pagar?" desde el frontend.
       */
      if (paymentPrompt) {
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

        console.log(
          "💳 [sendMessage] Abriendo selector único de método de pago:",
          formSetup
        );
      } else if (orderDraft) {
        /*
         * El resumen todavía espera confirmación.
         * Aseguramos que no quede abierto un formulario viejo.
         */
        setOrderForm(null);
      }
    } catch (err) {
      console.error("❌ [sendMessage] Error en la petición:", err);
      addMsg("bot", `❌ ${err.message}`);
    } finally {
      setLoading(false);
    }
  };


  const normalizeOrderText = (pedido) => {
    const original = pedido;
    let result = "";
    if (typeof pedido === "string") result = pedido.trim();
    else if (pedido && typeof pedido.raw === "string") result = pedido.raw.trim();
    else if (pedido) result = JSON.stringify(pedido).trim();
    
    console.log("🔍 [normalizeOrderText] De:", original, "-> Normalizado a:", result);
    return result;
  };

  const submitOrderStep = async (value) => {
    if (!orderForm || isSubmittingOrder) return;
    const step = ORDER_STEPS[orderForm.step];
    const newData = { ...orderForm.data, [step.key]: value };
    
    console.log(`📥 [submitOrderStep] Paso ${orderForm.step} (${step.key}) recibido valor:`, value);
    addMsg("user", value);

    if (orderForm.step < ORDER_STEPS.length - 1) {
      const nextFormState = { ...orderForm, step: orderForm.step + 1, data: newData };
      setOrderForm(nextFormState);
      console.log("➡️ [submitOrderStep] Avanzando al siguiente paso del formulario:", nextFormState);
    } else {
      const finalPendingData = { pedido: normalizeOrderText(orderForm.pedido), data: { ...newData } };
      setPendingOrderData(finalPendingData);
      setOrderForm(null);
      console.log("🏁 [submitOrderStep] Formulario finalizado. pendingOrderData listo:", finalPendingData);
      addMsg("bot", "📍 Para completar tu pedido, necesito tu ubicación exacta.", true);
    }
  };

  const handleLocationConfirm = async (location) => {
    console.log("📍 [handleLocationConfirm] Ubicación seleccionada del mapa:", location);
    if (isSubmittingOrder) return;
    if (!pendingOrderData) {
      console.error("❌ [handleLocationConfirm] Intento de confirmar ubicación sin pendingOrderData");
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
      
      console.log("🌐 [API placeOrder] Enviando payload final:", {
        userId: user.id,
        pedidoText,
        userData: orderData.data,
        location
      });

      const result = await placeOrder(user.id, pedidoText, orderData.data, location);
      console.log("📥 [API placeOrder] Respuesta del servidor:", result);

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
          console.log("💳 [handleLocationConfirm] Procesando pago Mercado Pago:", payment);

          // 1. QR Code (para pagos presenciales)
          if (payment.qr_code_base64) {
            console.log("📱 [handleLocationConfirm] Mostrando QR Code");
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
            console.log("🔗 [handleLocationConfirm] Mostrando link de pago:", payment.url);
            
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
            console.warn("⚠️ [handleLocationConfirm] Error en pago:", payment.error);
            addMsg(
              "bot",
              `⚠️ Tu pedido fue confirmado, pero no pude generar el pago automáticamente (${payment.error || "error desconocido"}). Por favor avísanos para coordinar el cobro.`
            );
          }

          // 4. Fallback: Pago en proceso
          else {
            console.log("ℹ️ [handleLocationConfirm] Pago en proceso sin detalles adicionales");
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
      console.error("❌ [handleLocationConfirm] Error fatal al procesar pedido:", err);
      addMsg("bot", `❌ Error al procesar el pedido: ${err.message}`);
    } finally {
      setLoading(false);
      setIsSubmittingOrder(false);
    }
  };

  const handleLogout = async () => { 
    console.log("🚪 [handleLogout] Cerrando sesión...");
    await logout(); 
    clearSession(); 
    onLogout(); 
  };

  const handleVoiceClick = () => {
    console.log("🎙️ [handleVoiceClick] Cambiando estado de escucha. Actual:", isListening);
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
        <div className={CLS.shell} style={s.shell}>

          {/* ── Header ────────────────────────────────────────────────────────── */}
          <header className={CLS.header} style={s.header}>
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
            <div style={{ display:"flex", alignItems:"center", gap:10, flexShrink:0 }}>
              <div style={s.userBadge}>
                <span style={s.userInitial}>{(user?.nombre || "U")[0].toUpperCase()}</span>
                <span className={CLS.userName} style={s.userName}>{user?.nombre}</span>
                <span style={s.userRole}>{user?.role}</span>
              </div>
              <button className={CLS.logoutBtn} onClick={handleLogout} style={s.logoutBtn} title="Cerrar sesión">⎋</button>
              <div style={s.dot} />
            </div>
          </header>

          {/* ── Feed ──────────────────────────────────────────────────────────── */}
          <div className={CLS.feed} style={s.feed}>
            {messages.map((msg) => (
              <div key={msg.id}>
                <MessageBubble msg={msg} />
                
                {/* QR Code */}
                {msg.qrCodeBase64 && (
                  <div style={{ marginTop: 8, marginLeft: 50, maxWidth: "calc(100% - 50px)" }}>
                    <img
                      src={`data:image/png;base64,${msg.qrCodeBase64}`}
                      alt="Código QR de Mercado Pago"
                      style={{
                        width: "min(220px, 55vw)",
                        height: "min(220px, 55vw)",
                        borderRadius: 12,
                        border: "1px solid rgba(0,0,0,.08)",
                        boxShadow: "0 2px 10px rgba(0,0,0,.08)",
                        background: "#fff",
                      }}
                    />
                  </div>
                )}

                {/* Botón de pago Mercado Pago */}
                {msg.paymentUrl && (
                  <div style={{ marginTop: 10, marginLeft: 50, maxWidth: "calc(100% - 50px)" }}>
                    <a
                      href={msg.paymentUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={CLS.link}
                      style={s.payLink}
                    >
                      <span style={{ marginRight: 8 }}>💳</span>
                      Pagar con Mercado Pago
                    </a>
                    {msg.isSandbox && (
                      <div style={{ 
                        marginTop: 6, 
                        fontSize: 12, 
                        color: "#f59e0b",
                        fontWeight: "500",
                      }}>
                        🔬 Modo de prueba (sandbox)
                      </div>
                    )}
                    {msg.paymentStatus === "pending" && (
                      <div style={{ 
                        marginTop: 4, 
                        fontSize: 12, 
                        color: "#6b7280",
                      }}>
                        ⏰ El enlace expira en 30 minutos
                      </div>
                    )}
                  </div>
                )}

                {msg.requiresLocation && !showLocationPicker && !loading && pendingOrderData && (
                  <div style={{ marginTop:8, marginLeft:50, maxWidth: "calc(100% - 50px)" }}>
                    <button
                      className={CLS.confirmBtn}
                      onClick={() => {
                        console.log("🗺️ [UI] Botón compartir ubicación clickeado. Abriendo LocationPicker.");
                        setShowLocationPicker(true);
                      }}
                      disabled={isSubmittingOrder}
                      style={{
                        ...s.shareLocBtn,
                        cursor: isSubmittingOrder ? "not-allowed" : "pointer",
                        opacity: isSubmittingOrder ? 0.5 : 1,
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
            <div className={CLS.inputBar} style={s.inputBar}>

              {/* Botón de voz */}
              {isSupported && (
                <button
                  className={CLS.micBtn}
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
                className={CLS.sendBtn}
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
              console.log("🎙️ [UI] Cancelando captura de voz.");
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
        <div style={s.voiceUnsupported}>
          ⚠️ Tu navegador no soporta reconocimiento de voz. Usa Chrome o Edge.
        </div>
      )}

      {/* ── Location Picker ───────────────────────────────────────────────────── */}
      {showLocationPicker && (
        <LocationPicker
          onLocationSelect={handleLocationConfirm}
          onClose={() => {
            console.log("🗺️ [UI] Cerrando LocationPicker.");
            setShowLocationPicker(false);
          }}
        />
      )}
    </>
  );
}