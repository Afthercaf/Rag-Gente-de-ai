# src/telegram_bot.py

import os
import httpx
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_BASE  = os.getenv("API_BASE_URL", "http://localhost:8000")

# ==========================================
# MAPA DE ACCIONES
# ==========================================
STATUS_MAP = {
    "confirm": (
        "confirmado",
        "✅ CONFIRMADO ✓",
        "✅ *Pedido confirmado*\nEl cliente será atendido en breve.",
    ),
    "preparing": (
        "preparando",
        "🍕 PREPARANDO ✓",
        "🍕 *Pedido en preparación*\nLos cocineros ya están trabajando en él.",
    ),
    "delivery": (
        "en camino",
        "🛵 EN CAMINO ✓",
        "🛵 *Pedido en camino*\nEl repartidor ya salió con el pedido.",
    ),
    "cancel": (
        "cancelado",
        "❌ CANCELADO ✓",
        "❌ *Pedido cancelado*\nSe notificó la cancelación al sistema.",
    ),
}

# ==========================================
# HANDLERS
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🍕 *Pizzería 220 — Bot activo*\nEsperando pedidos...",
        parse_mode="Markdown",
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data  = query.data          # ej: "confirm_21"
    parts = data.split("_", 1)

    if len(parts) != 2:
        return

    action, order_id = parts

    if action not in STATUS_MAP:
        return

    status, new_button_text, confirm_msg = STATUS_MAP[action]

    # ── Notificar a la API de FastAPI (que actualiza Supabase) ───────────────
    # Esto es lo que hace que el frontend se entere del cambio de estado.
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"{API_BASE}/order/{order_id}/status",
                json={"status": status},
                timeout=30,
            )
            if resp.status_code == 200:
                print(f"[BOT] Pedido {order_id} -> {status} ✅")
            else:
                print(f"[BOT] Error al actualizar pedido {order_id}: {resp.text}")
    except Exception as e:
        print(f"[BOT] Error notificando API: {e}")

    # ── Actualizar el teclado inline en el mensaje original ──────────────────
    original_keyboard = query.message.reply_markup
    if original_keyboard:
        new_keyboard = []
        for row in original_keyboard.inline_keyboard:
            new_row = []
            for button in row:
                if button.callback_data == data:
                    # Marcar el botón presionado
                    new_row.append(
                        InlineKeyboardButton(new_button_text, callback_data=data)
                    )
                else:
                    new_row.append(
                        InlineKeyboardButton(
                            button.text, callback_data=button.callback_data
                        )
                    )
            new_keyboard.append(new_row)

        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(new_keyboard)
        )

    # ── Respuesta en el chat de Telegram ─────────────────────────────────────
    await query.message.reply_text(
        f"{confirm_msg}\n🆔 Pedido: `{order_id}`",
        parse_mode="Markdown",
    )


# ==========================================
# INICIO DEL BOT
# ==========================================

def run_bot():
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN no configurado")
        return

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    print("🤖 Bot Telegram iniciado y escuchando...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    run_bot()