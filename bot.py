import os
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

BOT_TOKEN = os.getenv("8756561564:AAGEmLDO3lT3y41cRJPzlUNinSWq6w5MgaY")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
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
    await update.message.reply_text(
        "🚀 *KING FISHER BOT*\n\nস্বাগতম! নিচের Menu থেকে একটি অপশন নির্বাচন করুন।",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU,
    )


async def items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📦 *SYSTEM ITEMS*\n\nএকটি অপশন নির্বাচন করুন:",
        parse_mode="Markdown",
        reply_markup=ITEMS_MENU,
    )


async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔄 System reloaded successfully.\n\nMain Menu:",
        reply_markup=MAIN_MENU,
    )


async def close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔒 Menu closed.\n\nআবার চালু করতে /start লিখুন."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ *HELP*\n\n"
        "/start — Main Menu\n"
        "/items — System Items\n"
        "/restart — Reload menu\n"
        "/close — Close menu\n"
        "/help — Help\n"
        "/about — About",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU,
    )


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *ABOUT*\n\nKing Fisher Bot\nVersion 1.0",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU,
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "items":
        await query.edit_message_text(
            "📦 *SYSTEM ITEMS*\n\nএকটি অপশন নির্বাচন করুন:",
            parse_mode="Markdown",
            reply_markup=ITEMS_MENU,
        )

    elif query.data == "sms":
        await query.edit_message_text(
            "📩 *SMS*\n\nবর্তমানে কোনো SMS source connected নেই.",
            reply_markup=ITEMS_MENU,
        )

    elif query.data == "call":
        await query.edit_message_text(
            "📞 *CALL*\n\nবর্তমানে কোনো Call source connected নেই.",
            reply_markup=ITEMS_MENU,
        )

    elif query.data == "back":
        await query.edit_message_text(
            "🚀 *KING FISHER BOT*\n\nMain Menu:",
            parse_mode="Markdown",
            reply_markup=MAIN_MENU,
        )

    elif query.data == "restart":
        await query.edit_message_text(
            "🔄 System reloaded successfully.\n\nMain Menu:",
            reply_markup=MAIN_MENU,
        )

    elif query.data == "close":
        await query.edit_message_text(
            "🔒 Menu closed.\n\nআবার চালু করতে /start লিখুন."
        )

    elif query.data == "help":
        await query.edit_message_text(
            "❓ *HELP*\n\n"
            "/start — Main Menu\n"
            "/items — System Items\n"
            "/restart — Reload menu\n"
            "/close — Close menu\n"
            "/help — Help\n"
            "/about — About",
            parse_mode="Markdown",
            reply_markup=MAIN_MENU,
        )

    elif query.data == "about":
        await query.edit_message_text(
            "ℹ️ *ABOUT*\n\nKing Fisher Bot\nVersion 1.0",
            parse_mode="Markdown",
            reply_markup=MAIN_MENU,
        )


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is not set.")

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
