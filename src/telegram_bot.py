import os
import logging
import httpx

from dotenv import load_dotenv

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

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_BASE = os.getenv("API_BASE_URL", "https://ai-backend-gu75.onrender.com")

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

    try:

        async with httpx.AsyncClient(timeout=30) as client:

            response = await client.patch(
                f"{API_BASE}/order/{order_id}/status",
                json={"status": status}
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

    data = query.data

    logger.info(f"Callback recibido: {data}")

    if data == "disabled":

        await query.answer(
            "Este pedido ya fue procesado",
            show_alert=True
        )

        return

    try:

        action, order_id = data.split("_", 1)

    except ValueError:

        logger.error(f"Callback inválido: {data}")

        return

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

    if not BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN no configurado")
        return

    print("Iniciando bot Telegram...")

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_error_handler(error_handler)

    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)

    print("Bot Telegram iniciado correctamente")
    await asyncio.Event().wait()

# =====================================================
# ENTRYPOINT
# =====================================================
if __name__ == "__main__":
    asyncio.run(run_bot())