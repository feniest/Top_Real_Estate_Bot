from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile, InputMediaPhoto, InputMediaVideo
from aiogram.fsm.context import FSMContext
import database as db

router = Router()

# --- НИЖНЯЯ КЛАВИАТУРА В СИСТИЛЕ ДЕСКТОПНОГО ПРИЛОЖЕНИЯ ---

def get_main_menu_keyboard(category: str = "Rent") -> ReplyKeyboardMarkup:
    """Главное меню внизу экрана, адаптированное под логику main.py"""
    cat_label = "💰 Переключить на Продажу" if category == "Rent" else "🔑 Переключить на Аренду"
    
    keyboard = [
        [KeyboardButton(text="🏢 Квартиры (Аренда / Продажа)"), KeyboardButton(text="🏠 Дома (Аренда / Продажа)")],
        [KeyboardButton(text=cat_label)],
        [KeyboardButton(text="📍 Выбрать район"), KeyboardButton(text="🚪 Выбрать комнатность")],
        [KeyboardButton(text="📋 Показать объекты"), KeyboardButton(text="🔄 Сбросить фильтры")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def render_main_panel(count: int, category: str = "Rent", prop_type: str = "all", district: str = "all", rooms: str = "all") -> str:
    cat_name = "🔑 Аренда (Rent)" if category == "Rent" else "💰 Продажа (Sales)"
    type_map = {"all": "Квартиры и Дома", "Apartments": "🏢 Квартиры", "Houses": "🏠 Дома"}
    dist_str = "Все районы" if district == "all" else district
    rooms_str = "Любое" if rooms == "all" else f"{rooms}-комн."

    return (
        "<blockquote>"
        "<b>🏢 РБД УПРАВЛЕНИЕ НЕДВИЖИМОСТЬЮ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📂 <b>Текущий раздел:</b> {cat_name}\n"
        f"🏘 <b>Тип недвижимости:</b> {type_map.get(prop_type, prop_type)}\n"
        f"🚪 <b>Комнатность:</b> {rooms_str}\n"
        f"📍 <b>Район:</b> {dist_str}\n"
        f"📊 <b>Найдено объектов:</b> <code>{count}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Используйте кнопки внизу для навигации:</i>"
        "</blockquote>"
    )

def render_object_panel(ad: tuple, index: int, total: int) -> str:
    ad_num, category, prop_type, rooms, district, landmark, area, floor, floors_total, price = ad
    cat_label = "Аренда" if category == "Rent" else "Продажа"
    
    try:
        price_fmt = f"{int(price):,}".replace(",", " ") if float(price).is_integer() else f"{price:,.2f}".replace(",", " ")
    except Exception:
        price_fmt = str(price)

    if prop_type == "Houses":
        plot_size = floor if floor not in (None, 0) else (area or "—")
        header = f"🏠 ДОМ № {ad_num}"
        specific_lines = (
            f"🚪 <b>Кол-во комнат:</b> {rooms or '—'}\n"
            f"📐 <b>Площадь участка:</b> {plot_size} сот.\n"
            f"🏗 <b>Этажность дома:</b> {floors_total or '—'}\n"
        )
        footer_type = f"{cat_label} • Дом"
    else:
        header = f"🏢 КВАРТИРА № {ad_num}"
        specific_lines = (
            f"🚪 <b>Кол-во комнат:</b> {rooms or '—'}\n"
            f"🏗 <b>Этаж:</b> {floor or '—'} из {floors_total or '—'}\n"
        )
        footer_type = f"{cat_label} • Квартира"

    return (
        "<blockquote>"
        f"<b>{header}</b>  <i>({index + 1} из {total})</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 <b>Район:</b> {district or '—'}\n"
        f"🧭 <b>Ориентир:</b> {landmark or '—'}\n"
        f"{specific_lines}"
        f"💰 <b>Цена:</b> <b>{price_fmt} $</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Категория: {footer_type}</i>"
        "</blockquote>"
    )

def get_object_keyboard(index: int, total: int, ad_num: str) -> InlineKeyboardMarkup:
    prev_idx = (index - 1) % total
    next_idx = (index + 1) % total

    buttons = [
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"browse:{prev_idx}"),
            InlineKeyboardButton(text=f"{index + 1} / {total}", callback_data="noop"),
            InlineKeyboardButton(text="Вперед ➡️", callback_data=f"browse:{next_idx}"),
        ],
        [
            InlineKeyboardButton(text="📁 Медиафайлы (Фото / Видео)", callback_data=f"media:{ad_num}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- ОБРАБОТЧИКИ КОМАНД И КНОПОК ---

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.update_data(category="Rent", prop_type="all", district="all", rooms="all")
    ads = db.get_filtered_ads(category="Rent")
    
    await message.answer(
        text=render_main_panel(len(ads), category="Rent"),
        reply_markup=get_main_menu_keyboard(category="Rent"),
        parse_mode="HTML"
    )

@router.message(F.text.in_({"🔑 Переключить на Аренду", "💰 Переключить на Продажу"}))
async def toggle_category(message: types.Message, state: FSMContext):
    data = await state.get_data()
    curr = data.get("category", "Rent")
    new_cat = "Sales" if curr == "Rent" else "Rent"
    await state.update_data(category=new_cat)
    
    ads = db.get_filtered_ads(category=new_cat, prop_type=data.get("prop_type", "all"), district=data.get("district", "all"), rooms=data.get("rooms", "all"))
    
    await message.answer(
        text=render_main_panel(len(ads), category=new_cat, prop_type=data.get("prop_type", "all"), district=data.get("district", "all"), rooms=data.get("rooms", "all")),
        reply_markup=get_main_menu_keyboard(category=new_cat),
        parse_mode="HTML"
    )

@router.message(F.text == "🏢 Квартиры (Аренда / Продажа)")
async def select_apartments(message: types.Message, state: FSMContext):
    await state.update_data(prop_type="Apartments")
    data = await state.get_data()
    ads = db.get_filtered_ads(category=data.get("category", "Rent"), prop_type="Apartments", district=data.get("district", "all"), rooms=data.get("rooms", "all"))
    
    await message.answer(
        text=render_main_panel(len(ads), category=data.get("category", "Rent"), prop_type="Apartments", district=data.get("district", "all"), rooms=data.get("rooms", "all")),
        reply_markup=get_main_menu_keyboard(category=data.get("category", "Rent")),
        parse_mode="HTML"
    )

@router.message(F.text == "🏠 Дома (Аренда / Продажа)")
async def select_houses(message: types.Message, state: FSMContext):
    await state.update_data(prop_type="Houses")
    data = await state.get_data()
    ads = db.get_filtered_ads(category=data.get("category", "Rent"), prop_type="Houses", district=data.get("district", "all"), rooms=data.get("rooms", "all"))
    
    await message.answer(
        text=render_main_panel(len(ads), category=data.get("category", "Rent"), prop_type="Houses", district=data.get("district", "all"), rooms=data.get("rooms", "all")),
        reply_markup=get_main_menu_keyboard(category=data.get("category", "Rent")),
        parse_mode="HTML"
    )

@router.message(F.text == "🔄 Сбросить фильтры")
async def reset_filters(message: types.Message, state: FSMContext):
    await state.update_data(category="Rent", prop_type="all", district="all", rooms="all")
    ads = db.get_filtered_ads(category="Rent")
    
    await message.answer(
        text=render_main_panel(len(ads), category="Rent"),
        reply_markup=get_main_menu_keyboard(category="Rent"),
        parse_mode="HTML"
    )

@router.message(F.text == "📋 Показать объекты")
async def show_objects(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ads = db.get_filtered_ads(
        category=data.get("category", "Rent"),
        prop_type=data.get("prop_type", "all"),
        district=data.get("district", "all"),
        rooms=data.get("rooms", "all")
    )
    if not ads:
        await message.answer("📭 По вашим параметрам не найдено объектов в базе данных.")
        return
    
    ad = ads[0]
    await message.answer(
        text=render_object_panel(ad, 0, len(ads)),
        reply_markup=get_object_keyboard(0, len(ads), str(ad[0])),
        parse_mode="HTML"
    )

@router.message(F.text == "🚪 Выбрать комнатность")
async def menu_rooms(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1-комн.", callback_data="set_rooms:1"),
            InlineKeyboardButton(text="2-комн.", callback_data="set_rooms:2"),
            InlineKeyboardButton(text="3-комн.", callback_data="set_rooms:3"),
        ],
        [
            InlineKeyboardButton(text="4-комн.", callback_data="set_rooms:4"),
            InlineKeyboardButton(text="5-комн.", callback_data="set_rooms:5"),
            InlineKeyboardButton(text="Любое", callback_data="set_rooms:all"),
        ]
    ])
    await message.answer("🚪 Выберите количество комнат:", reply_markup=kb)

@router.message(F.text == "📍 Выбрать район")
async def menu_district(message: types.Message, state: FSMContext):
    data = await state.get_data()
    districts = db.get_active_districts(
        category=data.get("category", "Rent"),
        prop_type=data.get("prop_type", "all")
    )
    if not districts:
        await message.answer("📍 Нет доступных районов по текущим фильтрам.")
        return
        
    kb = []
    for i in range(0, len(districts), 2):
        row = [InlineKeyboardButton(text=f"📍 {d}", callback_data=f"set_dist:{d}") for d in districts[i:i+2]]
        kb.append(row)
    kb.append([InlineKeyboardButton(text="🌍 Все районы", callback_data="set_dist:all")])

    await message.answer("📍 Выберите район из списка:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# --- ОБРАБОТЧИКИ ИНЛАЙН-КНОПОК ---

@router.callback_query(F.data.startswith("set_dist:"))
async def set_district(callback: types.CallbackQuery, state: FSMContext):
    dist = callback.data.split(":", 1)[1]
    await state.update_data(district=dist)
    data = await state.get_data()
    
    ads = db.get_filtered_ads(category=data.get("category", "Rent"), prop_type=data.get("prop_type", "all"), district=data.get("district", "all"), rooms=data.get("rooms", "all"))
    
    await callback.message.edit_text(
        text=render_main_panel(len(ads), category=data.get("category", "Rent"), prop_type=data.get("prop_type", "all"), district=data.get("district", "all"), rooms=data.get("rooms", "all")),
        parse_mode="HTML"
    )
    await callback.answer(f"Район выбран: {dist}")

@router.callback_query(F.data.startswith("set_rooms:"))
async def set_rooms(callback: types.CallbackQuery, state: FSMContext):
    rooms = callback.data.split(":")[1]
    await state.update_data(rooms=rooms)
    data = await state.get_data()
    
    ads = db.get_filtered_ads(category=data.get("category", "Rent"), prop_type=data.get("prop_type", "all"), district=data.get("district", "all"), rooms=data.get("rooms", "all"))
    
    await callback.message.edit_text(
        text=render_main_panel(len(ads), category=data.get("category", "Rent"), prop_type=data.get("prop_type", "all"), district=data.get("district", "all"), rooms=data.get("rooms", "all")),
        parse_mode="HTML"
    )
    await callback.answer(f"Комнатность выбрана: {rooms}")

@router.callback_query(F.data.startswith("browse:"))
async def browse_objects(callback: types.CallbackQuery, state: FSMContext):
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    ads = db.get_filtered_ads(
        category=data.get("category", "Rent"),
        prop_type=data.get("prop_type", "all"),
        district=data.get("district", "all"),
        rooms=data.get("rooms", "all")
    )
    if not ads:
        await callback.answer("Объектов нет", show_alert=True)
        return

    idx = idx % len(ads)
    ad = ads[idx]
    ad_num = str(ad[0])

    await callback.message.edit_text(
        text=render_object_panel(ad, idx, len(ads)),
        reply_markup=get_object_keyboard(idx, len(ads), ad_num),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("media:"))
async def send_object_media(callback: types.CallbackQuery):
    ad_num = callback.data.split(":", 1)[1]
    files = db.get_ad_media_files(ad_num)

    if not files:
        await callback.answer(f"У объекта № {ad_num} нет медиафайлов", show_alert=True)
        return

    media_group = []
    for idx, (fname, fdata) in enumerate(files[:10]):
        ext = fname.lower().split('.')[-1] if '.' in fname else 'jpg'
        inp_file = BufferedInputFile(bytes(fdata), filename=fname)
        caption = f"📁 Медиафайлы к объекту № {ad_num}" if idx == 0 else None

        if ext in ['mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv']:
            media_group.append(InputMediaVideo(media=inp_file, caption=caption))
        else:
            media_group.append(InputMediaPhoto(media=inp_file, caption=caption))

    await callback.message.answer_media_group(media=media_group)
    await callback.answer()

@router.callback_query(F.data == "noop")
async def noop(callback: types.Category = None, callback_query: types.CallbackQuery = None):
    if callback_query:
        await callback_query.answer()