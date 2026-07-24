/** Tres puntos animados mientras el bot responde. */
export function TypingIndicator() {
  return (
    <div className="p220-msg-row">
      <span className="p220-avatar">🍕</span>
      <div className="p220-bubble p220-bubble-bot p220-typing-bubble">
        <span className="p220-dot" style={{ animationDelay: "0s" }} />
        <span className="p220-dot" style={{ animationDelay: ".18s" }} />
        <span className="p220-dot" style={{ animationDelay: ".36s" }} />
      </div>
    </div>
  );
}

/** Ícono SVG de enviar. */
export function SendIcon() {
  return (
    <svg
      width="20" height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="22" y1="2"  x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}
