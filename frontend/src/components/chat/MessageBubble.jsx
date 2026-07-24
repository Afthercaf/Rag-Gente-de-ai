/** Renderiza negrita (**texto**) y saltos de línea. */
function MarkdownText({ text }) {
  return (
    <span>
      {text.split("\n").map((line, li, arr) => (
        <span key={li}>
          {line.split(/(\*\*[^*]+\*\*)/g).map((part, pi) =>
            part.startsWith("**") && part.endsWith("**")
              ? <strong key={pi}>{part.slice(2, -2)}</strong>
              : part
          )}
          {li < arr.length - 1 && <br />}
        </span>
      ))}
    </span>
  );
}

/** Burbuja individual de chat (bot o usuario). */
export function MessageBubble({ msg }) {
  const isBot = msg.role === "bot";
  return (
    <div className={`p220-msg-row${isBot ? "" : " is-user"}`}>
      {isBot && <span className="p220-avatar">🍕</span>}
      <div className={`p220-bubble ${isBot ? "p220-bubble-bot" : "p220-bubble-user"}`}>
        <MarkdownText text={msg.text} />
      </div>
    </div>
  );
}