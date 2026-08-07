import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Header, HTTPException
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("KingFisherBot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not PUBLIC_URL:
    raise RuntimeError("PUBLIC_URL is not set")

telegram_app = Application.builder().token(BOT_TOKEN).updater(None).build()


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("╭━━ 📦 SYSTEM CENTER ━━╮", callback_data="items")],
        [
            InlineKeyboardButton("🔄 RESTART", callback_data="restart"),
            InlineKeyboardButton("🔒 CLOSE", callback_data="close"),
        ],
        [
            InlineKeyboardButton("❓ HELP", callback_data="help"),
            InlineKeyboardButton("ℹ️ ABOUT", callback_data="about"),
        ],
    ])


def items_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📩 SMS INBOX", callback_data="sms"),
            InlineKeyboardButton("📞 CALL LIST", callback_data="call"),
        ],
        [InlineKeyboardButton("📊 SYSTEM STATUS", callback_data="status")],
        [InlineKeyboardButton("🔙 MAIN MENU", callback_data="back")],
    ])


def back_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 BACK TO MAIN", callback_data="back")]
    ])


def restart_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 RESTART AGAIN", callback_data="restart")],
        [InlineKeyboardButton("🔙 MAIN MENU", callback_data="back")],
    ])


OPENING = """<b>╔════════════════════════════════╗
║       👑 KING FISHER
║       PREMIUM SYSTEM
╚════════════════════════════════╝</b>

✨ <b>Welcome, {name}</b>

━━━━━━━━━━━━━━━━━━━━━━━━
🟢 <b>SYSTEM</b>      ONLINE
⚡ <b>MODE</b>        PREMIUM
🛡️ <b>SECURITY</b>    PROTECTED
━━━━━━━━━━━━━━━━━━━━━━━━

<i>Choose an operation below.</i>"""

ITEMS = """<b>╔════════════════════════════════╗
║       📦 SYSTEM CENTER
╚════════════════════════════════╝</b>

<i>Available demo modules</i>

📩 <b>SMS INBOX</b>
   └─ Demo message center

📞 <b>CALL LIST</b>
   └─ Demo call activity

📊 <b>SYSTEM STATUS</b>
   └─ Runtime information

⚠️ <i>All records shown here are fictional demo data.</i>"""

SMS = """<b>📩 SMS INBOX</b>
<i>Premium Demo Center</i>

━━━━━━━━━━━━━━━━━━━━━━━━

🟢 <b>Demo Bank</b>
Your demo transaction was successful.
<code>Today • 10:42 AM</code>

────────────────────────

🔵 <b>King Fisher</b>
Welcome to the premium demo system.
<code>Today • 09:18 AM</code>

────────────────────────

🟣 <b>Delivery Demo</b>
Your demo package is ready.
<code>Yesterday • 06:35 PM</code>

━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ <i>Fictional demo messages only.</i>"""

CALL = """<b>📞 CALL ACTIVITY</b>
<i>Premium Demo Center</i>

━━━━━━━━━━━━━━━━━━━━━━━━

🟢 <b>Demo Contact</b>
Incoming Call • <code>02:14</code>
<code>Today • 11:25 AM</code>

────────────────────────

🔵 <b>Support Demo</b>
Missed Call • <code>00:48</code>
<code>Today • 08:10 AM</code>

────────────────────────

🟣 <b>King Fisher</b>
Outgoing Call • <code>01:36</code>
<code>Yesterday • 07:42 PM</code>

━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ <i>Fictional demo call records only.</i>"""

STATUS = """<b>📊 SYSTEM STATUS</b>
<i>King Fisher Premium Monitor</i>

━━━━━━━━━━━━━━━━━━━━━━━━
🟢 <b>BOT</b>          ONLINE
🟢 <b>WEBHOOK</b>      CONNECTED
🟢 <b>TELEGRAM API</b> READY
🟢 <b>WEB SERVICE</b> ACTIVE
🟢 <b>INTERFACE</b>    PREMIUM
🧪 <b>DATA MODE</b>    DEMO
━━━━━━━━━━━━━━━━━━━━━━━━

<i>All core services are operational.</i>"""

RESTARTED = """<b>╔════════════════════════════════╗
║       🔄 SYSTEM RESTART
╚════════════════════════════════╝</b>

✨ System refresh completed.

━━━━━━━━━━━━━━━━━━━━━━━━
🟢 Interface       READY
🟢 Services        READY
🟢 Webhook         CONNECTED
🟢 Session         ACTIVE
━━━━━━━━━━━━━━━━━━━━━━━━

<i>King Fisher is ready for use.</i>"""

