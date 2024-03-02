import logging
import sqlite3
import tempfile
import datetime

from aiogram import Bot, Dispatcher, types, executor
from moviepy.editor import VideoFileClip
from io import BytesIO, FileIO
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

import aiogram.utils.exceptions

class SendBroadcastState(StatesGroup):
    waiting_for_message = State()

API_TOKEN = ""  # @BotFather token bot
CHANNEL_ID = -1002120834518 # channel id
CHANNEL_LINK = "https://t.me/+_IQt3BVSW_o5Yjhk"  # линк на канал

# Ваш ID в переменной для проверки админских прав
ADMIN_USER_ID = 123456789  # Замените на ваш реальный ID

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
dp = Dispatcher(bot)


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


dp.register_message_handler(start, commands=["start"])
dp.register_message_handler(process_video, content_types=types.ContentType.VIDEO)

async def admin_command(message: types.Message):
    user = message.from_user

    if user.id == ADMIN_USER_ID:
        # Пользователь является администратором
        total_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        await message.answer(f"В базе данных всего юзеров: {total_users}")

        # Создаем инлайн-кнопку для рассылки
        keyboard = types.InlineKeyboardMarkup()
        send_broadcast_button = types.InlineKeyboardButton(text="Рассылка", callback_data="send_broadcast")
        keyboard.add(send_broadcast_button)

        await message.answer("Выберите действие:", reply_markup=keyboard)
    else:
        # Пользователь не имеет прав на выполнение команды
        await message.answer("У вас нет прав на выполнение этой команды.")

async def send_broadcast_request(callback_query: types.CallbackQuery):
    await callback_query.answer()

    # Запрос на ввод сообщения для рассылки
    await callback_query.message.answer("Пожалуйста, напишите сообщение для рассылки:")
    await SendBroadcastState.waiting_for_message.set()

@dp.message_handler(state=SendBroadcastState.waiting_for_message)
async def process_broadcast_message(message: types.Message, state: FSMContext):
    await state.finish()

    user = message.from_user

    # Ваш ID в переменной для проверки админских прав
    if user.id != ADMIN_USER_ID:
        await message.answer("У вас нет прав на выполнение этой команды.")
        return

    # Запрашиваем подтверждение перед рассылкой
    keyboard = types.InlineKeyboardMarkup()
    confirm_button = types.InlineKeyboardButton(text="Да", callback_data="confirm_broadcast")
    cancel_button = types.InlineKeyboardButton(text="Нет", callback_data="cancel_broadcast")
    keyboard.add(confirm_button, cancel_button)

    await message.answer("Вы уверены?", reply_markup=keyboard)
    await state.update_data(broadcast_message=message.text)

@dp.callback_query_handler(lambda callback_query: callback_query.data == "confirm_broadcast", state="*")
async def confirm_broadcast(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()

    # Получаем данные из состояния
    data = await state.get_data()
    broadcast_message = data.get("broadcast_message")

    # Рассылаем сообщение всем пользователям
    users = cursor.execute("SELECT user_id FROM users").fetchall()
    for user_id in users:
        try:
            await bot.send_message(user_id[0], broadcast_message)
        except aiogram.utils.exceptions.BotBlocked:
            pass  # Игнорируем заблокированных пользователей

    await callback_query.message.answer("Рассылка завершена.")
    await state.finish()

@dp.callback_query_handler(lambda callback_query: callback_query.data == "cancel_broadcast", state="*")
async def cancel_broadcast(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    await callback_query.message.answer("Рассылка отменена.")
    await state.finish()

# Регистрируем новую команду для админа
dp.register_message_handler(admin_command, commands=["admin"])

# Регистрируем обработчик для запроса рассылки
dp.callback_query_handler(lambda callback_query: callback_query.data == "send_broadcast", state="*")(send_broadcast_request)


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
