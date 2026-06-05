// ── Colores ──────────────────────────────────────────────────────────────────
export const RED    = "#e8372a";
export const DARK   = "#111111";
export const CARD   = "#1a1a1a";
export const BORDER = "#2c2c2c";
export const TEXT   = "#f0ede8";
export const MUTED  = "#888";

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
        from { opacity:0; transform:translateY(6px) }
        to   { opacity:1; transform:translateY(0)   }
      }
      textarea { scrollbar-width:thin; scrollbar-color:#2c2c2c transparent }
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
    backgroundImage:`radial-gradient(circle at 20% 50%,rgba(232,55,42,.07) 0%,transparent 60%),
                     radial-gradient(circle at 80% 20%,rgba(232,55,42,.05) 0%,transparent 50%)`,
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
    border:`1px solid ${BORDER}`, borderRadius:18,
    padding:"28px 28px 24px",
  },
  authTitle: { fontSize:20, fontWeight:"bold", color:TEXT, marginBottom:20, textAlign:"center" },
  fieldWrap: { marginBottom:14 },
  fieldLabel:{ display:"block", fontSize:13, color:MUTED, marginBottom:5, fontFamily:"monospace" },
  authInput: {
    width:"100%", boxSizing:"border-box",
    background:"#111", border:`1px solid ${BORDER}`,
    borderRadius:8, color:TEXT, padding:"10px 14px",
    fontSize:15, fontFamily:"'Georgia',serif", outline:"none",
  },
  select: {
    width:"100%", boxSizing:"border-box",
    background:"#111", border:`1px solid ${BORDER}`,
    borderRadius:8, color:TEXT, padding:"10px 14px",
    fontSize:15, fontFamily:"'Georgia',serif", outline:"none",
  },
  authSubmit: {
    width:"100%", marginTop:6,
    background:RED, border:"none", borderRadius:10,
    color:"#fff", padding:"12px",
    fontSize:16, fontWeight:"bold",
    cursor:"pointer", fontFamily:"'Georgia',serif",
    transition:"opacity .15s",
  },
  authLink: { color:RED, cursor:"pointer", textDecoration:"underline" },
  errorMsg: {
    background:"#2a1010", border:`1px solid ${RED}55`,
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
    background:"#141414", flexShrink:0,
  },
  logoWrap:   { display:"flex", alignItems:"center", gap:12 },
  logoEmoji:  { fontSize:30, lineHeight:1 },
  logoName:   { fontSize:17, fontWeight:"bold", color:TEXT, letterSpacing:".02em" },
  logoSub:    { fontSize:11, color:"#4caf50", marginTop:2, fontFamily:"monospace" },
  dot:        { width:10, height:10, borderRadius:"50%", background:"#4caf50", boxShadow:"0 0 8px #4caf50" },
  userBadge:  { display:"flex", alignItems:"center", gap:7, background:"#222", borderRadius:20, padding:"4px 10px 4px 5px", border:`1px solid ${BORDER}` },
  userInitial:{ width:24, height:24, borderRadius:"50%", background:RED, color:"#fff", fontSize:12, fontWeight:"bold", display:"flex", alignItems:"center", justifyContent:"center" },
  userName:   { fontSize:13, color:TEXT },
  userRole:   { fontSize:11, color:MUTED, fontFamily:"monospace" },
  logoutBtn:  { background:"transparent", border:`1px solid ${BORDER}`, borderRadius:8, color:MUTED, width:32, height:32, cursor:"pointer", fontSize:16 },

  // feed
  feed: {
    flex:1, overflowY:"auto", padding:"24px 20px",
    display:"flex", flexDirection:"column", gap:16,
    scrollbarWidth:"thin", scrollbarColor:`${BORDER} transparent`,
  },
  msgRow:     { display:"flex", alignItems:"flex-end", gap:10 },
  avatar:     { fontSize:22, flexShrink:0, marginBottom:2 },
  bubbleBot:  { background:"#242424", border:`1px solid ${BORDER}`, color:TEXT, padding:"12px 16px", borderRadius:"16px 16px 16px 4px", maxWidth:"75%", fontSize:15, lineHeight:1.6 },
  bubbleUser: { background:RED, color:"#fff", padding:"12px 16px", borderRadius:"16px 16px 4px 16px", maxWidth:"75%", fontSize:15, lineHeight:1.6 },
  typingBubble:{ display:"flex", alignItems:"center", gap:5, padding:"14px 18px" },
  dot2:       { display:"inline-block", width:7, height:7, borderRadius:"50%", background:MUTED, animation:"bounce 0.9s infinite ease-in-out" },

  // order
  orderCard:  { background:"#1e1e1e", border:`1px solid ${RED}44`, borderRadius:14, padding:"18px 20px", marginLeft:36, animation:"fadeIn .3s ease" },
  orderLabel: { fontSize:14, color:"#f5a623", marginBottom:12, fontFamily:"monospace", letterSpacing:".05em" },
  orderInputRow:{ display:"flex", gap:8 },
  orderInput: { flex:1, background:"#111", border:`1px solid ${BORDER}`, borderRadius:8, color:TEXT, padding:"10px 14px", fontSize:15, outline:"none" },
  orderSubmit:{ background:RED, border:"none", borderRadius:8, color:"#fff", width:44, fontSize:20, cursor:"pointer" },
  selectRow:  { display:"flex", gap:12 },
  optBtn:     { flex:1, padding:"12px", border:`1px solid ${BORDER}`, borderRadius:10, background:"transparent", color:TEXT, fontSize:15, cursor:"pointer" },
  optBtnActive:{ background:RED, border:`1px solid ${RED}`, color:"#fff" },

  // input bar
  inputBar:   { padding:"14px 16px", borderTop:`1px solid ${BORDER}`, display:"flex", gap:10, alignItems:"flex-end", background:"#141414", flexShrink:0 },
  textarea:   { flex:1, background:"#1e1e1e", border:`1px solid ${BORDER}`, borderRadius:12, color:TEXT, padding:"12px 16px", fontSize:15, resize:"none", outline:"none", lineHeight:1.5, maxHeight:120, overflow:"auto" },
  sendBtn:    { background:RED, border:"none", borderRadius:12, color:"#fff", width:46, height:46, display:"flex", alignItems:"center", justifyContent:"center", cursor:"pointer", flexShrink:0, transition:"opacity .15s" },

  // location picker – overlay
  locOverlay: {
    position:"fixed", inset:0,
    background:"rgba(0,0,0,.65)", backdropFilter:"blur(4px)",
    display:"flex", alignItems:"center", justifyContent:"center",
    zIndex:50, padding:16,
  },
  locModal: {
    background:CARD, border:`1px solid ${BORDER}`, borderRadius:18,
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
    background:"transparent", border:`1px solid ${BORDER}`,
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
  },
  locConfirmBtn: {
    width:"100%", background:"#1a3a1a", border:`1px solid #4caf5066`,
    borderRadius:10, color:"#4caf50", padding:"12px",
    fontSize:15, fontWeight:"bold",
    cursor:"pointer", fontFamily:"'Georgia',serif", transition:"opacity .15s",
    marginTop:4,
  },
  locConfirmBtnDone: {
    width:"100%", background:"#4caf5022", border:`1px solid #4caf5066`,
    borderRadius:10, color:"#4caf50", padding:"12px",
    fontSize:15, fontWeight:"bold",
    cursor:"default", fontFamily:"'Georgia',serif", opacity:.7,
    marginTop:4,
  },

  // location picker – search row
  locSearchRow: { position:"relative" },
  locSearchInput: {
    width:"100%", boxSizing:"border-box",
    background:"#111", border:`1px solid ${BORDER}`,
    borderRadius:8, color:TEXT, padding:"10px 44px 10px 14px",
    fontSize:15, fontFamily:"'Georgia',serif", outline:"none",
  },
  locSearchBtn: {
    position:"absolute", right:10, top:"50%", transform:"translateY(-50%)",
    background:"transparent", border:"none", cursor:"pointer",
    fontSize:18, lineHeight:1,
  },

  // location picker – feedback cards
  locError: {
    background:"#2a1010", border:`1px solid ${RED}55`,
    borderRadius:8, color:"#f87171",
    padding:"10px 14px", fontSize:13, fontFamily:"monospace",
  },
  locAddressCard: {
    background:"#0f1f0f", border:`1px solid #4caf5044`,
    borderRadius:8, padding:"12px 14px",
  },
  locAddressLabel: { fontSize:13, fontWeight:"bold", color:"#4caf50", marginBottom:4, fontFamily:"monospace" },
  locAddressText:  { fontSize:13, color:TEXT, lineHeight:1.5 },
  locCoordsCard: {
    background:"#1a1a1a", border:`1px solid ${BORDER}`,
    borderRadius:8, padding:"10px 14px",
    fontSize:12, color:MUTED, fontFamily:"monospace",
  },

  // location picker – static map
  locMap: { width:"100%", borderRadius:10, border:`1px solid ${BORDER}`, display:"block", marginTop:4 },
};