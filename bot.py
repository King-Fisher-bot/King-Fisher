"""
King Fisher Bot - Real Device Data Integration
Telegram bot that receives and displays real SMS/Call logs from Android devices

Environment Variables:
- BOT_TOKEN: Telegram bot token from BotFather
- PUBLIC_URL: Public URL of the bot (e.g., https://your-bot.onrender.com)
- WEBHOOK_SECRET: Secret token for webhook security

Deployment: Render, Heroku, or any FastAPI-compatible platform
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Dict, List
from datetime import datetime

from fastapi import FastAPI, Request, Header, HTTPException
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ============ LOGGING ============
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("KingFisherBot")

# ============ ENVIRONMENT ============
BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN is not set")
if not PUBLIC_URL:
    raise RuntimeError("❌ PUBLIC_URL is not set")

# ============ TELEGRAM APP ============
telegram_app = Application.builder().token(BOT_TOKEN).updater(None).build()

# ============ DATA STORAGE ============
DEVICE_DATA = {
    "sms": {},      # device_id -> list of SMS
    "calls": {},    # device_id -> list of calls
    "devices": set()
}
MAX_HISTORY = 100  # Maximum items to keep per device

class DeviceDataManager:
    """Manages device data storage and retrieval"""
    
    @staticmethod
    def store_sms(device_id: str, sms_list: List[Dict]):
        if device_id not in DEVICE_DATA["sms"]:
            DEVICE_DATA["sms"][device_id] = []
        
        for sms in sms_list:
            sms_id = sms.get("id")
            if sms_id:
                # Avoid duplicates
                existing = [s for s in DEVICE_DATA["sms"][device_id] if s.get("id") == sms_id]
                if not existing:
                    DEVICE_DATA["sms"][device_id].append(sms)
        
        # Keep only recent items
        DEVICE_DATA["sms"][device_id] = DEVICE_DATA["sms"][device_id][-MAX_HISTORY:]
        DEVICE_DATA["devices"].add(device_id)

    @staticmethod
    def store_calls(device_id: str, call_list: List[Dict]):
        if device_id not in DEVICE_DATA["calls"]:
            DEVICE_DATA["calls"][device_id] = []
        
        for call in call_list:
            call_id = call.get("id")
            if call_id:
                existing = [c for c in DEVICE_DATA["calls"][device_id] if c.get("id") == call_id]
                if not existing:
                    DEVICE_DATA["calls"][device_id].append(call)
        
        DEVICE_DATA["calls"][device_id] = DEVICE_DATA["calls"][device_id][-MAX_HISTORY:]
        DEVICE_DATA["devices"].add(device_id)

    @staticmethod
    def get_sms(device_id: str, limit: int = 10) -> List[Dict]:
        return DEVICE_DATA["sms"].get(device_id, [])[-limit:]

    @staticmethod
    def get_calls(device_id: str, limit: int = 10) -> List[Dict]:
        return DEVICE_DATA["calls"].get(device_id, [])[-limit:]

    @staticmethod
    def get_devices() -> List[str]:
        return list(DEVICE_DATA["devices"])

    @staticmethod
    def get_stats() -> Dict:
        sms_count = sum(len(v) for v in DEVICE_DATA["sms"].values())
        call_count = sum(len(v) for v in DEVICE_DATA["calls"].values())
        return {
            "devices": len(DEVICE_DATA["devices"]),
            "sms": sms_count,
            "calls": call_count,
            "total": sms_count + call_count
        }

# ============ UI COMPONENTS ============
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 SYSTEM ITEMS", callback_data="items")],
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
        [InlineKeyboardButton("🔙 BACK TO MAIN", callback_data="back")],
    ])

def back_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 BACK TO MAIN", callback_data="back")]
    ])

# ============ TEXT TEMPLATES ============
OPENING = """<b>╔════════════════════════════╗
   👑 KING FISHER SYSTEM
╚════════════════════════════╝</b>

✨ <b>System initialized successfully</b>

Welcome back, <b>{name}</b>.

🟢 <b>Status:</b> Online
⚡ <b>Mode:</b> Real Data
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

📦 <b>System Items</b> — View real SMS/Call logs
🔄 <b>Restart</b> — Refresh interface
🔒 <b>Close</b> — Close current interface
📊 <b>Status</b> — Show connected devices and stats

