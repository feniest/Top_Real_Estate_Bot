from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import CommandStart
from database import search_ads, get_ad_media_files

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 Добро пожаловать в бот **Поиска недвижимости**!\n\n"
        "Отправьте мне название района или ориентир (например, *Чиланзар* или *Центр*), "
        "чтобы найти доступные объекты."
    )

@router.message(F.text)
async def handle_search(message: Message):
    query = message.text.strip()
    ads = search_ads(query)
    
    if not ads:
        await message.answer("😔 По вашему запросу ничего не найдено. Попробуйте другой район.")
        return
        
    await message.answer(f"🔍 Найдено объектов: {len(ads)}. Загружаю информацию...")
    
    for ad in ads:
        ad_num, category, prop_type, rooms, district, landmark, price, floor, floors_total = ad
        
        text = (
            f"🏠 **Объявление № {ad_num}**\n"
            f"📌 Категория: {category} ({prop_type})\n"
            f"🚪 Комнат: {rooms} | Этаж: {floor}/{floors_total}\n"
            f"📍 Район: {district}\n"
            f"🎯 Ориентир: {landmark}\n"
            f"💰 Цена: {price:,.0f} у.е."
        )
        
        # Получаем прикрепленные медиафайлы из базы данных
        media_files = get_ad_media_files(ad_num)
        
        if media_files:
            # Отправляем первый файл с текстом описания
            file_name, file_data = media_files[0]
            input_file = BufferedInputFile(bytes(file_data), filename=file_name)
            
            if file_name.lower().endswith(('png', 'jpg', 'jpeg', 'webp')):
                await message.answer_photo(photo=input_file, caption=text, parse_mode="Markdown")
            else:
                await message.answer_video(video=input_file, caption=text, parse_mode="Markdown")
        else:
            await message.answer(text, parse_mode="Markdown")