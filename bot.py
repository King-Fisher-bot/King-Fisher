import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

# ============================================================
# 1) এখানে আপনার BotFather API Token বসাবেন
#    উদাহরণ:
#    BOT_TOKEN = "8756561564:AAGEmLDO3lT3y41cRJPzlUNinSWq6w5MgaY"
# ============================================================
BOT_TOKEN = "8756561564:AAGEmLDO3lT3y41cRJPzlUNinSWq6w5MgaY"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

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
    text = (
        "🚀 *KING FISHER BOT*\n\n"
        "স্বাগতম! নিচের Menu থেকে একটি অপশন নির্বাচন করুন।"
    )
    await update.message.reply_text(
        text, parse_mode="Markdown", reply_markup=MAIN_MENU
    )


async def items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📦 *SYSTEM ITEMS*\n\nএকটি অপশন নির্বাচন করুন:",
        parse_mode="Markdown",
        reply_markup=ITEMS_MENU
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ *HELP*\n\n"
        "/start — Main Menu\n"
        "/items — System Items\n"
        "/restart — Reload menu\n"
        "/close — Close current menu\n"
        "/help — Help\n"
        "/about — About",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU
    )


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *ABOUT*\n\n"
        "King Fisher Bot\n"
        "Version 1.0",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU
    )


async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔄 System reloaded successfully.\n\n"
        "Main Menu:",
        reply_markup=MAIN_MENU
    )


async def close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔒 Menu closed.\n\n"
        "আবার চালু করতে /start লিখুন।"
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "items":
        await query.edit_message_text(
            "📦 *SYSTEM ITEMS*\n\nএকটি অপশন নির্বাচন করুন:",
            parse_mode="Markdown",
            reply_markup=ITEMS_MENU
        )

    elif data == "sms":
        await query.edit_message_text(
            "📩 *SMS*\n\n"
            "এখানে শুধুমাত্র আপনার অনুমোদিত/নিজস্ব SMS data integration "
            "যোগ করা যাবে।\n\n"
            "বর্তমানে কোনো SMS source connected নেই।",
            parse_mode="Markdown",
            reply_markup=ITEMS_MENU
        )

    elif data == "call":
        await query.edit_message_text(
            "📞 *CALL*\n\n"
            "এখানে শুধুমাত্র আপনার অনুমোদিত/নিজস্ব call data integration "
            "যোগ করা যাবে।\n\n"
            "বর্তমানে কোনো Call source connected নেই।",
            parse_mode="Markdown",
            reply_markup=ITEMS_MENU
        )

    elif data == "back":
        await query.edit_message_text(
            "🚀 *KING FISHER BOT*\n\nMain Menu:",
            parse_mode="Markdown",
            reply_markup=MAIN_MENU
        )

    elif data == "restart":
        await query.edit_message_text(
            "🔄 System reloaded successfully.\n\nMain Menu:",
            reply_markup=MAIN_MENU
        )

    elif data == "close":
        await query.edit_message_text(
            "🔒 Menu closed.\n\nআবার চালু করতে /start লিখুন।"
        )

    elif data == "help":
        await query.edit_message_text(
            "❓ *HELP*\n\n"
            "/start — Main Menu\n"
            "/items — System Items\n"
            "/restart — Reload menu\n"
            "/close — Close menu\n"
            "/help — Help\n"
            "/about — About",
            parse_mode="Markdown",
            reply_markup=MAIN_MENU
        )

    elif data == "about":
        await query.edit_message_text(
            "ℹ️ *ABOUT*\n\nKing Fisher Bot\nVersion 1.0",
            parse_mode="Markdown",
            reply_markup=MAIN_MENU
        )


def main():
    if not BOT_TOKEN or BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise RuntimeError(
            "BOT_TOKEN সেট করা হয়নি। bot.py ফাইলে BotFather Token বসান।"
        )

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("items", items))
    app.add_handler(CommandHandler("restart", restart))
    app.add_handler(CommandHandler("close", close))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("King Fisher Bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
