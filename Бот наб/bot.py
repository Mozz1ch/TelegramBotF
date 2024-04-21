from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackContext, filters # Изменение
from queue import Queue
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine, Column, Integer, String
import logging
from logging.handlers import RotatingFileHandler

# Настройка базы данных
engine = create_engine('sqlite:///queue.db')
Base = declarative_base()

class QueueItem(Base):
    __tablename__ = 'queue'
    id = Column(Integer, primary_key=True)
    name = Column(String)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

#Логирование
logging.basicConfig(filename='bot.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('bot_logger')
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(
    filename='bot.log',
    maxBytes=1024 * 1024 * 5,  # 5 MB max file size
    backupCount=5  # Keep 5 old log files
)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Функции бота
async def start(update: Update, context: CallbackContext) -> None:
    logger.info(f"/start команда использована пользователем user_id: {update.effective_user.id}")
    await update.message.reply_text('Привет! Я бот для управления очередью. Используй /add [имя], чтобы добавить в очередь, /list чтобы посмотреть очередь, и /next чтобы перейти к следующему.')

async def add(update: Update, context: CallbackContext) -> None:
    name = ' '.join(context.args)
    if not name:
        await update.message.reply_text('❌ Ошибка: Укажите имя для добавления в очередь. Например: `/add Иван`')
        return
    session = Session()
    item = QueueItem(name=name)
    session.add(item)
    session.commit()
    logger.info(f"Пользователь {update.effective_user.id} добавил '{name}' в очередь")
    await update.message.reply_text(f'{name} добавлен в очередь.')

async def list_queue(update: Update, context: CallbackContext) -> None:
    logger.info(f"/list команда использована пользователем user_id: {update.effective_user.id}")
    session = Session()
    items = session.query(QueueItem).all()
    if not items:
        await update.message.reply_text('⚠️ Очередь пуста.')
        return
    message = 'Очередь:\n'
    for i, item in enumerate(items):
        message += f'{i+1}. {item.name}\n'
    await update.message.reply_text(message)

async def next_item(update: Update, context: CallbackContext) -> None:
    logger.info(f"/next команда использована пользователем user_id: {update.effective_user.id}")
    session = Session()
    item = session.query(QueueItem).first()
    if not item:
        await update.message.reply_text('⚠️ Очередь пуста.')  
        return
    session.delete(item)
    session.commit()
    await update.message.reply_text(f'Следующий: {item.name}')

# Запуск бота
update_queue = Queue()
if __name__ == '__main__':
    application = ApplicationBuilder().token("7140791741:AAFklhqVhhZVDxRSbOFoHH5B4-fE6eipQfg").build()

    # Определение обработчиков команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add))
    application.add_handler(CommandHandler("list", list_queue))
    application.add_handler(CommandHandler("next", next_item))

    # Запуск приложения
    application.run_polling()

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("add", add))
dispatcher.add_handler(CommandHandler("list", list_queue))
dispatcher.add_handler(CommandHandler("next", next_item))

updater.start_polling()
updater.idle()