CLOSING = """<b>╔════════════════════════════════╗
║       🔒 SESSION CLOSED
╚════════════════════════════════╝</b>

Thank you for using
<b>👑 KING FISHER PREMIUM</b>

━━━━━━━━━━━━━━━━━━━━━━━━
🟡 SYSTEM     STANDBY
🔐 SESSION    CLOSED
━━━━━━━━━━━━━━━━━━━━━━━━

<i>Send /start to open the system again.</i>"""

HELP = """<b>❓ KING FISHER — HELP</b>

━━━━━━━━━━━━━━━━━━━━━━━━

📦 <b>System Center</b>
Open the demo modules.

🔄 <b>Restart</b>
Refresh the current system interface.

🔒 <b>Close</b>
Close the current session screen.

📊 <b>System Status</b>
View demo runtime information.

━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ <i>SMS and Call sections contain fictional demo data.
They do not access device messages, calls, contacts, or private data.</i>"""

ABOUT = """<b>ℹ️ ABOUT KING FISHER</b>

👑 <b>King Fisher Premium Bot</b>

━━━━━━━━━━━━━━━━━━━━━━━━
⚙️ Runtime       Python
🌐 Web Service   FastAPI
🔗 Webhook       Active
🎨 Interface     Premium
🧪 Data          Demo
━━━━━━━━━━━━━━━━━━━━━━━━

<i>Designed as a premium Telegram bot interface.</i>"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "User"
    await update.message.reply_text(
        OPENING.format(name=name),
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )


async def items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        ITEMS,
        parse_mode=ParseMode.HTML,
        reply_markup=items_menu(),
    )


async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        RESTARTED,
        parse_mode=ParseMode.HTML,
        reply_markup=restart_menu(),
    )


async def close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(CLOSING, parse_mode=ParseMode.HTML)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        HELP, parse_mode=ParseMode.HTML, reply_markup=back_menu()
    )


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        ABOUT, parse_mode=ParseMode.HTML, reply_markup=back_menu()
    )


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data

    if d == "items":
        await q.edit_message_text(
            ITEMS, parse_mode=ParseMode.HTML, reply_markup=items_menu()
        )
    elif d == "sms":
        await q.edit_message_text(
            SMS, parse_mode=ParseMode.HTML, reply_markup=back_menu()
        )
    elif d == "call":
        await q.edit_message_text(
            CALL, parse_mode=ParseMode.HTML, reply_markup=back_menu()
        )
    elif d == "status":
        await q.edit_message_text(
            STATUS, parse_mode=ParseMode.HTML, reply_markup=back_menu()
        )
    elif d == "restart":
        await q.edit_message_text(
            RESTARTED, parse_mode=ParseMode.HTML, reply_markup=restart_menu()
        )
    elif d == "close":
        await q.edit_message_text(CLOSING, parse_mode=ParseMode.HTML)
    elif d == "help":
        await q.edit_message_text(
            HELP, parse_mode=ParseMode.HTML, reply_markup=back_menu()
        )
    elif d == "about":
        await q.edit_message_text(
            ABOUT, parse_mode=ParseMode.HTML, reply_markup=back_menu()
        )
    elif d == "back":
        name = q.from_user.first_name or "User"
        await q.edit_message_text(
            OPENING.format(name=name),
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )


telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("items", items))
telegram_app.add_handler(CommandHandler("restart", restart))
telegram_app.add_handler(CommandHandler("close", close))
telegram_app.add_handler(CommandHandler("help", help_cmd))
telegram_app.add_handler(CommandHandler("about", about))
telegram_app.add_handler(CallbackQueryHandler(callbacks))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await telegram_app.initialize()
    await telegram_app.start()

    webhook_url = f"{PUBLIC_URL}/telegram/webhook"

    await telegram_app.bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET or None,
        drop_pending_updates=True,
    )

    logger.info("Webhook configured: %s", webhook_url)

    # Do not delete the webhook during Render shutdown/spin-down.
    yield

    try:
        await telegram_app.stop()
        await telegram_app.shutdown()
    except Exception:
        logger.exception("Application shutdown error")


app = FastAPI(
    title="King Fisher Premium Bot",
    version="3.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def home():
    return {
        "status": "online",
        "service": "King Fisher Premium Bot",
        "version": "3.0.0",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/telegram/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)

    return {"ok": True}
