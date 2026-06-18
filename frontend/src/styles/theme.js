// ── Colores ──────────────────────────────────────────────────────────────────
export const RED    = "#e8372a";
export const DARK   = "#0e0e0e";
export const CARD   = "#161616";
export const CARD2  = "#1c1c1c";
export const BORDER = "#252525";
export const BORDER2= "#2e2e2e";
export const TEXT   = "#f0ede8";
export const MUTED  = "#777";
export const GREEN  = "#4caf50";

// ── Estilos globales (inyectados una sola vez) ────────────────────────────────
if (typeof document !== "undefined") {
  const id = "p220-global-styles";
  if (!document.getElementById(id)) {
    const st = document.createElement("style");
    st.id = id;
    st.textContent = `
      @keyframes bounce {
        0%,80%,100% { transform:translateY(0) }
        40%          { transform:translateY(-6px) }
      }
      @keyframes fadeIn {
        from { opacity:0; transform:translateY(8px) }
        to   { opacity:1; transform:translateY(0)   }
      }
      @keyframes pulse {
        0%,100% { box-shadow:0 0 0 0 rgba(239,68,68,.45) }
        60%     { box-shadow:0 0 0 12px rgba(239,68,68,0) }
      }
      @keyframes voicePulse {
        0%,100% { transform:scale(1);   opacity:1   }
        50%     { transform:scale(1.55);opacity:.45 }
      }
      @keyframes slideUp {
        from { opacity:0; transform:translateX(-50%) translateY(16px) }
        to   { opacity:1; transform:translateX(-50%) translateY(0)    }
      }
      @keyframes ripple {
        0%   { transform:scale(.8); opacity:1 }
        100% { transform:scale(2.2);opacity:0 }
      }
      @keyframes micGlow {
        0%,100% { box-shadow:0 0 0 0 rgba(239,68,68,.6),0 4px 16px rgba(0,0,0,.5) }
        50%     { box-shadow:0 0 0 8px rgba(239,68,68,.1),0 4px 20px rgba(0,0,0,.6) }
      }
      @keyframes waveBar {
        0%,100% { height:4px }
        50%     { height:16px }
      }
      textarea { scrollbar-width:thin; scrollbar-color:#252525 transparent }
      * { box-sizing:border-box; margin:0; padding:0 }
      body { margin:0 }
    `;
    document.head.appendChild(st);
  }
}

