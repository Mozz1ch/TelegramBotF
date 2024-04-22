from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackContext, filters,CallbackQueryHandler
from queue import Queue
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine, Column, Integer, String, Boolean, func
from telegram.constants import ParseMode
import logging
from logging.handlers import RotatingFileHandler

# Логирование
logging.basicConfig(filename='bot.log', level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('bot_logger')
telegram_logger = logging.getLogger('telegram')
telegram_logger.setLevel(logging.WARNING)
logger.setLevel(logging.WARNING)
handler = RotatingFileHandler(
    filename='bot.log',
    maxBytes=1024 * 1024 * 5,  # 5 MB max file size
    backupCount=5  # Keep 5 old log files
)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Настройка базы данных
engine = create_engine('sqlite:///queue.db')
Base = declarative_base()

class QueueItem(Base):
    __tablename__ = 'queue'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    position = Column(Integer, default=0)
    is_playing = Column(Boolean, default=False)  # <-- Добавляем is_playing

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

class CurrentPlayer(Base):
    __tablename__ = 'current_player'
    id = Column(Integer, primary_key=True)
    name = Column(String)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

class WhitelistItem(Base):
    __tablename__ = 'whitelist'
    username = Column(String, primary_key=True)  # <-- Username как первичный ключ
    access_level = Column(String)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# Уровни доступа
master_password = "12345"
second_master_password = "1359725"
access_levels = {
    "full": "Полный доступ",
    "limited": "Ограниченный доступ",
    "basic": "Базовый доступ"
}
whitelist = {}

def is_master_password(password):
    return password == master_password

def is_second_master_password(password):
    return password == second_master_password

def has_full_access(update):
    username = update.effective_user.username
    session = Session()
    user = session.get(WhitelistItem, username)
    session.close()
    return user is not None and user.access_level == "full"

def full_access_only(func):
    async def wrapper(update: Update, context: CallbackContext):
        if not has_full_access(update):
            await update.message.reply_text("❌ У вас нет прав для этой команды.")
            return
        return await func(update, context)
    return wrapper

def limited_access_only(func):
    async def wrapper(update: Update, context: CallbackContext):
        username = update.effective_user.username
        session = Session()
        user = session.query(WhitelistItem).get(username)
        session.close()
        if user is None or user.access_level == "basic":
            await update.message.reply_text("❌ У вас нет прав для этой команды.")
            return
        return await func(update, context)
    return wrapper

def basic_access_only(func):
    # Базовый доступ не требует проверки, так как он доступен всем
    return func

# Функции бота
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Привет! Я бот для управления очередью.")
    logging.warning(f'Пользователь {update.effective_user.username} запустил бота.')
    message = """
    🏐бот предназначен для управления очередью🏐

1️⃣Если вы хотите добавить себя в конец очереди, используйте команду- /add 

2️⃣Чтобы посмотреть текущий список очереди, воспользуйтесь командой- /list. 

Если у вас есть ограниченный доступ, вы можете использовать команды

3️⃣ /next- для перехода к следующему человеку в очереди

4️⃣/remove- для удаления из очереди по номеру

5️⃣/insert- для добавления в очередь. 

❗️❗️❗️Если у вас есть какие-либо вопросы или проблемы-обращаться к администратору бота. (@Mozzich)
    """
    await update.message.reply_text(message)

@basic_access_only
async def add(update: Update, context: CallbackContext) -> None:
    name = ' '.join(context.args)
    if not name:
       await update.message.reply_text('❌ Ошибка: Укажите имя капитана команды для добавления в очередь. Например: `/add Иван`')
       return
    session = Session()
    item = QueueItem(name=name)
    session.add(item)
    session.commit()
    await update.message.reply_text(f'Команда {name} добавлена в очередь.')
    logging.warning(f'Команда {name} добавлена в очередь пользователем {update.effective_user.username}')

@basic_access_only
async def list_queue(update: Update, context: CallbackContext) -> None:
    session = Session()
    items = session.query(QueueItem).order_by(QueueItem.position).all()
    current_player = session.query(CurrentPlayer).first()
    
    message = 'Очередь:\n'
    if current_player:
        message += f'Сейчас играет команда: {current_player.name}\n'

        # Получаем следующего игрока (если он есть)
        next_in_line = session.query(QueueItem).first()
        if next_in_line:
            message += f'Следующая команда: {next_in_line.name}\n\n'
        else:
            message += '\n'

    if not items:
        message += '⚠️ Очередь пуста.'
    else:
        for i, item in enumerate(items):
            message += f'{i+1}. Команда {item.name}\n'
    
    await update.message.reply_text(message)
    logging.warning(f'Пользователь {update.effective_user.username} запросил список очереди.')

@limited_access_only
async def insert_into_queue(update: Update, context: CallbackContext):
    try:
        position_str, name = context.args[0], " ".join(context.args[1:])
        position = int(position_str) - 1
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Неверный формат. Используйте: /insert [позиция] [имя]")
        return

    session = Session()
    items = session.query(QueueItem).all()
    if position < 0 or position > len(items):
        await update.message.reply_text("❌ Неверная позиция.")
    else:
        # Создаем новый элемент с правильной позицией
        new_item = QueueItem(name=name, position=position)

        # Сдвигаем позиции элементов после вставки
        for item in items[position:]:
            item.position += 1

        # Добавляем новый элемент и сохраняем изменения
        session.add(new_item)
        session.commit()
        await update.message.reply_text(f"✅ Команда {name} добавлена в очередь на позицию {position + 1}.")
        logging.warning(f'Пользователь {update.effective_user.username} вставил команду {name} в очередь на позицию {position + 1}')
    session.close()

@limited_access_only
async def next_item(update: Update, context: CallbackContext) -> None:
    session = Session()

    # Удаляем предыдущего игрока
    session.query(CurrentPlayer).delete()

    # Получаем следующего игрока из очереди
    next_player_queue = session.query(QueueItem).first()
    if not next_player_queue:
        await update.message.reply_text('⚠️ Очередь пуста.')  
        return

    remaining_items = session.query(QueueItem).filter(QueueItem.position > next_player_queue.position).all()
    for item in remaining_items:
        item.position -= 1

    # Создаем запись о текущем игроке
    next_player = CurrentPlayer(name=next_player_queue.name)
    session.add(next_player)
    session.delete(next_player_queue)  # Удаляем из очереди
    session.commit()

    # Получаем следующего игрока (если он есть)
    next_in_line = session.query(QueueItem).first()
    next_player_info = f"\nСледующая команда идет на счёт: {next_in_line.name}" if next_in_line else ""

    await update.message.reply_text(f'Сейчас играет команда: {next_player.name}{next_player_info}')
    logging.warning(f'Пользователь {update.effective_user.username} перешел к следующей команде: {next_player.name}')

@limited_access_only
async def remove_from_queue(update: Update, context: CallbackContext):
    try:
        item_number = int(context.args[0]) - 1
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Неверный формат. Используйте: /remove [номер]")
        return

    session = Session()
    items = session.query(QueueItem).all()
    if item_number < 0 or item_number >= len(items):
        await update.message.reply_text("❌ Неверный номер элемента.")
    else:
        item_to_remove = items[item_number]
        session.delete(item_to_remove)
        session.commit()
        await update.message.reply_text(f"✅ Команда {item_to_remove.name} удалена из очереди.")
        logging.warning(f'Пользователь {update.effective_user.username} удалил команду {item_to_remove.name} из очереди.')
    session.close()

async def adduser(update: Update, context: CallbackContext):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Недостаточно аргументов. Используйте: /adduser [мастер-пароль] [имя_пользователя]")
        return

    if is_master_password(context.args[0]):
        access_level = "limited"
    elif is_second_master_password(context.args[0]):
        session = Session()
        existing_full_access_user = session.query(WhitelistItem).filter_by(access_level="full").first()
        access_level = "full"   
    else:
        await update.message.reply_text("❌ Неверный пароль.")
        logging.warning(f'Пользователь {update.effective_user.username} пытался добавить пользователя {username_with_at} с уровнем доступа {access_level}')
        return

    username_with_at = context.args[1]  # Получаем username с "@"
    username = username_with_at[1:]  # Удаляем "@"
    session = Session()
    existing_user = session.query(WhitelistItem).filter_by(username=username).first()
    if existing_user:
        await update.message.reply_text(f"❌ Пользователь {username} уже находится в белом списке.")
        session.close()
        return
    new_user = WhitelistItem(username=username, access_level=access_level)
    session.add(new_user)
    session.commit()
    session.close()
    await update.message.reply_text(f"✅ Пользователь {username} добавлен с {access_levels[access_level]}.")
    logging.warning(f'Пользователь {username} добавлен с уровнем доступа {access_levels[access_level]} пользователем {update.effective_user.username}')

@full_access_only
async def clear_queue(update: Update, context: CallbackContext):
    session=Session()
    session.query(QueueItem).delete()
    session.query(CurrentPlayer).delete()
    session.commit()
    session.close()
    await update.message.reply_text("✅ Очередь полностью очищена.")
    logger.warning("Очередь очищена пользователем", extra={"user": update.effective_user.username})

@full_access_only
async def removeuser(update: Update, context: CallbackContext):
    if not is_second_master_password(context.args[0]):
        await update.message.reply_text("❌ Неверный мастер-пароль.")
        return
    username_with_at = context.args[1]  # Получаем username с "@"
    username = username_with_at[1:]  # Удаляем "@"
    session = Session()
    user_to_remove = session.query(WhitelistItem).filter_by(username=username).first()
    if not user_to_remove:
        await update.message.reply_text("❌ Пользователь не найден в белом списке.")
    elif user_to_remove.access_level == "full":
        await update.message.reply_text("❌ Невозможно удалить пользователя с полным доступом.")
        logging.warning(f'Пользователь {update.effective_user.username} пытался удалить пользователя {username_with_at}') 
    else:
        session.delete(user_to_remove)
        session.commit()
        await update.message.reply_text(f"✅ Пользователь {username} удален из белого списка.")
        logging.warning(f'Пользователь {username} удален из белого списка пользователем {update.effective_user.username}')
    session.close()

async def list_whitelist(update: Update, context: CallbackContext) -> None:
    session = Session()
    whitelist_items = session.query(WhitelistItem).all()
    
    if not whitelist_items:
        await update.message.reply_text("⚠️ Белый список пуст.")
        return

    message = "**Белый список:**\n"
    for item in whitelist_items:
        message += f" {item.username} \-\  {access_levels[item.access_level]}\n"

    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN_V2)
    logging.warning(f'Пользователь {update.effective_user.username} запросил список белого списка.')

# Запуск бота
update_queue = Queue()
if __name__ == '__main__':
    application = ApplicationBuilder().token("7140791741:AAFklhqVhhZVDxRSbOFoHH5B4-fE6eipQfg").build()
    # Определение обработчиков команд
    # Для базовых пользователей
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add))
    application.add_handler(CommandHandler("list", list_queue))
    # Для ограниченных пользователей 
    application.add_handler(CommandHandler("remove", remove_from_queue))
    application.add_handler(CommandHandler("next", next_item))
    application.add_handler(CommandHandler("insert", insert_into_queue))
    # Для пользователя с полным уровнем доступа
    application.add_handler(CommandHandler("whitelist", list_whitelist))
    application.add_handler(CommandHandler("adduser", adduser))
    application.add_handler(CommandHandler("removeuser", removeuser))
    application.add_handler(CommandHandler("clearqueue", clear_queue))

    # Запуск приложения
    application.run_polling()