import os
import json
from aiogram import types, F, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

# Читаем ID риелтора (менеджера) из переменных окружения
REALTOR_ID_STR = os.getenv("REALTOR_ID") or os.getenv("ADMIN_ID")
if not REALTOR_ID_STR:
    raise ValueError("Не найден REALTOR_ID в переменных окружения!")
REALTOR_ID = int(REALTOR_ID_STR)

@router.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        if data.get("action") == "contact":
            ad_num = data.get("ad_num")
            
            # Данные о клиенте из Telegram
            client_name = message.from_user.full_name
            client_username = f"@{message.from_user.username}" if message.from_user.username else "скрыт"
            client_id = message.from_user.id
            
            # Формируем текст уведомления для риелтора
            realtor_text = (
                f"🚨 **Новая заявка из мини-приложения!**\n\n"
                f"🏠 Объект №: **{ad_num}**\n"
                f"👤 Клиент: {client_name} ({client_username})\n"
                f"🆔 Telegram ID: `{client_id}`"
            )

            # Инлайн-кнопка для прямой связи с клиентом
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💬 Написать клиенту", url=f"tg://user?id={client_id}")]
            ])

            # Отправка заявки риелтору
            await message.bot.send_message(
                chat_id=REALTOR_ID,
                text=realtor_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )

            # Подтверждение пользователю в чат с ботом
            await message.answer("✅ Ваша заявка успешно отправлена нашему риелтору! Скоро с вами свяжутся.")
            
    except Exception as e:
        print(f"Ошибка обработки Web App данных: {e}")
        await message.answer("❌ Произошла ошибка при отправке заявки. Попробуйте еще раз.")