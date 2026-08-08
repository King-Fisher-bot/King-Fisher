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
from fastapi.responses import HTMLResponse
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
🟢 Platform: Android + IFTTT
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

# ============ IFTTT SETUP PAGE HTML ============
IFTTT_SETUP_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>King Fisher - IFTTT Setup</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            color: #ffffff;
        }
        .container {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(20px);
            border-radius: 24px;
            padding: 30px;
            max-width: 500px;
            width: 100%;
            border: 1px solid rgba(0, 255, 136, 0.2);
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 32px;
            background: linear-gradient(135deg, #00ff88, #00ccff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 5px;
        }
        .header p {
            color: #888;
            font-size: 14px;
        }
        .step {
            background: rgba(0, 255, 136, 0.05);
            border: 1px solid rgba(0, 255, 136, 0.1);
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 15px;
            transition: all 0.3s ease;
        }
        .step:hover {
            border-color: rgba(0, 255, 136, 0.3);
            transform: translateY(-2px);
        }
        .step h3 {
            color: #00ff88;
            font-size: 16px;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .step h3 .number {
            background: #00ff88;
            color: #000;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: bold;
        }
        .btn {
            display: block;
            width: 100%;
            padding: 14px;
            margin: 8px 0;
            border: none;
            border-radius: 12px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-align: center;
            text-decoration: none;
            background: #00ff88;
            color: #000;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0, 255, 136, 0.3);
        }
        .btn-secondary {
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.2);
            box-shadow: 0 8px 25px rgba(255, 255, 255, 0.1);
        }
        .btn-small {
            padding: 10px 20px;
            font-size: 13px;
            display: inline-block;
            width: auto;
        }
        .code {
            background: #000;
            padding: 15px;
            border-radius: 10px;
            font-family: 'Courier New', monospace;
            font-size: 11px;
            overflow-x: auto;
            color: #00ff88;
            line-height: 1.6;
            margin: 10px 0;
            border: 1px solid rgba(0, 255, 136, 0.1);
        }
        .status {
            padding: 12px;
            border-radius: 10px;
            background: rgba(0, 0, 0, 0.3);
            font-size: 13px;
            color: #aaa;
            margin-top: 10px;
        }
        .status.success { color: #00ff88; border-left: 3px solid #00ff88; }
        .status.error { color: #ff4444; border-left: 3px solid #ff4444; }
        .row { display: flex; gap: 10px; }
        .row .btn { flex: 1; }
        .footer {
            text-align: center;
            margin-top: 20px;
            font-size: 12px;
            color: #555;
        }
        .badge {
            display: inline-block;
            background: rgba(0, 255, 136, 0.2);
            color: #00ff88;
            padding: 2px 10px;
            border-radius: 20px;
            font-size: 11px;
            margin-top: 5px;
        }
        @media (max-width: 480px) {
            .container { padding: 20px; }
            .row { flex-direction: column; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>👑 KING FISHER</h1>
            <p>IFTTT Auto Setup System</p>
            <span class="badge">v3.0 • No Termux Required</span>
        </div>

        <!-- Step 1: Install IFTTT -->
        <div class="step">
            <h3><span class="number">1</span> Install IFTTT App</h3>
            <p style="color:#888;font-size:13px;margin-bottom:12px;">
                Download the IFTTT app from Play Store. This is required for SMS forwarding.
            </p>
            <button class="btn" onclick="downloadIFTTT()">
                📥 Download from Play Store
            </button>
        </div>

        <!-- Step 2: Create Applet -->
        <div class="step">
            <h3><span class="number">2</span> Create Applet</h3>
            <p style="color:#888;font-size:13px;margin-bottom:12px;">
                Automatically create the applet with pre-filled settings. Just click "Connect".
            </p>
            <button class="btn" onclick="createApplet()">
                ⚡ Auto Create Applet
            </button>
            <div style="margin-top:10px;">
                <button class="btn btn-secondary btn-small" onclick="manualSetup()">
                    📝 Manual Setup
                </button>
            </div>
        </div>

        <!-- Step 3: Test -->
        <div class="step">
            <h3><span class="number">3</span> Test Connection</h3>
            <p style="color:#888;font-size:13px;margin-bottom:12px;">
                Verify that your bot is online and ready to receive data.
            </p>
            <button class="btn btn-secondary" onclick="testBot()">
                🏥 Test Bot Connection
            </button>
            <div id="testResult" class="status">
                Status: Not tested
            </div>
        </div>

        <!-- Manual Code -->
        <div class="step" style="border-color: rgba(255,255,255,0.05);">
            <h3 style="color:#fff;">📝 Manual Setup Code</h3>
            <div class="code" id="manualCode">
URL: https://king-fisher-0g8k.onrender.com/device/data
Method: POST
Content-Type: application/json

Body:
{
  "device_id": "my_android_phone",
  "type": "sms",
  "data": [{
    "id": "{{OccurredAt}}",
    "sender": "{{FromNumber}}",
    "body": "{{Text}}",
    "timestamp": "{{OccurredAt}}"
  }]
}
            </div>
            <button class="btn btn-secondary" onclick="copyCode()">
                📋 Copy Code
            </button>
        </div>

        <!-- Share -->
        <div class="step" style="border-color: rgba(255,255,255,0.05);">
            <h3 style="color:#fff;">📤 Share Setup</h3>
            <div class="row">
                <button class="btn btn-secondary" onclick="shareLink()">
                    📤 Share Link
                </button>
                <button class="btn btn-secondary" onclick="showQR()">
                    📱 QR Code
                </button>
            </div>
            <div id="qrContainer" style="text-align:center;margin-top:10px;"></div>
        </div>

        <div class="footer">
            <p>🔒 All data is encrypted and transmitted securely via HTTPS</p>
            <p style="margin-top:5px;">Made with ❤️ by King Fisher Team</p>
        </div>
    </div>

    <script>
        const BOT_URL = "https://king-fisher-0g8k.onrender.com";
        const DEVICE_ID = "android_" + Date.now().toString(36);

        function downloadIFTTT() {
            window.open("https://play.google.com/store/apps/details?id=com.ifttt.ifttt", "_blank");
            document.getElementById('testResult').innerHTML = "📥 Opening Play Store for IFTTT...";
            document.getElementById('testResult').className = "status success";
        }

        function createApplet() {
            const appletData = {
                name: "King Fisher - SMS to Bot",
                triggers: [{
                    service: "android_sms",
                    id: "any_new_sms_received"
                }],
                actions: [{
                    service: "webhooks",
                    id: "make_a_web_request",
                    fields: {
                        url: BOT_URL + "/device/data",
                        method: "POST",
                        content_type: "application/json",
                        body: JSON.stringify({
                            device_id: DEVICE_ID,
                            type: "sms",
                            data: [{
                                id: "{{OccurredAt}}",
                                sender: "{{FromNumber}}",
                                body: "{{Text}}",
                                timestamp: "{{OccurredAt}}"
                            }]
                        })
                    }
                }]
            };
            
            const url = "https://ifttt.com/create?applet=" + encodeURIComponent(JSON.stringify(appletData));
            window.open(url, "_blank");
            document.getElementById('testResult').innerHTML = "✅ Opening IFTTT with pre-filled settings...";
            document.getElementById('testResult').className = "status success";
        }

        function manualSetup() {
            document.getElementById('testResult').innerHTML = 
                "📝 Manual Setup Instructions:<br><br>" +
                "1. Open IFTTT → Create<br>" +
                "2. If This → Android SMS → Any new SMS received<br>" +
                "3. Then That → Webhooks → Make a web request<br>" +
                "4. Copy the code from the box above<br>" +
                "5. Click Finish → Connect";
            document.getElementById('testResult').className = "status";
        }

        async function testBot() {
            try {
                const response = await fetch(BOT_URL + "/health");
                const data = await response.json();
                document.getElementById('testResult').innerHTML = 
                    `✅ Bot Online<br>` +
                    `📱 Devices: ${data.devices || 0}<br>` +
                    `📩 Messages: ${data.messages || 0}`;
                document.getElementById('testResult').className = "status success";
            } catch (error) {
                document.getElementById('testResult').innerHTML = 
                    `❌ Cannot connect to bot<br>` +
                    `Error: ${error.message}`;
                document.getElementById('testResult').className = "status error";
            }
        }

        function copyCode() {
            const code = document.getElementById('manualCode').textContent;
            if (navigator.clipboard) {
                navigator.clipboard.writeText(code).then(() => {
                    document.getElementById('testResult').innerHTML = "✅ Copied to clipboard!";
                    document.getElementById('testResult').className = "status success";
                });
            } else {
                const textarea = document.createElement('textarea');
                textarea.value = code;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                document.getElementById('testResult').innerHTML = "✅ Copied to clipboard!";
                document.getElementById('testResult').className = "status success";
            }
        }

        function shareLink() {
            const shareText = `👑 KING FISHER SETUP\n\n` +
                `1. Install IFTTT: https://play.google.com/store/apps/details?id=com.ifttt.ifttt\n` +
                `2. Open setup: ${window.location.href}\n` +
                `3. Or use manual code:\n` +
                `URL: ${BOT_URL}/device/data\n` +
                `Body: {"device_id":"${DEVICE_ID}","type":"sms","data":[{"id":"{{OccurredAt}}","sender":"{{FromNumber}}","body":"{{Text}}","timestamp":"{{OccurredAt}}"}]}`;
            
            if (navigator.share) {
                navigator.share({
                    title: 'King Fisher Setup',
                    text: shareText
                });
            } else {
                copyToClipboard(shareText);
                document.getElementById('testResult').innerHTML = "✅ Link copied! Share it with your other phone.";
                document.getElementById('testResult').className = "status success";
            }
        }

        function showQR() {
            const text = `${BOT_URL}/ifttt-setup`;
            const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(text)}`;
            document.getElementById('qrContainer').innerHTML = `
                <img src="${qrUrl}" style="border-radius:12px;border:2px solid #00ff88;" />
                <p style="color:#888;font-size:12px;margin-top:5px;">Scan to open setup page</p>
            `;
        }

        function copyToClipboard(text) {
            if (navigator.clipboard) {
                navigator.clipboard.writeText(text);
            } else {
                const textarea = document.createElement('textarea');
                textarea.value = text;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
            }
        }

        // Auto-check on load
        document.addEventListener('DOMContentLoaded', () => {
            testBot();
        });
    </script>
</body>
</html>
"""

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
        "docs": "/docs",
        "setup": "/ifttt-setup"
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

@app.get("/ifttt-setup")
async def ifttt_setup():
    """IFTTT setup page"""
    return HTMLResponse(content=IFTTT_SETUP_PAGE)

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