// ── Objeto de estilos compartidos ────────────────────────────────────────────
export const s = {
  // layout
  root: {
    minHeight:"100vh", background:DARK,
    display:"flex", alignItems:"center", justifyContent:"center",
    fontFamily:"'Georgia','Times New Roman',serif",
    position:"relative", overflow:"hidden",
  },
  bgPattern: {
    position:"absolute", inset:0, zIndex:0, pointerEvents:"none",
    backgroundImage:`radial-gradient(ellipse 60% 40% at 15% 55%,rgba(232,55,42,.08) 0%,transparent 65%),
                     radial-gradient(ellipse 50% 35% at 85% 15%,rgba(232,55,42,.04) 0%,transparent 55%)`,
  },

  // auth
  authWrap: {
    position:"relative", zIndex:1,
    width:"min(440px,100vw)", padding:"0 0 40px",
    display:"flex", flexDirection:"column", alignItems:"center",
  },
  authLogo: { display:"flex", flexDirection:"column", alignItems:"center", gap:6, marginBottom:24 },
  authCard: {
    width:"100%", background:CARD,
    border:`1px solid ${BORDER2}`, borderRadius:18,
    padding:"28px 28px 24px",
  },
  authTitle: { fontSize:20, fontWeight:"bold", color:TEXT, marginBottom:20, textAlign:"center" },
  fieldWrap: { marginBottom:14 },
  fieldLabel:{ display:"block", fontSize:13, color:MUTED, marginBottom:5, fontFamily:"monospace" },
  authInput: {
    width:"100%", boxSizing:"border-box",
    background:"#111", border:`1px solid ${BORDER2}`,
    borderRadius:8, color:TEXT, padding:"10px 14px",
    fontSize:15, fontFamily:"'Georgia',serif", outline:"none",
    transition:"border-color .2s",
  },
  select: {
    width:"100%", boxSizing:"border-box",
    background:"#111", border:`1px solid ${BORDER2}`,
    borderRadius:8, color:TEXT, padding:"10px 14px",
    fontSize:15, fontFamily:"'Georgia',serif", outline:"none",
  },
  authSubmit: {
    width:"100%", marginTop:6,
    background:RED, border:"none", borderRadius:10,
    color:"#fff", padding:"12px",
    fontSize:16, fontWeight:"bold",
    cursor:"pointer", fontFamily:"'Georgia',serif",
    transition:"opacity .15s, background .15s",
    boxShadow:"0 2px 14px rgba(232,55,42,.3)",
  },
  authLink: { color:RED, cursor:"pointer", textDecoration:"underline" },
  errorMsg: {
    background:"#1e0a0a", border:`1px solid ${RED}44`,
    borderRadius:8, color:"#f87171",
    padding:"10px 14px", fontSize:13,
    marginBottom:12, fontFamily:"monospace",
  },

  // chat shell
  shell: {
    position:"relative", zIndex:1,
    width:"min(700px,100vw)", height:"100vh",
    display:"flex", flexDirection:"column",
    background:CARD, borderLeft:`1px solid ${BORDER}`, borderRight:`1px solid ${BORDER}`,
  },
  header: {
    padding:"14px 20px", borderBottom:`1px solid ${BORDER}`,
    display:"flex", alignItems:"center", justifyContent:"space-between",
    background:"#111", flexShrink:0,
  },
  logoWrap:   { display:"flex", alignItems:"center", gap:12 },
  logoEmoji:  { fontSize:28, lineHeight:1, filter:"drop-shadow(0 1px 6px rgba(232,55,42,.35))" },
  logoName:   { fontSize:17, fontWeight:"bold", color:TEXT, letterSpacing:".02em" },
  logoSub:    { fontSize:11, color:GREEN, marginTop:2, fontFamily:"monospace", display:"flex", alignItems:"center", gap:5 },
  logoSubDot: { display:"inline-block", width:6, height:6, borderRadius:"50%", background:GREEN, boxShadow:`0 0 6px ${GREEN}` },
  dot:        { width:9, height:9, borderRadius:"50%", background:GREEN, boxShadow:`0 0 8px ${GREEN}` },
  userBadge:  { display:"flex", alignItems:"center", gap:7, background:"#1a1a1a", borderRadius:20, padding:"4px 12px 4px 5px", border:`1px solid ${BORDER2}` },
  userInitial:{ width:26, height:26, borderRadius:"50%", background:RED, color:"#fff", fontSize:12, fontWeight:"bold", display:"flex", alignItems:"center", justifyContent:"center", boxShadow:"0 0 8px rgba(232,55,42,.35)" },
  userName:   { fontSize:13, color:TEXT },
  userRole:   { fontSize:11, color:MUTED, fontFamily:"monospace" },
  logoutBtn:  { background:"transparent", border:`1px solid ${BORDER2}`, borderRadius:8, color:MUTED, width:30, height:30, cursor:"pointer", fontSize:15, transition:"all .2s", display:"flex", alignItems:"center", justifyContent:"center" },

  // feed
  feed: {
    flex:1, overflowY:"auto", padding:"24px 20px",
    display:"flex", flexDirection:"column", gap:14,
    scrollbarWidth:"thin", scrollbarColor:`${BORDER} transparent`,
  },
  msgRow:     { display:"flex", alignItems:"flex-end", gap:10, animation:"fadeIn .25s ease" },
  avatar:     { fontSize:21, flexShrink:0, marginBottom:2 },
  bubbleBot:  { background:CARD2, border:`1px solid ${BORDER2}`, color:TEXT, padding:"11px 15px", borderRadius:"16px 16px 16px 4px", maxWidth:"76%", fontSize:14, lineHeight:1.65 },
  bubbleUser: { background:`linear-gradient(135deg,#d42d21,${RED})`, color:"#fff", padding:"11px 15px", borderRadius:"16px 16px 4px 16px", maxWidth:"76%", fontSize:14, lineHeight:1.65, boxShadow:"0 2px 12px rgba(232,55,42,.22)" },
  typingBubble:{ display:"flex", alignItems:"center", gap:5, padding:"13px 16px" },
  dot2:       { display:"inline-block", width:7, height:7, borderRadius:"50%", background:MUTED, animation:"bounce 0.9s infinite ease-in-out" },

  // order
  orderCard:  { background:"#1a1a1a", border:`1px solid ${RED}33`, borderRadius:14, padding:"18px 20px", marginLeft:36, animation:"fadeIn .3s ease" },
  orderLabel: { fontSize:14, color:"#f5a623", marginBottom:12, fontFamily:"monospace", letterSpacing:".05em" },
  orderInputRow:{ display:"flex", gap:8 },
  orderInput: { flex:1, background:"#111", border:`1px solid ${BORDER2}`, borderRadius:8, color:TEXT, padding:"10px 14px", fontSize:15, outline:"none" },
  orderSubmit:{ background:RED, border:"none", borderRadius:8, color:"#fff", width:44, fontSize:20, cursor:"pointer" },
  selectRow:  { display:"flex", gap:12 },
  optBtn:     { flex:1, padding:"12px", border:`1px solid ${BORDER2}`, borderRadius:10, background:"transparent", color:TEXT, fontSize:15, cursor:"pointer" },
  optBtnActive:{ background:RED, border:`1px solid ${RED}`, color:"#fff" },

  // input bar
  inputBar:   { padding:"12px 16px", borderTop:`1px solid ${BORDER}`, display:"flex", gap:9, alignItems:"flex-end", background:"#111", flexShrink:0 },
  textarea:   {
    flex:1, background:CARD2, border:`1px solid ${BORDER2}`, borderRadius:12,
    color:TEXT, padding:"11px 15px", fontSize:14, resize:"none", outline:"none",
    lineHeight:1.5, maxHeight:120, overflow:"auto",
    fontFamily:"'Georgia',serif", transition:"border-color .2s, background .2s",
  },
  textareaListening: {
    borderColor:"#ef4444", background:"#1e0a0a", color:"#fca5a5",
  },
  sendBtn:    {
    background:RED, border:"none", borderRadius:12, color:"#fff",
    width:44, height:44, display:"flex", alignItems:"center", justifyContent:"center",
    cursor:"pointer", flexShrink:0, transition:"all .15s",
    boxShadow:"0 2px 10px rgba(232,55,42,.28)",
  },

  // ── Mic button ──────────────────────────────────────────────────────────────
  // Estado idle
  micBtn: {
    position:"relative", width:44, height:44, borderRadius:12, flexShrink:0,
    background:CARD2, border:`1px solid ${BORDER2}`,
    color:MUTED, fontSize:18, cursor:"pointer",
    display:"flex", alignItems:"center", justifyContent:"center",
    transition:"all .2s", overflow:"hidden",
  },
  // Estado activo (listening) — fusionar sobre micBtn
  micBtnActive: {
    background:"#ef4444", borderColor:"#ef4444", color:"#fff",
    animation:"micGlow 1.4s ease-in-out infinite",
  },
  // Ondas ripple (position:absolute, inset:0 dentro del botón)
  micRipple: {
    position:"absolute", inset:0, borderRadius:12,
    border:"2px solid rgba(255,255,255,.5)",
    animation:"ripple 1.2s ease-out infinite",
    pointerEvents:"none",
  },
  micRipple2: {
    position:"absolute", inset:0, borderRadius:12,
    border:"2px solid rgba(255,255,255,.3)",
    animation:"ripple 1.2s ease-out .4s infinite",
    pointerEvents:"none",
  },
  // Barras de onda de audio (dentro del botón en modo activo)
  micWave: { display:"flex", alignItems:"center", gap:2, height:20 },
  micWaveBar: {
    display:"inline-block", width:3, background:"#fff",
    borderRadius:2, height:4,
  },
  // Cada barra con su delay (aplicar via style inline)
  micWaveBar1: { animation:"waveBar .6s ease-in-out infinite" },
  micWaveBar2: { animation:"waveBar .6s ease-in-out .1s infinite" },
  micWaveBar3: { animation:"waveBar .6s ease-in-out .2s infinite" },
  micWaveBar4: { animation:"waveBar .6s ease-in-out .15s infinite" },
  micWaveBar5: { animation:"waveBar .6s ease-in-out .05s infinite" },

  // ── Toast flotante de escucha ──────────────────────────────────────────────
  listenToast: {
    position:"fixed", bottom:100, left:"50%", transform:"translateX(-50%)",
    background:"#161616", border:`1px solid ${BORDER2}`,
    color:TEXT, padding:"10px 18px", borderRadius:28,
    display:"flex", alignItems:"center", gap:12,
    fontSize:13, animation:"slideUp .3s ease", zIndex:1000,
    whiteSpace:"nowrap", boxShadow:"0 8px 28px rgba(0,0,0,.55)",
  },
  listenDot: {
    width:10, height:10, background:"#ef4444", borderRadius:"50%",
    flexShrink:0, animation:"voicePulse 1s infinite",
  },
  listenInterim: {
    color:"#fbbf24", fontSize:12, maxWidth:160,
    overflow:"hidden", textOverflow:"ellipsis",
    borderLeft:`1px solid ${BORDER2}`, paddingLeft:10,
  },
  cancelBtn: {
    background:"#222", border:`1px solid ${BORDER2}`, color:MUTED,
    padding:"5px 12px", borderRadius:16, cursor:"pointer",
    fontSize:12, transition:"all .2s",
  },

  // location picker – overlay
  locOverlay: {
    position:"fixed", inset:0,
    background:"rgba(0,0,0,.72)", backdropFilter:"blur(4px)",
    display:"flex", alignItems:"center", justifyContent:"center",
    zIndex:50, padding:16,
  },
  locModal: {
    background:CARD, border:`1px solid ${BORDER2}`, borderRadius:18,
    width:"min(440px,100%)", maxHeight:"90vh",
    overflowY:"auto", display:"flex", flexDirection:"column",
    scrollbarWidth:"thin", scrollbarColor:`${BORDER} transparent`,
  },

  // location picker – header (sticky)
  locHeader: {
    padding:"16px 20px", borderBottom:`1px solid ${BORDER}`,
    display:"flex", alignItems:"center", justifyContent:"space-between",
    background:CARD, position:"sticky", top:0, zIndex:1,
  },
  locTitle: { fontSize:18, fontWeight:"bold", color:TEXT, fontFamily:"'Georgia',serif" },
  locCloseBtn: {
    background:"transparent", border:`1px solid ${BORDER2}`,
    borderRadius:8, color:MUTED, width:32, height:32,
    cursor:"pointer", fontSize:18, display:"flex",
    alignItems:"center", justifyContent:"center",
  },

  // location picker – body
  locBody: { padding:"20px", display:"flex", flexDirection:"column", gap:14 },

  // location picker – buttons
  locGpsBtn: {
    width:"100%", background:RED, border:"none", borderRadius:10,
    color:"#fff", padding:"12px", fontSize:15, fontWeight:"bold",
    cursor:"pointer", fontFamily:"'Georgia',serif", transition:"opacity .15s",
    boxShadow:"0 2px 12px rgba(232,55,42,.28)",
  },
  locConfirmBtn: {
    width:"100%", background:"#0f1e0f", border:`1px solid #4caf5055`,
    borderRadius:10, color:GREEN, padding:"12px",
    fontSize:15, fontWeight:"bold",
    cursor:"pointer", fontFamily:"'Georgia',serif", transition:"opacity .15s", marginTop:4,
  },
  locConfirmBtnDone: {
    width:"100%", background:"#4caf5015", border:`1px solid #4caf5055`,
    borderRadius:10, color:GREEN, padding:"12px",
    fontSize:15, fontWeight:"bold",
    cursor:"default", fontFamily:"'Georgia',serif", opacity:.65, marginTop:4,
  },

  // location picker – search row
  locSearchRow: { position:"relative" },
  locSearchInput: {
    width:"100%", boxSizing:"border-box",
    background:"#111", border:`1px solid ${BORDER2}`,
    borderRadius:8, color:TEXT, padding:"10px 44px 10px 14px",
    fontSize:15, fontFamily:"'Georgia',serif", outline:"none",
  },
  locSearchBtn: {
    position:"absolute", right:10, top:"50%", transform:"translateY(-50%)",
    background:"transparent", border:"none", cursor:"pointer", fontSize:18, lineHeight:1,
  },

  // location picker – feedback cards
  locError: {
    background:"#1e0a0a", border:`1px solid ${RED}44`,
    borderRadius:8, color:"#f87171", padding:"10px 14px", fontSize:13, fontFamily:"monospace",
  },
  locAddressCard: {
    background:"#0d1a0d", border:`1px solid #4caf5033`,
    borderRadius:8, padding:"12px 14px",
  },
  locAddressLabel: { fontSize:13, fontWeight:"bold", color:GREEN, marginBottom:4, fontFamily:"monospace" },
  locAddressText:  { fontSize:13, color:TEXT, lineHeight:1.5 },
  locCoordsCard: {
    background:"#1a1a1a", border:`1px solid ${BORDER}`,
    borderRadius:8, padding:"10px 14px", fontSize:12, color:MUTED, fontFamily:"monospace",
  },

  // location picker – static map
  locMap: { width:"100%", borderRadius:10, border:`1px solid ${BORDER2}`, display:"block", marginTop:4 },
};