<i>Data is collected in real-time from your Android device.</i>"""

ABOUT = """<b>ℹ️ ABOUT KING FISHER</b>

👑 <b>King Fisher Bot</b>
Premium Telegram bot with real device integration.

━━━━━━━━━━━━━━━━━━
🟢 Webhook: Active
🟢 Runtime: Python (FastAPI)
🟢 Mode: Real Data
🟢 Platform: Android + Termux
━━━━━━━━━━━━━━━━━━

<i>Real-time SMS and call log monitoring.</i>"""

# ============ FORMATTERS ============
def format_realtime_sms(sms_list: List[Dict]) -> str:
    """Format SMS data for display"""
    if not sms_list:
        return "📭 <b>No SMS messages found</b>\n\n<i>Make sure your Android device is connected and running the sender script.</i>"
    
    lines = ["<b>📩 REAL SMS INBOX</b>", "━━━━━━━━━━━━━━━━━━"]
    
    for i, sms in enumerate(sms_list[:10], 1):
        sender = sms.get("sender", "Unknown")
        body = sms.get("body", "")[:100]
        timestamp = sms.get("timestamp", "")
        msg_type = sms.get("type", "received")
        
        icon = "📥" if msg_type == "received" else "📤"
        time_str = timestamp[:16] if timestamp else "Unknown"
        
        lines.append(f"{i}. {icon} <b>{sender}</b>")
        lines.append(f"   {body[:80]}{'...' if len(body) > 80 else ''}")
        lines.append(f"   <i>{time_str}</i>")
        lines.append("")
    
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 <i>Total: {len(sms_list)} messages</i>")
    return "\n".join(lines)

def format_realtime_calls(call_list: List[Dict]) -> str:
    """Format call data for display"""
    if not call_list:
        return "📭 <b>No call logs found</b>\n\n<i>Make sure your Android device is connected and running the sender script.</i>"
    
    lines = ["<b>📞 REAL CALL LOGS</b>", "━━━━━━━━━━━━━━━━━━"]
    
    icons = {
        "Incoming": "📞",
        "Outgoing": "📤",
        "Missed": "❌",
        "Rejected": "🚫",
        "Blocked": "⛔",
        "Voicemail": "🎙️"
    }
    
    for i, call in enumerate(call_list[:10], 1):
        number = call.get("number", "Unknown")
        name = call.get("name", "Unknown")
        duration = call.get("duration", "0")
        timestamp = call.get("timestamp", "")
        call_type = call.get("type", "Unknown")
        
        icon = icons.get(call_type, "📞")
        
        # Format duration
        duration_str = "0s"
        if duration.isdigit():
            dur = int(duration)
            if dur >= 60:
                duration_str = f"{dur//60}m {dur%60}s"
            else:
                duration_str = f"{dur}s"
        
        time_str = timestamp[:16] if timestamp else "Unknown"
        
        lines.append(f"{i}. {icon} <b>{name}</b> ({number})")
        lines.append(f"   📱 {call_type} • ⏱️ {duration_str}")
        lines.append(f"   <i>{time_str}</i>")
        lines.append("")
    
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 <i>Total: {len(call_list)} calls</i>")
    return "\n".join(lines)

# ============ COMMAND HANDLERS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "User"
    await update.message.reply_text(
        OPENING.format(name=name),
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>🔄 SYSTEM RESTARTED</b>\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🟢 Interface refreshed\n"
        "🟢 Services ready\n"
        "🟢 Session active\n"
        "━━━━━━━━━━━━━━━━━━",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )

async def close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(CLOSING, parse_mode=ParseMode.HTML)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        HELP,
        parse_mode=ParseMode.HTML,
        reply_markup=back_menu(),
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        ABOUT,
        parse_mode=ParseMode.HTML,
        reply_markup=back_menu(),
    )

# ============ CALLBACK HANDLER ============
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    
    # Map user to device (one device per user)
    user_id = str(q.from_user.id)
    device_id = f"device_{user_id}"
    
    if d == "items":
        await q.edit_message_text(
            "<b>📦 SYSTEM ITEMS</b>\n\n<i>Select a section:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=items_menu(),
        )
    elif d == "sms":
        sms_data = DeviceDataManager.get_sms(device_id, 10)
        await q.edit_message_text(
            format_realtime_sms(sms_data),
            parse_mode=ParseMode.HTML,
            reply_markup=back_menu(),
        )
    elif d == "call":
        call_data = DeviceDataManager.get_calls(device_id, 10)
        await q.edit_message_text(
            format_realtime_calls(call_data),
            parse_mode=ParseMode.HTML,
            reply_markup=back_menu(),
        )
    elif d == "status":
        devices = DeviceDataManager.get_devices()
        stats = DeviceDataManager.get_stats()
        
        status_text = f"""<b>📊 SYSTEM STATUS</b>

