import logging
import sqlite3
import tempfile
import datetime
import os

from aiogram import Bot, Dispatcher, types, executor
from moviepy.editor import VideoFileClip
from io import BytesIO, FileIO

import aiogram.utils.exceptions
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.contrib.fsm_storage.memory import MemoryStorage

class BroadcastState(StatesGroup):
    WaitingForAdminMessage = State()

API_TOKEN = ""  # @BotFather token bot
CHANNEL_ID = -1002120834518 # channel id
CHANNEL_LINK = "https://t.me/+_IQt3BVSW_o5Yjhk"  # линк на канал

# -------------------
ADMIN_ID = 1132917616  # Замените на реальный ID администратора
# -------------------

conn = sqlite3.connect('users.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        join_date TEXT,
        message_id INTEGER
    )
''')
conn.commit()

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
# Создаем объект MemoryStorage для хранения состояний
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

async def start(message: types.Message):
    user = message.from_user
    user_in_channel = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user.id)

    if user_in_channel.status == 'member' or user_in_channel.status == 'administrator':
        cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, join_date) VALUES (?, ?, ?, ?, ?)",
                       (user.id, user.username, user.first_name, user.last_name, datetime.datetime.now()))
        conn.commit()
        await message.answer("<b>Вы подписаны на наш канал. Теперь вы можете использовать бот</b>", parse_mode='HTML')
    else:
        keyboard = types.InlineKeyboardMarkup()
        channel_link_button = types.InlineKeyboardButton(text="Подписаться", url=CHANNEL_LINK)
        check_subscription_button = types.InlineKeyboardButton(text="✅ Проверить", callback_data="check_subscription")
        keyboard.add(channel_link_button)
        keyboard.add(check_subscription_button)

        await message.answer("Для использования бота, подпишитесь на наш канал https://t.me/+_IQt3BVSW_o5Yjhk, и нажмите кнопку 'Проверить подписку'.", reply_markup=keyboard, parse_mode='HTML')

# Функция для подсчета количества людей в базе данных
async def count_users():
    cursor.execute("SELECT COUNT(user_id) FROM users")
    result = cursor.fetchone()
    if result:
        return result[0]
    return 0

# Функция admin_command
async def admin_command(message: types.Message):
    user = message.from_user
    if user.id == ADMIN_ID:
        total_users = await count_users()

        keyboard = types.InlineKeyboardMarkup()
        broadcast_button = types.InlineKeyboardButton(text="Рассылка", callback_data="broadcast")
        export_button = types.InlineKeyboardButton(text="Выгрузить", callback_data="export_data")
        keyboard.add(broadcast_button, export_button)
        
        await message.answer(f"Всего людей в базе данных: {total_users}", reply_markup=keyboard)
    else:
        await message.answer("Вы не являетесь администратором и не имеете доступа к этой команде.")

async def process_video(message: types.Message):
    user = message.from_user
    user_in_channel = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user.id)

    if user_in_channel.status != 'member' and user_in_channel.status != 'administrator':
        await message.answer("‼️ Для использования бота, подпишитесь на наш канал https://t.me/+_IQt3BVSW_o5Yjhk, и нажмите кнопку 'Проверить подписку'.", parse_mode='HTML')
        return

    video_file_id = message.video.file_id
    wait_message = await message.answer("<b>Ожидайте генерации кружка ⏳</b>", parse_mode='HTML')

    video_data = BytesIO()
    await message.bot.download_file_by_id(video_file_id, video_data)
    video_data.seek(0)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video_file:
        temp_video_file.write(video_data.read())

    input_video = VideoFileClip(temp_video_file.name)
    w, h = input_video.size
    circle_size = 360
    aspect_ratio = float(w) / float(h)

    if w > h:
        new_w = int(circle_size * aspect_ratio)
        new_h = circle_size
    else:
        new_w = circle_size
        new_h = int(circle_size / aspect_ratio)

    resized_video = input_video.resize((new_w, new_h))
    output_video = resized_video.crop(x_center=resized_video.w / 2, y_center=resized_video.h / 2, width=circle_size,
                                       height=circle_size)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_output_file:
        output_video.write_videofile(temp_output_file.name, codec="libx264", audio_codec="aac")
        temp_output_file.seek(0)
        output_data = FileIO(temp_output_file.name)

    await message.bot.send_video_note(chat_id=message.chat.id, video_note=output_data, duration=int(output_video.duration),
                                      length=circle_size)

    await wait_message.delete()

    keyboard = types.InlineKeyboardMarkup()
    hide_message_button = types.InlineKeyboardButton(text="Скрыть сообщение", callback_data="hide_message")
    keyboard.add(hide_message_button)
    await message.answer("<b>Вот твой кружок ⤴️</b>", reply_markup=keyboard, parse_mode='HTML')


@dp.callback_query_handler(lambda callback_query: callback_query.data == "check_subscription")
async def check_subscription(callback_query: types.CallbackQuery):
    user = callback_query.from_user
    user_in_channel = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user.id)

    if user_in_channel.status == 'member' or user_in_channel.status == 'administrator':
        cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, join_date) VALUES (?, ?, ?, ?, ?)",
                       (user.id, user.username, user.first_name, user.last_name, datetime.datetime.now()))
        conn.commit()
        await callback_query.answer("✅")

        try:
            await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)
        except aiogram.utils.exceptions.MessageToDeleteNotFound:
            pass

        await bot.send_message(user.id,
                               "Отправьте мне видео, и я преобразую его в видеокружок.\n\n<b>Не забудьте разрешить доступ к ГС, если вы их ограничили</b>",
                               parse_mode='HTML')
    else:
        await callback_query.answer("‼️ Вы не подписаны на наш канал. Пожалуйста, подпишитесь на канал", show_alert=True)

@dp.callback_query_handler(lambda callback_query: callback_query.data == "hide_message")
async def hide_message(callback_query: types.CallbackQuery):
    await callback_query.answer("Сообщение скрыто")

    try:
        await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)
    except aiogram.utils.exceptions.MessageToDeleteNotFound:
        pass

@dp.callback_query_handler(lambda callback_query: callback_query.data == "export_data")
async def export_data(callback_query: types.CallbackQuery):
    # Получаем данные из базы данных
    cursor.execute("SELECT user_id, username, first_name, last_name, join_date FROM users")
    data = cursor.fetchall()

    # Создаем файл с данными
    with open("file.txt", "w", encoding="utf-8") as file:
        for row in data:
            file.write(" : ".join(map(str, row)) + "\n")

    # Отправляем файл пользователю
    with open("file.txt", "rb") as file:
        await bot.send_document(callback_query.from_user.id, file)

    # Удаляем временный файл
    os.remove("file.txt")

    await callback_query.answer("Данные успешно выгружены в файл.")

@dp.callback_query_handler(lambda callback_query: callback_query.data == "broadcast")
async def start_broadcast(callback_query: types.CallbackQuery, state: FSMContext):
    await BroadcastState.WaitingForAdminMessage.set()
    await bot.send_message(callback_query.from_user.id, "🫴Для рассылки, отправь любое сообщение (Видео, изображение, стикеры)")


@dp.message_handler(state=BroadcastState.WaitingForAdminMessage, content_types=types.ContentType.ANY)
async def process_admin_message(message: types.Message, state: FSMContext):
    await state.finish()  # Завершаем состояние

    # Проверяем, есть ли текст в сообщении
    admin_message_text = message.text or ''

    # Получаем список всех пользователей из базы данных
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()

    # Отправляем текстовое сообщение каждому пользователю
    for user_id in users:
        try:
            await bot.send_message(user_id[0], admin_message_text, parse_mode='HTML')
        except Exception as e:
            print(f"Ошибка при отправке текстового сообщения пользователю {user_id[0]}: {e}")

    # Отправляем фото каждому пользователю, если есть
    if message.photo:
        for user_id in users:
            try:
                # Отправляем фото с текстом в виде подписи
                await bot.send_photo(user_id[0], photo=message.photo[-1].file_id, caption=f"{admin_message_text}\n\n{message.caption}" if message.caption else None, parse_mode='HTML')
            except Exception as e:
                print(f"Ошибка при отправке фото пользователю {user_id[0]}: {e}")

    # Отправляем видео каждому пользователю, если есть
    if message.video:
        for user_id in users:
            try:
                # Отправляем видео с текстом в виде подписи
                await bot.send_video(user_id[0], video=message.video.file_id, caption=f"{admin_message_text}\n\n{message.caption}" if message.caption else None, parse_mode='HTML')
            except Exception as e:
                print(f"Ошибка при отправке видео пользователю {user_id[0]}: {e}")

    # Отправляем стикер каждому пользователю, если есть
    if message.sticker:
        for user_id in users:
            try:
                await bot.send_sticker(user_id[0], sticker=message.sticker.file_id)
            except Exception as e:
                print(f"Ошибка при отправке стикера пользователю {user_id[0]}: {e}")

    await bot.send_message(message.chat.id, "Рассылка успешно завершена!", parse_mode='HTML')

dp.register_message_handler(start, commands=["start"])
dp.register_message_handler(process_video, content_types=types.ContentType.VIDEO)
# Добавляем команду /admin
dp.register_message_handler(admin_command, commands=["admin"])

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
