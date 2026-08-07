import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Header, HTTPException
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set.")

logging.basicConfig(level=logging.INFO)

telegram_app = Application.builder().token(BOT_TOKEN).updater(None).build()

MAIN_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("📦 SYSTEM ITEMS", callback_data="items")],
    [InlineKeyboardButton("🔄 RESTART", callback_data="restart")],
    [InlineKeyboardButton("🔒 CLOSE", callback_data="close")],
    [InlineKeyboardButton("❓ HELP", callback_data="help")],
    [InlineKeyboardButton("ℹ️ ABOUT", callback_data="about")],
])

ITEMS_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("📩 SMS", callback_data="sms")],
    [InlineKeyboardButton("📞 CALL", callback_data="call")],
    [InlineKeyboardButton("🔙 BACK", callback_data="back")],
])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 *KING FISHER BOT*\n\nস্বাগতম! নিচের Menu থেকে একটি অপশন নির্বাচন করুন।",
        parse_mode="Markdown", reply_markup=MAIN_MENU)

async def items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📦 *SYSTEM ITEMS*\n\nএকটি অপশন নির্বাচন করুন:",
        parse_mode="Markdown", reply_markup=ITEMS_MENU)

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 System reloaded successfully.\n\nMain Menu:",
                                    reply_markup=MAIN_MENU)

async def close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔒 Menu closed.\n\nআবার চালু করতে /start লিখুন।")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ *HELP*\n\n/start — Main Menu\n/items — System Items\n/restart — Reload menu\n/close — Close menu\n/help — Help\n/about — About",
        parse_mode="Markdown", reply_markup=MAIN_MENU)

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ℹ️ *ABOUT*\n\nKing Fisher Bot\nVersion 1.0",
                                    parse_mode="Markdown", reply_markup=MAIN_MENU)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "items":
        await query.edit_message_text("📦 *SYSTEM ITEMS*\n\nএকটি অপশন নির্বাচন করুন:",
                                       parse_mode="Markdown", reply_markup=ITEMS_MENU)
    elif query.data == "sms":
        await query.edit_message_text("📩 *SMS*\n\nবর্তমানে কোনো SMS source connected নেই।",
                                       reply_markup=ITEMS_MENU)
    elif query.data == "call":
        await query.edit_message_text("📞 *CALL*\n\nবর্তমানে কোনো Call source connected নেই।",
                                       reply_markup=ITEMS_MENU)
    elif query.data == "back":
        await query.edit_message_text("🚀 *KING FISHER BOT*\n\nMain Menu:",
                                       parse_mode="Markdown", reply_markup=MAIN_MENU)
    elif query.data == "restart":
        await query.edit_message_text("🔄 System reloaded successfully.\n\nMain Menu:",
                                       reply_markup=MAIN_MENU)
    elif query.data == "close":
        await query.edit_message_text("🔒 Menu closed.\n\nআবার চালু করতে /start লিখুন।")
    elif query.data == "help":
        await query.edit_message_text(
            "❓ *HELP*\n\n/start — Main Menu\n/items — System Items\n/restart — Reload menu\n/close — Close menu\n/help — Help\n/about — About",
            parse_mode="Markdown", reply_markup=MAIN_MENU)
    elif query.data == "about":
        await query.edit_message_text("ℹ️ *ABOUT*\n\nKing Fisher Bot\nVersion 1.0",
                                       parse_mode="Markdown", reply_markup=MAIN_MENU)

for command, handler in [
    ("start", start), ("items", items), ("restart", restart),
    ("close", close), ("help", help_command), ("about", about)
]:
    telegram_app.add_handler(CommandHandler(command, handler))
telegram_app.add_handler(CallbackQueryHandler(button_handler))

@asynccontextmanager
async def lifespan(app: FastAPI):
    await telegram_app.initialize()
    await telegram_app.start()
    if PUBLIC_URL:
        await telegram_app.bot.set_webhook(
            url=f"{PUBLIC_URL}/webhook",
            secret_token=WEBHOOK_SECRET or None,
            drop_pending_updates=True,
        )
    yield
    if PUBLIC_URL:
        try:
            await telegram_app.bot.delete_webhook(drop_pending_updates=False)
        except Exception:
            logging.exception("Webhook cleanup failed")
    await telegram_app.stop()
    await telegram_app.shutdown()

app = FastAPI(title="King Fisher Bot", lifespan=lifespan)

@app.get("/")
async def home():
    return {"status": "ok", "bot": "King Fisher Bot"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    update = Update.de_json(await request.json(), bot=telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}
