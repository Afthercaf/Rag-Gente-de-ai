import { s } from "../../styles/theme";

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
    <div style={{ ...s.msgRow, justifyContent: isBot ? "flex-start" : "flex-end" }}>
      {isBot && <span style={s.avatar}>🍕</span>}
      <div style={isBot ? s.bubbleBot : s.bubbleUser}>
        <MarkdownText text={msg.text} />
      </div>
    </div>
  );
}
