import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Header, HTTPException
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not PUBLIC_URL:
    raise RuntimeError("PUBLIC_URL is not set")

tg = Application.builder().token(BOT_TOKEN).updater(None).build()

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦  SYSTEM ITEMS", callback_data="items")],
        [InlineKeyboardButton("🔄  RESTART", callback_data="restart"),
         InlineKeyboardButton("🔒  CLOSE", callback_data="close")],
        [InlineKeyboardButton("❓  HELP", callback_data="help"),
         InlineKeyboardButton("ℹ️  ABOUT", callback_data="about")]
    ])

def items_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📩  SMS INBOX", callback_data="sms"),
         InlineKeyboardButton("📞  CALL LIST", callback_data="call")],
        [InlineKeyboardButton("📊  SYSTEM STATUS", callback_data="status")],
        [InlineKeyboardButton("🔙  BACK TO MAIN", callback_data="back")]
    ])

def back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙  BACK TO MAIN", callback_data="back")]])

OPENING = """<b>╔════════════════════════════╗
   👑 KING FISHER SYSTEM
╚════════════════════════════╝</b>

✨ <b>System initialized successfully</b>

Welcome back, <b>{name}</b>.

🟢 <b>Status:</b> Online
⚡ <b>Mode:</b> Premium
🛡️ <b>Security:</b> Protected

<i>Select an option below to continue.</i>"""

CLOSING = """<b>╔════════════════════════════╗
      🔒 SESSION CLOSED
╚════════════════════════════╝</b>

Thank you for using <b>King Fisher</b>.

🟡 <b>Status:</b> Standby
🔐 <b>Session:</b> Closed

<i>Send /start whenever you want to open the system again.</i>"""

HELP = """<b>❓ KING FISHER — HELP</b>

📦 <b>System Items</b> — demo sections
🔄 <b>Restart</b> — refresh interface
🔒 <b>Close</b> — close current interface
📊 <b>Status</b> — demo system status

⚠️ SMS/Call sections contain fictional demo data only.
This bot does not read device SMS, call logs, contacts, or private data."""

ABOUT = """<b>ℹ️ ABOUT KING FISHER</b>

👑 <b>King Fisher Bot</b>
Premium Telegram interface demo.

━━━━━━━━━━━━━━━━━━
🟢 Webhook: Active
🟢 Runtime: Python
🟢 Interface: Premium
🧪 Data: Demo only
━━━━━━━━━━━━━━━━━━"""

STATUS = """<b>📊 SYSTEM STATUS</b>

━━━━━━━━━━━━━━━━━━
🟢 <b>Bot:</b> Online
🟢 <b>Webhook:</b> Connected
🟢 <b>API:</b> Ready
🟢 <b>Interface:</b> Premium
🧪 <b>Data:</b> Demo
━━━━━━━━━━━━━━━━━━"""

SMS = """<b>📩 SMS INBOX — DEMO</b>

━━━━━━━━━━━━━━━━━━
<b>1.</b> 🟢 <b>Demo Bank</b>
Your demo transaction was successful.
<i>Today • 10:42 AM</i>

<b>2.</b> 🔵 <b>King Fisher</b>
Welcome to the premium demo system.
<i>Today • 09:18 AM</i>

<b>3.</b> 🟣 <b>Delivery Demo</b>
Your demo package is ready for delivery.
<i>Yesterday • 06:35 PM</i>
━━━━━━━━━━━━━━━━━━
⚠️ <i>Fictional demo messages.</i>"""

CALL = """<b>📞 CALL LIST — DEMO</b>

━━━━━━━━━━━━━━━━━━
<b>1.</b> 🟢 <b>Demo Contact</b>
Incoming • 02:14
<i>Today • 11:25 AM</i>

<b>2.</b> 🔵 <b>Support Demo</b>
Missed • 00:48
<i>Today • 08:10 AM</i>

<b>3.</b> 🟣 <b>King Fisher</b>
Outgoing • 01:36
<i>Yesterday • 07:42 PM</i>
━━━━━━━━━━━━━━━━━━
⚠️ <i>Fictional demo call records.</i>"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "User"
    await update.message.reply_text(OPENING.format(name=name), parse_mode=ParseMode.HTML, reply_markup=main_menu())

async def items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("<b>📦 SYSTEM ITEMS</b>\n\n<i>Select a demo section:</i>", parse_mode=ParseMode.HTML, reply_markup=items_menu())

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("<b>🔄 SYSTEM RESTARTED</b>\n\n━━━━━━━━━━━━━━━━━━\n🟢 Interface refreshed\n🟢 Services ready\n🟢 Session active\n━━━━━━━━━━━━━━━━━━", parse_mode=ParseMode.HTML, reply_markup=main_menu())

async def close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(CLOSING, parse_mode=ParseMode.HTML)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP, parse_mode=ParseMode.HTML, reply_markup=back_menu())

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(ABOUT, parse_mode=ParseMode.HTML, reply_markup=back_menu())

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    if d == "items":
        await q.edit_message_text("<b>📦 SYSTEM ITEMS</b>\n\n<i>Select a demo section:</i>", parse_mode=ParseMode.HTML, reply_markup=items_menu())
    elif d == "sms":
        await q.edit_message_text(SMS, parse_mode=ParseMode.HTML, reply_markup=back_menu())
    elif d == "call":
        await q.edit_message_text(CALL, parse_mode=ParseMode.HTML, reply_markup=back_menu())
    elif d == "status":
        await q.edit_message_text(STATUS, parse_mode=ParseMode.HTML, reply_markup=back_menu())
    elif d == "restart":
        await q.edit_message_text("<b>🔄 SYSTEM RESTARTED</b>\n\n━━━━━━━━━━━━━━━━━━\n🟢 Interface refreshed\n🟢 Services ready\n🟢 Session active\n━━━━━━━━━━━━━━━━━━", parse_mode=ParseMode.HTML, reply_markup=main_menu())
    elif d == "close":
        await q.edit_message_text(CLOSING, parse_mode=ParseMode.HTML)
    elif d == "help":
        await q.edit_message_text(HELP, parse_mode=ParseMode.HTML, reply_markup=back_menu())
    elif d == "about":
        await q.edit_message_text(ABOUT, parse_mode=ParseMode.HTML, reply_markup=back_menu())
    elif d == "back":
        name = q.from_user.first_name or "User"
        await q.edit_message_text(OPENING.format(name=name), parse_mode=ParseMode.HTML, reply_markup=main_menu())

tg.add_handler(CommandHandler("start", start))
tg.add_handler(CommandHandler("items", items))
tg.add_handler(CommandHandler("restart", restart))
tg.add_handler(CommandHandler("close", close))
tg.add_handler(CommandHandler("help", help_cmd))
tg.add_handler(CommandHandler("about", about))
tg.add_handler(CallbackQueryHandler(callbacks))

@asynccontextmanager
async def lifespan(app: FastAPI):
    await tg.initialize()
    await tg.start()
    await tg.bot.set_webhook(
        url=f"{PUBLIC_URL}/telegram/webhook",
        secret_token=WEBHOOK_SECRET or None,
        drop_pending_updates=True
    )
    logging.info("Webhook configured")
    yield
    await tg.bot.delete_webhook()
    await tg.stop()
    await tg.shutdown()

app = FastAPI(title="King Fisher Bot", version="2.0.0", lifespan=lifespan)

@app.get("/")
async def home():
    return {"status": "online", "service": "King Fisher Bot"}

@app.post("/telegram/webhook")
async def webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(default=None)):
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    update = Update.de_json(await request.json(), tg.bot)
    await tg.process_update(update)
    return {"ok": True}
