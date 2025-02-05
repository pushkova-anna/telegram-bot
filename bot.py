import logging
from gspread import Worksheet
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import asyncio

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Авторизация с Google Sheets API
scope = ['https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive"]
creds_file: str = 'vacationtrackerbot-449910-7facd633d4c7.json'  # Путь к вашему JSON-файлу с ключами
creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)
client = gspread.authorize(creds)
sheet: Worksheet = client.open_by_key("1W2jYXR9Nexw26WuP0hH7HIdc0ryLr7P7uNb2S7UWj1I").sheet1  # Используйте ID таблицы

# Токен вашего Telegram-бота
TELEGRAM_TOKEN: str = '7448225374:AAH8r9K2oVBxkKwkgw8tfKPYzD97NqzU2UU'


# Функции для бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработка команды /start.
    """
    await update.message.reply_text('Привет! Я бот для отслеживания отпусков, больничных и выходных.')


async def request_leave(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработка команды /leave для отправки заявки на отпуск.
    """
    user_name = update.message.from_user.username
    leave_request = ' '.join(context.args)  # Переименовали переменную с 'request' на 'leave_request'

    if len(leave_request.split()) != 3:
        await update.message.reply_text(
            'Введите тип (отпуск, больничный или выходной) и даты в формате: "тип ДД.ММ.ГГГГ ДД.ММ.ГГГГ"')
        return

    try:
        leave_type, start_date_str, end_date_str = leave_request.split()  # Заменили 'request' на 'leave_request'
        start_date = datetime.strptime(start_date_str, "%d.%m.%Y")
        end_date = datetime.strptime(end_date_str, "%d.%m.%Y")
        delta = (end_date - start_date).days + 1  # Включаем день окончания

        # Формируем строку данных для добавления в таблицу
        row = [user_name, leave_type, start_date.strftime('%d.%m.%Y'), end_date.strftime('%d.%m.%Y'), delta,
               "ожидает подтверждения"]

        # Логируем данные перед добавлением в таблицу
        logger.info(
            f"Received leave request: {leave_request} from user: {user_name}")  # Заменили 'request' на 'leave_request'
        logger.info(f"Attempting to add row to sheet: {row}")

        # Асинхронный вызов для добавления строки в таблицу
        await asyncio.to_thread(sheet.append_row, row)

        await update.message.reply_text(
            f"Заявка на {leave_type} с {start_date.strftime('%d.%m.%Y')} по {end_date.strftime('%d.%m.%Y')} на {delta} дней отправлена на подтверждение.")
    except ValueError as e:
        logger.error(f"Error in date format: {e}")  # Логируем ошибку формата даты
        await update.message.reply_text(f"Ошибка в формате даты: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")  # Логируем непредвиденную ошибку
        await update.message.reply_text(f"Произошла ошибка при обработке заявки: {e}")


async def approve_leave(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработка команды /approve для утверждения заявки.
    """
    # Разрешаем подтверждать запросы пользователю annapushkov
    if update.message.from_user.username not in ['idealpromo', 'annapushkov']:  # Добавлен annapushkov
        await update.message.reply_text('Только CEO или annapushkov могут утверждать заявки!')
        return

    try:
        # Получаем все строки из таблицы
        all_rows = await asyncio.to_thread(sheet.get_all_values)

        # Проверяем, есть ли данные в таблице
        if len(all_rows) <= 1:  # Если только заголовки или пусто
            await update.message.reply_text("Нет заявок, ожидающих подтверждения.")
            return

        # Ищем заявки со статусом "ожидает подтверждения"
        for i, row in enumerate(all_rows[1:], start=2):  # Пропускаем заголовки
            if len(row) >= 6 and row[5] == "ожидает подтверждения":  # Проверяем статус
                # Обновляем статус на "подтверждено"
                await asyncio.to_thread(sheet.update_cell, i, 6, 'подтверждено')

                # Формируем сообщение для пользователя
                user_name = row[0]
                leave_type = row[1]
                start_date = row[2]
                end_date = row[3]
                days = row[4]

                await update.message.reply_text(
                    f"Заявка на {leave_type} от {user_name} с {start_date} по {end_date} на {days} дней подтверждена."
                )
                return

        # Если не найдено заявок со статусом "ожидает подтверждения"
        await update.message.reply_text("Нет заявок, ожидающих подтверждения.")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /approve: {e}")
        await update.message.reply_text(f"Произошла ошибка при обработке команды: {e}")


async def view_requests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработка команды /view для просмотра всех запросов.
    """
    try:
        # Получаем все строки из таблицы
        all_rows = await asyncio.to_thread(sheet.get_all_values)

        # Проверяем, есть ли данные в таблице
        if len(all_rows) <= 1:  # Если только заголовки или пусто
            await update.message.reply_text("Нет заявок.")
            return

        # Формируем сообщение со всеми заявками
        response = "Все заявки:\n"
        for row in all_rows[1:]:  # Пропускаем заголовки
            if len(row) >= 6:  # Проверяем, что строка содержит все данные
                user_name, leave_type, start_date, end_date, days, status = row
                response += (
                    f"👤 {user_name}\n"
                    f"📅 {start_date} - {end_date} ({days} дней)\n"
                    f"📝 Тип: {leave_type}\n"
                    f"🟢 Статус: {status}\n"
                    "————————————\n"
                )

        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /view: {e}")
        await update.message.reply_text(f"Произошла ошибка при обработке команды: {e}")


def main() -> None:
    """
    Основная функция, которая запускает бота.
    """
    # Указываем тип переменной application
    application: Application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("leave", request_leave))  # Команда для подачи заявки
    application.add_handler(CommandHandler("approve", approve_leave))  # Команда для утверждения заявки
    application.add_handler(CommandHandler("view", view_requests))  # Команда для просмотра всех запросов

    # Запуск бота
    application.run_polling()


if __name__ == '__main__':
    main()  # Запуск main() без asyncio.run()