// ── Colores ──────────────────────────────────────────────────────────────────
export const RED    = "#e8372a";
export const RED_DK = "#c72d22";
export const DARK   = "#0e0e0e";
export const CARD   = "#161616";
export const CARD2  = "#1c1c1c";
export const BORDER = "#252525";
export const BORDER2= "#2e2e2e";
export const TEXT   = "#f0ede8";
export const MUTED  = "#777";
export const GREEN  = "#4caf50";

// ── Nombres de clase reales (se aplican vía className en los componentes) ───
export const CLS = {
  shell:      "p220-shell",
  header:     "p220-header",
  userName:   "p220-user-name",
  feed:       "p220-feed",
  bubble:     "p220-bubble",
  orderCard:  "p220-order-card",
  inputBar:   "p220-input-bar",
  authCard:   "p220-auth-card",
  locModal:   "p220-loc-modal",
  sendBtn:    "p220-btn-icon",
  micBtn:     "p220-btn-icon",
  logoutBtn:  "p220-btn-icon",
  optBtn:     "p220-opt-btn",
  authSubmit: "p220-btn-primary",
  gpsBtn:     "p220-btn-primary",
  confirmBtn: "p220-btn-confirm",
  closeBtn:   "p220-btn-icon",
  searchBtn:  "p220-btn-icon",
  link:       "p220-link",
};

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
        from { opacity:0; transform:translate(-50%,16px) }
        to   { opacity:1; transform:translate(-50%,0)    }
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

      /* ── Base / cross-device hygiene ─────────────────────────────────── */
      * { box-sizing:border-box; margin:0; padding:0; -webkit-tap-highlight-color:transparent }
      html, body { height:100%; overscroll-behavior-y:none; }
      body { margin:0; -webkit-text-size-adjust:100%; }
      textarea { scrollbar-width:thin; scrollbar-color:${BORDER} transparent }
      input, textarea, select, button { font-family:inherit; }
      button { touch-action:manipulation; }
      img { max-width:100%; }

      /* Custom scrollbars (WebKit) for anything scrollable */
      .p220-feed::-webkit-scrollbar,
      .p220-loc-modal::-webkit-scrollbar,
      textarea::-webkit-scrollbar {
        width:8px;
      }
      .p220-feed::-webkit-scrollbar-thumb,
      .p220-loc-modal::-webkit-scrollbar-thumb,
      textarea::-webkit-scrollbar-thumb {
        background:${BORDER}; border-radius:8px;
      }
      .p220-feed::-webkit-scrollbar-track,
      .p220-loc-modal::-webkit-scrollbar-track,
      textarea::-webkit-scrollbar-track { background:transparent; }

      /* Visible keyboard focus everywhere (accessibility, not just mobile) */
      button:focus-visible, input:focus-visible, textarea:focus-visible, a:focus-visible {
        outline:2px solid ${RED};
        outline-offset:2px;
      }

      /* ── Hover / active micro-interactions (skipped on touch-only devices,
         since :hover sticks after a tap on phones otherwise) ─────────────── */
      @media (hover:hover) and (pointer:fine) {
        .p220-btn-primary:hover   { filter:brightness(1.08); transform:translateY(-1px); }
        .p220-btn-icon:hover      { border-color:${RED}; color:${TEXT}; }
        .p220-opt-btn:hover       { border-color:${RED}; }
        .p220-btn-confirm:hover   { filter:brightness(1.15); }
        .p220-link:hover          { opacity:.8; }
        .p220-btn-primary, .p220-btn-icon, .p220-opt-btn, .p220-btn-confirm {
          transition:all .15s ease;
        }
      }
      .p220-btn-primary:active, .p220-btn-icon:active, .p220-opt-btn:active {
        transform:scale(.97);
      }

      /* ── Small phones (≤480px): tighten rhythm so more of the
         conversation is visible on a short viewport ──────────────────────── */
      @media (max-width:480px) {
        .p220-feed        { padding:16px 12px !important; gap:10px !important; }
        .p220-header      { padding:10px 14px !important; }
        .p220-input-bar   { padding:10px 10px !important; gap:7px !important; }
        .p220-bubble      { max-width:86% !important; font-size:14px !important; }
        .p220-order-card  { margin-left:0 !important; }
        .p220-auth-card   { padding:22px 18px 18px !important; border-radius:14px !important; }
      }

      /* Register form's two-column rows (nombre/teléfono, contraseñas)
         stack into one column on very narrow phones so labels/placeholders
         never get squeezed or truncated. */
      @media (max-width:380px) {
        .p220-row-2col { grid-template-columns:1fr !important; }
      }

      /* ── Short / landscape phones: the on-screen keyboard + a horizontal
         phone leaves very little vertical room, so compress further ─────── */
      @media (max-height:480px) and (orientation:landscape) {
        .p220-header    { padding:6px 14px !important; }
        .p220-feed      { padding:10px 16px !important; gap:8px !important; }
        .p220-input-bar { padding:6px 12px !important; }
      }

      /* ── Tablets (600–899px): a little more breathing room, reveal the
         user's name next to their avatar ─────────────────────────────────── */
      @media (min-width:600px) {
        .p220-user-name { display:inline !important; }
      }
      @media (min-width:600px) and (max-width:899px) {
        .p220-feed { padding:26px 28px; }
      }

      /* ── Desktop / large viewports (≥900px): present the chat as a
         floating card instead of an edge-to-edge column, like a real
         desktop app rather than a stretched phone screen ─────────────────── */
      @media (min-width:900px) {
        .p220-shell {
          height:min(860px,92dvh) !important;
          margin:24px 0;
          border-radius:20px !important;
          overflow:hidden;
          box-shadow:0 30px 80px rgba(0,0,0,.55), 0 0 0 1px ${BORDER2};
        }
        .p220-loc-modal {
          border-radius:18px !important;
          margin-bottom:24px;
        }
        .p220-loc-overlay { align-items:center !important; }
      }

      /* ── Very large / wide screens: cap width so lines don't stretch
         uncomfortably wide ─────────────────────────────────────────────────── */
      @media (min-width:1200px) {
        .p220-shell { width:min(760px,100vw) !important; }
      }

      /* ── Respect reduced-motion preference ───────────────────────────────── */
      @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
          animation-duration:.001ms !important;
          animation-iteration-count:1 !important;
          transition-duration:.001ms !important;
        }
      }
    `;
    document.head.appendChild(st);
  }
}

// ── Objeto de estilos compartidos ────────────────────────────────────────────
export const s = {
  // layout
  root: {
    minHeight:"100dvh", background:DARK,
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
    width:"min(440px,100vw)", padding:"0 16px 40px",
    display:"flex", flexDirection:"column", alignItems:"center",
  },
  authLogo: { display:"flex", flexDirection:"column", alignItems:"center", gap:6, marginBottom:24 },
  authCard: {
    width:"100%", background:CARD,
    border:`1px solid ${BORDER2}`, borderRadius:18,
    padding:"28px 28px 24px",
  },
  authTitle: { fontSize:"clamp(18px,5vw,20px)", fontWeight:"bold", color:TEXT, marginBottom:20, textAlign:"center" },
  fieldWrap: { marginBottom:14 },
  fieldLabel:{ display:"block", fontSize:13, color:MUTED, marginBottom:5, fontFamily:"monospace" },
  authInput: {
    width:"100%", boxSizing:"border-box",
    background:"#111", border:`1px solid ${BORDER2}`,
    borderRadius:8, color:TEXT, padding:"12px 14px",
    fontSize:16, fontFamily:"'Georgia',serif", outline:"none",
    transition:"border-color .2s",
  },
  select: {
    width:"100%", boxSizing:"border-box",
    background:"#111", border:`1px solid ${BORDER2}`,
    borderRadius:8, color:TEXT, padding:"12px 14px",
    fontSize:16, fontFamily:"'Georgia',serif", outline:"none",
  },
  authSubmit: {
    width:"100%", marginTop:6,
    background:RED, border:"none", borderRadius:10,
    color:"#fff", padding:"13px",
    fontSize:16, fontWeight:"bold",
    cursor:"pointer", fontFamily:"'Georgia',serif",
    transition:"opacity .15s, background .15s, transform .15s, filter .15s",
    boxShadow:"0 2px 14px rgba(232,55,42,.3)",
    minHeight:48, // comfortable thumb target
  },
  authLink: { color:RED, cursor:"pointer", textDecoration:"underline" },
  errorMsg: {
    background:"#1e0a0a", border:`1px solid ${RED}44`,
    borderRadius:8, color:"#f87171",
    padding:"10px 14px", fontSize:13,
    marginBottom:12, fontFamily:"monospace",
    wordBreak:"break-word",
  },

  // chat shell
  shell: {
    position:"relative", zIndex:1,
    width:"min(700px,100vw)", height:"100dvh",
    display:"flex", flexDirection:"column",
    background:CARD, borderLeft:`1px solid ${BORDER}`, borderRight:`1px solid ${BORDER}`,
    transition:"height .2s ease, border-radius .2s ease",
  },
  header: {
    padding:"14px 20px", borderBottom:`1px solid ${BORDER}`,
    display:"flex", alignItems:"center", justifyContent:"space-between",
    background:"#111", flexShrink:0,
    paddingTop:"calc(14px + env(safe-area-inset-top))",
    gap:10, flexWrap:"nowrap",
  },
  logoWrap:   { display:"flex", alignItems:"center", gap:12, minWidth:0 },
  logoEmoji:  { fontSize:26, lineHeight:1, filter:"drop-shadow(0 1px 6px rgba(232,55,42,.35))", flexShrink:0 },
  logoName:   { fontSize:"clamp(15px,4vw,17px)", fontWeight:"bold", color:TEXT, letterSpacing:".02em", whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" },
  logoSub:    { fontSize:11, color:GREEN, marginTop:2, fontFamily:"monospace", display:"flex", alignItems:"center", gap:5 },
  logoSubDot: { display:"inline-block", width:6, height:6, borderRadius:"50%", background:GREEN, boxShadow:`0 0 6px ${GREEN}` },
  dot:        { width:9, height:9, borderRadius:"50%", background:GREEN, boxShadow:`0 0 8px ${GREEN}`, flexShrink:0 },
  userBadge:  { display:"flex", alignItems:"center", gap:7, background:"#1a1a1a", borderRadius:20, padding:"4px 12px 4px 5px", border:`1px solid ${BORDER2}`, minWidth:0 },
  userInitial:{ width:26, height:26, borderRadius:"50%", background:RED, color:"#fff", fontSize:12, fontWeight:"bold", display:"flex", alignItems:"center", justifyContent:"center", boxShadow:"0 0 8px rgba(232,55,42,.35)", flexShrink:0 },
  // Hidden by default on narrow phones; the .p220-user-name media rule
  // reveals it from 600px up so the badge doesn't crowd the header on phones.
  userName:   { fontSize:13, color:TEXT, display:"none", whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis", maxWidth:120 },
  userRole:   { fontSize:11, color:MUTED, fontFamily:"monospace", flexShrink:0 },
  logoutBtn:  { background:"transparent", border:`1px solid ${BORDER2}`, borderRadius:8, color:MUTED, width:34, height:34, cursor:"pointer", fontSize:15, display:"flex", alignItems:"center", justifyContent:"center", flexShrink:0 },

  // feed
  feed: {
    flex:1, overflowY:"auto", overscrollBehavior:"contain",
    padding:"24px 20px",
    display:"flex", flexDirection:"column", gap:14,
    scrollbarWidth:"thin", scrollbarColor:`${BORDER} transparent`,
    WebkitOverflowScrolling:"touch",
  },
  msgRow:     { display:"flex", alignItems:"flex-end", gap:10, animation:"fadeIn .25s ease" },
  avatar:     { fontSize:20, flexShrink:0, marginBottom:2 },
  bubbleBot:  { background:CARD2, border:`1px solid ${BORDER2}`, color:TEXT, padding:"11px 15px", borderRadius:"16px 16px 16px 4px", maxWidth:"78%", fontSize:14.5, lineHeight:1.6, wordBreak:"break-word" },
  bubbleUser: { background:`linear-gradient(135deg,#d42d21,${RED})`, color:"#fff", padding:"11px 15px", borderRadius:"16px 16px 4px 16px", maxWidth:"78%", fontSize:14.5, lineHeight:1.6, boxShadow:"0 2px 12px rgba(232,55,42,.22)", wordBreak:"break-word" },
  typingBubble:{ display:"flex", alignItems:"center", gap:5, padding:"13px 16px" },
  dot2:       { display:"inline-block", width:7, height:7, borderRadius:"50%", background:MUTED, animation:"bounce 0.9s infinite ease-in-out" },

  // order
  orderCard:  { background:"#1a1a1a", border:`1px solid ${RED}33`, borderRadius:14, padding:"16px 18px", marginLeft:34, animation:"fadeIn .3s ease" },
  orderLabel: { fontSize:13.5, color:"#f5a623", marginBottom:12, fontFamily:"monospace", letterSpacing:".05em" },
  orderInputRow:{ display:"flex", gap:8 },
  orderInput: { flex:1, minWidth:0, background:"#111", border:`1px solid ${BORDER2}`, borderRadius:8, color:TEXT, padding:"12px 14px", fontSize:16, outline:"none" },
  orderSubmit:{ background:RED, border:"none", borderRadius:8, color:"#fff", width:46, minHeight:46, fontSize:20, cursor:"pointer", flexShrink:0 },
  selectRow:  { display:"flex", gap:10, flexWrap:"wrap" },
  optBtn:     { flex:"1 1 100px", padding:"12px", border:`1px solid ${BORDER2}`, borderRadius:10, background:"transparent", color:TEXT, fontSize:15, cursor:"pointer", minHeight:44 },
  optBtnActive:{ background:RED, border:`1px solid ${RED}`, color:"#fff" },

  // input bar
  inputBar: {
    padding:"12px 16px", borderTop:`1px solid ${BORDER}`,
    display:"flex", gap:9, alignItems:"flex-end", background:"#111", flexShrink:0,
    paddingBottom:"calc(12px + env(safe-area-inset-bottom))",
  },
  textarea:   {
    flex:1, minWidth:0, background:CARD2, border:`1px solid ${BORDER2}`, borderRadius:12,
    color:TEXT, padding:"12px 15px", fontSize:16, resize:"none", outline:"none",
    lineHeight:1.5, maxHeight:120, overflow:"auto",
    fontFamily:"'Georgia',serif", transition:"border-color .2s, background .2s",
  },
  textareaListening: {
    borderColor:"#ef4444", background:"#1e0a0a", color:"#fca5a5",
  },
  sendBtn:    {
    background:RED, border:"none", borderRadius:12, color:"#fff",
    width:46, height:46, display:"flex", alignItems:"center", justifyContent:"center",
    cursor:"pointer", flexShrink:0, transition:"all .15s",
    boxShadow:"0 2px 10px rgba(232,55,42,.28)",
  },

  // ── Mic button ──────────────────────────────────────────────────────────────
  micBtn: {
    position:"relative", width:46, height:46, borderRadius:12, flexShrink:0,
    background:CARD2, border:`1px solid ${BORDER2}`,
    color:MUTED, fontSize:18, cursor:"pointer",
    display:"flex", alignItems:"center", justifyContent:"center",
    transition:"all .2s", overflow:"hidden",
  },
  micBtnActive: {
    background:"#ef4444", borderColor:"#ef4444", color:"#fff",
    animation:"micGlow 1.4s ease-in-out infinite",
  },
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
  micWave: { display:"flex", alignItems:"center", gap:2, height:20 },
  micWaveBar: {
    display:"inline-block", width:3, background:"#fff",
    borderRadius:2, height:4,
  },
  micWaveBar1: { animation:"waveBar .6s ease-in-out infinite" },
  micWaveBar2: { animation:"waveBar .6s ease-in-out .1s infinite" },
  micWaveBar3: { animation:"waveBar .6s ease-in-out .2s infinite" },
  micWaveBar4: { animation:"waveBar .6s ease-in-out .15s infinite" },
  micWaveBar5: { animation:"waveBar .6s ease-in-out .05s infinite" },

  // ── Toast flotante de escucha ──────────────────────────────────────────────
  listenToast: {
    position:"fixed", bottom:"calc(100px + env(safe-area-inset-bottom))", left:"50%", transform:"translateX(-50%)",
    background:"#161616", border:`1px solid ${BORDER2}`,
    color:TEXT, padding:"10px 18px", borderRadius:28,
    display:"flex", alignItems:"center", gap:12,
    fontSize:13, animation:"slideUp .3s ease", zIndex:1000,
    maxWidth:"92vw", whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis",
    boxShadow:"0 8px 28px rgba(0,0,0,.55)",
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
    padding:"6px 12px", borderRadius:16, cursor:"pointer",
    fontSize:12, transition:"all .2s", minHeight:32,
  },

  // unsupported-voice banner (was a hardcoded fixed-position block in
  // ChatScreen — now responsive: shrinks and wraps instead of overflowing
  // on very narrow phones)
  voiceUnsupported: {
    position:"fixed", bottom:"calc(100px + env(safe-area-inset-bottom))", left:"50%",
    transform:"translateX(-50%)",
    background:"rgba(239,68,68,.92)", color:"#fff",
    padding:"10px 18px", borderRadius:12, fontSize:13, zIndex:1000,
    backdropFilter:"blur(10px)",
    maxWidth:"min(360px,92vw)", textAlign:"center", lineHeight:1.4,
  },

  // location picker – overlay
  locOverlay: {
    position:"fixed", inset:0,
    background:"rgba(0,0,0,.72)", backdropFilter:"blur(4px)",
    display:"flex", alignItems:"flex-end", justifyContent:"center",
    zIndex:50, padding:0,
  },
  locModal: {
    background:CARD, border:`1px solid ${BORDER2}`, borderRadius:"18px 18px 0 0",
    width:"min(440px,100%)", maxHeight:"92dvh",
    overflowY:"auto", display:"flex", flexDirection:"column",
    scrollbarWidth:"thin", scrollbarColor:`${BORDER} transparent`,
    paddingBottom:"env(safe-area-inset-bottom)",
  },

  // location picker – header (sticky)
  locHeader: {
    padding:"16px 20px", borderBottom:`1px solid ${BORDER}`,
    display:"flex", alignItems:"center", justifyContent:"space-between",
    background:CARD, position:"sticky", top:0, zIndex:1,
  },
  locTitle: { fontSize:"clamp(16px,4.5vw,18px)", fontWeight:"bold", color:TEXT, fontFamily:"'Georgia',serif" },
  locCloseBtn: {
    background:"transparent", border:`1px solid ${BORDER2}`,
    borderRadius:8, color:MUTED, width:34, height:34,
    cursor:"pointer", fontSize:18, display:"flex",
    alignItems:"center", justifyContent:"center", flexShrink:0,
  },

  // location picker – body
  locBody: { padding:"20px", display:"flex", flexDirection:"column", gap:14 },

  // location picker – buttons
  locGpsBtn: {
    width:"100%", background:RED, border:"none", borderRadius:10,
    color:"#fff", padding:"13px", fontSize:15, fontWeight:"bold",
    cursor:"pointer", fontFamily:"'Georgia',serif", transition:"opacity .15s, transform .15s, filter .15s",
    boxShadow:"0 2px 12px rgba(232,55,42,.28)", minHeight:48,
  },
  locConfirmBtn: {
    width:"100%", background:"#0f1e0f", border:`1px solid #4caf5055`,
    borderRadius:10, color:GREEN, padding:"13px",
    fontSize:15, fontWeight:"bold",
    cursor:"pointer", fontFamily:"'Georgia',serif", transition:"opacity .15s, filter .15s", marginTop:4,
    minHeight:48,
  },
  locConfirmBtnDone: {
    width:"100%", background:"#4caf5015", border:`1px solid #4caf5055`,
    borderRadius:10, color:GREEN, padding:"13px",
    fontSize:15, fontWeight:"bold",
    cursor:"default", fontFamily:"'Georgia',serif", opacity:.65, marginTop:4,
    minHeight:48,
  },

  // location picker – search row
  locSearchRow: { position:"relative" },
  locSearchInput: {
    width:"100%", boxSizing:"border-box",
    background:"#111", border:`1px solid ${BORDER2}`,
    borderRadius:8, color:TEXT, padding:"12px 44px 12px 14px",
    fontSize:16, fontFamily:"'Georgia',serif", outline:"none",
  },
  locSearchBtn: {
    position:"absolute", right:8, top:"50%", transform:"translateY(-50%)",
    background:"transparent", border:"none", cursor:"pointer", fontSize:18, lineHeight:1,
    width:34, height:34, borderRadius:8,
  },

  // location picker – feedback cards
  locError: {
    background:"#1e0a0a", border:`1px solid ${RED}44`,
    borderRadius:8, color:"#f87171", padding:"10px 14px", fontSize:13, fontFamily:"monospace",
    wordBreak:"break-word",
  },
  locAddressCard: {
    background:"#0d1a0d", border:`1px solid #4caf5033`,
    borderRadius:8, padding:"12px 14px",
  },
  locAddressLabel: { fontSize:13, fontWeight:"bold", color:GREEN, marginBottom:4, fontFamily:"monospace" },
  locAddressText:  { fontSize:13, color:TEXT, lineHeight:1.5, wordBreak:"break-word" },
  locCoordsCard: {
    background:"#1a1a1a", border:`1px solid ${BORDER}`,
    borderRadius:8, padding:"10px 14px", fontSize:12, color:MUTED, fontFamily:"monospace",
  },

  // location picker – static map
  locMap: { width:"100%", borderRadius:10, border:`1px solid ${BORDER2}`, display:"block", marginTop:4 },

  // ── payment / location-share action buttons (previously hardcoded inline
  // in ChatScreen with no wrapping or width limits — now bounded so they
  // never overflow a narrow phone screen) ─────────────────────────────────
  payLink: {
    display:"inline-block", padding:"12px 24px",
    background:"linear-gradient(135deg, #009ee3 0%, #0073b7 100%)",
    color:"#fff", borderRadius:10, textDecoration:"none",
    fontWeight:"bold", fontSize:"clamp(13px,3.6vw,15px)",
    boxShadow:"0 4px 15px rgba(0, 158, 227, 0.35)",
    transition:"transform 0.15s ease, box-shadow 0.15s ease",
    cursor:"pointer", maxWidth:"100%", textAlign:"center",
  },
  shareLocBtn: {
    backgroundColor:"#10b981", color:"white",
    padding:"8px 16px", borderRadius:8, border:"none",
    fontSize:14, fontWeight:"bold",
    display:"inline-flex", alignItems:"center", gap:8,
    boxShadow:"0 2px 10px rgba(16,185,129,.25)",
    maxWidth:"100%", flexWrap:"wrap",
  },
};