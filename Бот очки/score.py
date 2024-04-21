from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext
# Счет игры
score = {"team1": 0, "team2": 0}

async def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [
            KeyboardButton("➕ Команда 1"),
            KeyboardButton("➕ Команда 2"),
        ],
        [KeyboardButton("🏆 Счет")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("👋 Привет! Я бот для подсчета очков в волейболе.", reply_markup=reply_markup)

async def handle_button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == 'team1':
        await team1_point(update, context)
    elif data == 'team2':
        await team2_point(update, context)
    elif data == 'score':
        await get_score(update, context)

async def team1_point(update: Update, context: CallbackContext) -> None:
    score["team1"] += 1
    await update.callback_query.edit_message_text(f"🏐 Очко команде 1! Текущий счет: {score['team1']}:{score['team2']}")

async def team2_point(update: Update, context: CallbackContext) -> None:
    score["team2"] += 1
    await update.callback_query.edit_message_text(f"🏐 Очко команде 2! Текущий счет: {score['team1']}:{score['team2']}")

async def get_score(update: Update, context: CallbackContext) -> None:
    await update.callback_query.edit_message_text(f"🏆 Текущий счет: {score['team1']}:{score['team2']}")

if __name__ == '__main__':
    application = ApplicationBuilder().token("6990209707:AAGOaqjJNQ52a-D1nn5pwIl-j-4bzrRGxKI").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("team1", team1_point))
    application.add_handler(CommandHandler("team2", team2_point))
    application.add_handler(CommandHandler("score", get_score))
    application.add_handler(CallbackQueryHandler(handle_button))

    application.run_polling()