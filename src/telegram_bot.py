import os
import logging
import httpx
import asyncio          
import time
from collections import defaultdict, deque
import core.config  # Carga centralizada del entorno.
from core.telegram_callback import verify_callback

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_BASE = os.getenv("API_BASE_URL")
API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
ADMIN_IDS = {
    int(value.strip())
    for value in os.getenv("TELEGRAM_ADMIN_IDS", "").split(",")
    if value.strip().isdigit()
}
_callback_attempts = defaultdict(deque)
CALLBACK_LIMIT = 12
CALLBACK_WINDOW_SECONDS = 60

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# ==========================================
# CONFIGURACIÓN DE ESTADOS
# ==========================================

STATUS_MAP = {
    "confirm": {
        "status": "confirmado",
        "label": "✅ CONFIRMADO",
        "message": "✅ Pedido confirmado"
    },
    "preparing": {
        "status": "preparando",
        "label": "🍕 PREPARANDO",
        "message": "🍕 Pedido en preparación"
    },
    "delivery": {
        "status": "en camino",
        "label": "🛵 EN CAMINO",
        "message": "🛵 Pedido en camino"
    },
    "delivered": {
        "status": "entregado",
        "label": "🎉 ENTREGADO",
        "message": "🎉 Pedido entregado"
    },
    "cancel": {
        "status": "cancelado",
        "label": "❌ CANCELADO",
        "message": "❌ Pedido cancelado"
    }
}

# SOLO ESTOS BLOQUEAN BOTONES
FINAL_STATES = {
    "cancelado",
    "entregado"
}


# =====================================================
# START
# =====================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🍕 Bot de Pizzería 220 activo"
    )

# =====================================================
# API
# =====================================================

async def update_order(order_id: str, status: str):

    if not API_BASE or not API_TOKEN:
        logger.error("API_BASE_URL o TELEGRAM_API_TOKEN no configurado")
        return False

    try:

        async with httpx.AsyncClient(timeout=30) as client:

            response = await client.patch(
                f"{API_BASE}/order/{order_id}/status",
                json={"status": status},
                headers={"Authorization": f"Bearer {API_TOKEN}"},
            )

            logger.info(
                f"Pedido {order_id} -> {status} | {response.status_code}"
            )

            return response.status_code == 200

    except Exception as e:

        logger.error(f"Error API: {e}")

        return False

# =====================================================
# CREAR TECLADO DESHABILITADO
# =====================================================

def build_disabled_keyboard(keyboard):

    disabled_rows = []

    for row in keyboard.inline_keyboard:

        new_row = []

        for button in row:

            if button.url:

                new_row.append(
                    InlineKeyboardButton(
                        text=button.text,
                        url=button.url
                    )
                )

            else:

                new_row.append(
                    InlineKeyboardButton(
                        text=f"🔒 {button.text}",
                        callback_data="disabled"
                    )
                )

        disabled_rows.append(new_row)

    return InlineKeyboardMarkup(disabled_rows)

# =====================================================
# CALLBACKS
# =====================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    actor_id = update.effective_user.id if update.effective_user else None
    if actor_id not in ADMIN_IDS:
        logger.warning("Callback Telegram no autorizado: user_id=%s", actor_id)
        await query.answer("No autorizado", show_alert=True)
        return

    now = time.monotonic()
    attempts = _callback_attempts[actor_id]
    while attempts and now - attempts[0] > CALLBACK_WINDOW_SECONDS:
        attempts.popleft()
    if len(attempts) >= CALLBACK_LIMIT:
        await query.answer("Demasiadas solicitudes. Intenta más tarde.", show_alert=True)
        return
    attempts.append(now)

    data = query.data

    if data == "disabled":

        await query.answer(
            "Este pedido ya fue procesado",
            show_alert=True
        )

        return

    verified = verify_callback(data)
    if verified is None:
        logger.warning("Callback Telegram inválido o expirado.")
        await query.answer("Acción inválida o expirada", show_alert=True)
        return
    action, order_id = verified

    if action not in STATUS_MAP:

        logger.error(f"Acción inválida: {action}")

        return

    config = STATUS_MAP[action]

    status = config["status"]

    success = await update_order(
        order_id,
        status
    )

    if not success:

        await query.answer(
            "Error actualizando pedido",
            show_alert=True
        )

        return

    try:

        current_keyboard = query.message.reply_markup

        if current_keyboard:

            if status in FINAL_STATES:

                await query.edit_message_reply_markup(
                    reply_markup=build_disabled_keyboard(
                        current_keyboard
                    )
                )

            else:

                new_rows = []

                for row in current_keyboard.inline_keyboard:

                    new_row = []

                    for button in row:

                        if button.url:

                            new_row.append(
                                InlineKeyboardButton(
                                    text=button.text,
                                    url=button.url
                                )
                            )

                        elif button.callback_data == data:

                            new_row.append(
                                InlineKeyboardButton(
                                    text=f"✅ {button.text}",
                                    callback_data="disabled"
                                )
                            )

                        else:

                            new_row.append(
                                InlineKeyboardButton(
                                    text=button.text,
                                    callback_data=button.callback_data
                                )
                            )

                    new_rows.append(new_row)

                await query.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup(new_rows)
                )

    except Exception as e:

        logger.error(
            f"Error actualizando teclado: {e}"
        )

    try:

        await query.message.reply_text(
            f"{config['message']}\n\n"
            f"🆔 Pedido #{order_id}"
        )

    except Exception as e:

        logger.error(
            f"Error enviando confirmación: {e}"
        )

# =====================================================
# ERROR HANDLER
# =====================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.error(
        msg="Exception while handling update:",
        exc_info=context.error
    )

# =====================================================
# MAIN
# =====================================================

async def run_bot():

    if not BOT_TOKEN or not ADMIN_IDS or not API_BASE or not API_TOKEN:
        logger.error(
            "Telegram requiere TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_IDS, "
            "API_BASE_URL y TELEGRAM_API_TOKEN"
        )
        return

    logger.info("Iniciando bot Telegram...")

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_error_handler(error_handler)

    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)

    logger.info("Bot Telegram iniciado correctamente")
    await asyncio.Event().wait()

# =====================================================
# ENTRYPOINT
# =====================================================
if __name__ == "__main__":
    asyncio.run(run_bot())