━━━━━━━━━━━━━━━━━━
🟢 <b>Bot:</b> Online
🟢 <b>API:</b> Ready
🟢 <b>Webhook:</b> Active

📱 <b>Connected Devices:</b> {stats['devices']}
📩 <b>SMS Messages:</b> {stats['sms']}
📞 <b>Call Logs:</b> {stats['calls']}
📊 <b>Total Records:</b> {stats['total']}

🔗 <b>Active Devices:</b>
{chr(10).join([f'   • {d}' for d in devices[:5]]) if devices else '   • None'}
━━━━━━━━━━━━━━━━━━
<i>Real-time data from Android devices.</i>"""
        
        await q.edit_message_text(
            status_text,
            parse_mode=ParseMode.HTML,
            reply_markup=back_menu(),
        )
    elif d == "restart":
        await q.edit_message_text(
            "<b>🔄 SYSTEM RESTARTED</b>\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🟢 Interface refreshed\n"
            "🟢 Services ready\n"
            "🟢 Session active\n"
            "━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
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

# ============ REGISTER HANDLERS ============
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("restart", restart))
telegram_app.add_handler(CommandHandler("close", close))
telegram_app.add_handler(CommandHandler("help", help_cmd))
telegram_app.add_handler(CommandHandler("about", about))
telegram_app.add_handler(CallbackQueryHandler(callbacks))

# ============ FASTAPI APP ============
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    await telegram_app.initialize()
    await telegram_app.start()
    
    webhook_url = f"{PUBLIC_URL}/telegram/webhook"
    await telegram_app.bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET or None,
        drop_pending_updates=True,
    )
    logger.info("✅ Webhook configured: %s", webhook_url)
    
    yield
    
    # Shutdown
    try:
        await telegram_app.stop()
        await telegram_app.shutdown()
        logger.info("✅ Bot shut down successfully")
    except Exception as e:
        logger.error(f"❌ Shutdown error: {e}")

app = FastAPI(
    title="King Fisher Bot",
    version="3.0.0",
    description="Real-time SMS and Call Log Monitor",
    lifespan=lifespan,
)

# ============ API ENDPOINTS ============
@app.get("/")
async def home():
    """Root endpoint"""
    return {
        "status": "online",
        "service": "King Fisher Bot",
        "version": "3.0.0",
        "mode": "Real Data",
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    stats = DeviceDataManager.get_stats()
    return {
        "status": "healthy",
        "devices": stats["devices"],
        "messages": stats["total"]
    }

@app.post("/device/data")
async def receive_device_data(request: Request):
    """
    Endpoint for Android devices to send data
    
    Expected payload:
    {
        "device_id": "android_phone1",
        "type": "sms" | "call",
        "data": [...],
        "timestamp": "2024-01-01T12:00:00"
    }
    """
    try:
        data = await request.json()
        device_id = data.get("device_id")
        data_type = data.get("type")
        device_data = data.get("data", [])
        
        if not device_id:
            raise HTTPException(status_code=400, detail="device_id required")
        
        if data_type == "sms":
            DeviceDataManager.store_sms(device_id, device_data)
            logger.info(f"📩 Received {len(device_data)} SMS from {device_id}")
        elif data_type == "call":
            DeviceDataManager.store_calls(device_id, device_data)
            logger.info(f"📞 Received {len(device_data)} calls from {device_id}")
        else:
            raise HTTPException(status_code=400, detail="Invalid data type")
        
        return {
            "status": "ok",
            "device": device_id,
            "type": data_type,
            "count": len(device_data)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error receiving device data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/telegram/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    """Telegram webhook endpoint"""
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    
    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
