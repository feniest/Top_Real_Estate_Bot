from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile, InputMediaPhoto, InputMediaVideo
from aiogram.fsm.context import FSMContext
import database as db

router = Router()

# --- 1. НИЖНЯЯ КЛАВИАТУРА (ReplyKeyboard) — ВСЕГДА ПОД РУКОЙ ---

def get_reply_keyboard(category: str = "all", prop_type: str = "all") -> ReplyKeyboardMarkup:
    rent_txt = "✅ Аренда" if category == "Rent" else "🔑 Аренда"
    sales_txt = "✅ Продажа" if category == "Sales" else "💰 Продажа"
    apt_txt = "✅ Квартиры" if prop_type == "Apartments" else "🏢 Квартиры"
    house_txt = "✅ Дома" if prop_type == "Houses" else "🏠 Дома"

    keyboard = [
        [KeyboardButton(text=rent_txt), KeyboardButton(text=sales_txt)],
        [KeyboardButton(text=apt_txt), KeyboardButton(text=house_txt)],
        [KeyboardButton(text="📍 Выбрать район"), KeyboardButton(text="🚪 Комнаты")],
        [KeyboardButton(text="📋 Смотреть каталог"), KeyboardButton(text="🔄 Сброс фильтров")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# --- 2. ФОРМИРОВАНИЕ ИНФОРМАЦИИ (В РАМКЕ) ---

def render_main_panel(count: int, category: str = "all", prop_type: str = "all", district: str = "all", rooms: str = "all") -> str:
    cat_map = {"all": "Все (Аренда и Продажа)", "Rent": "🔑 Аренда", "Sales": "💰 Продажа"}
    type_map = {"all": "Квартиры и Дома", "Apartments": "🏢 Квартиры", "Houses": "🏠 Дома"}
    dist_str = "Все районы" if district == "all" else district
    rooms_str = "Любое" if rooms == "all" else f"{rooms}-комн."

    return (
        "<blockquote>"
        "<b>🏢 TOP REAL ESTATE | ПАНЕЛЬ УПРАВЛЕНИЯ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Найдено объектов:</b> <code>{count}</code>\n"
        f"🏷 <b>Сделка:</b> {cat_map.get(category, category)}\n"
        f"🏘 <b>Тип жилья:</b> {type_map.get(prop_type, prop_type)}\n"
        f"🚪 <b>Комнат:</b> {rooms_str}\n"
        f"📍 <b>Район:</b> {dist_str}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Используйте кнопки внизу экрана для управления фильтрами:</i>"
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

# --- 3. ИНЛАЙН-КНОПКИ ТОЛЬКО ДЛЯ ЛИСТАНИЯ И ФОТО ---

def get_object_keyboard(index: int, total: int, ad_num: str) -> InlineKeyboardMarkup:
    prev_idx = (index - 1) % total
    next_idx = (index + 1) % total

    buttons = [
        [
            InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"browse:{prev_idx}"),
            InlineKeyboardButton(text=f"{index + 1} / {total}", callback_data="noop"),
            InlineKeyboardButton(text="След. ➡️", callback_data=f"browse:{next_idx}"),
        ],
        [
            InlineKeyboardButton(text="🖼 Фото / Видео объекта", callback_data=f"media:{ad_num}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- 4. ОБРАБОТЧИКИ СОБЫТИЙ И КНОПОК НИЖНЕЙ КЛАВИАТУРЫ ---

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.update_data(category="all", prop_type="all", district="all", rooms="all")
    ads = db.get_filtered_ads()
    
    await message.answer(
        text=render_main_panel(len(ads)),
        reply_markup=get_reply_keyboard(),
        parse_mode="HTML"
    )

@router.message(F.text.in_({"🔑 Аренда", "✅ Аренда"}))
async def handle_rent(message: types.Message, state: FSMContext):
    data = await state.get_data()
    curr = data.get("category")
    new_val = "all" if curr == "Rent" else "Rent"
    await state.update_data(category=new_val)
    
    data = await state.get_data()
    ads = db.get_filtered_ads(category=data.get("category"), prop_type=data.get("prop_type"), district=data.get("district"), rooms=data.get("rooms"))
    
    await message.answer(
        text=render_main_panel(len(ads), data.get("category"), data.get("prop_type"), data.get("district"), data.get("rooms")),
        reply_markup=get_reply_keyboard(data.get("category"), data.get("prop_type")),
        parse_mode="HTML"
    )

@router.message(F.text.in_({"💰 Продажа", "✅ Продажа"}))
async def handle_sales(message: types.Message, state: FSMContext):
    data = await state.get_data()
    curr = data.get("category")
    new_val = "all" if curr == "Sales" else "Sales"
    await state.update_data(category=new_val)
    
    data = await state.get_data()
    ads = db.get_filtered_ads(category=data.get("category"), prop_type=data.get("prop_type"), district=data.get("district"), rooms=data.get("rooms"))
    
    await message.answer(
        text=render_main_panel(len(ads), data.get("category"), data.get("prop_type"), data.get("district"), data.get("rooms")),
        reply_markup=get_reply_keyboard(data.get("category"), data.get("prop_type")),
        parse_mode="HTML"
    )

@router.message(F.text.in_({"🏢 Квартиры", "✅ Квартиры"}))
async def handle_apartments(message: types.Message, state: FSMContext):
    data = await state.get_data()
    curr = data.get("prop_type")
    new_val = "all" if curr == "Apartments" else "Apartments"
    await state.update_data(prop_type=new_val)
    
    data = await state.get_data()
    ads = db.get_filtered_ads(category=data.get("category"), prop_type=data.get("prop_type"), district=data.get("district"), rooms=data.get("rooms"))
    
    await message.answer(
        text=render_main_panel(len(ads), data.get("category"), data.get("prop_type"), data.get("district"), data.get("rooms")),
        reply_markup=get_reply_keyboard(data.get("category"), data.get("prop_type")),
        parse_mode="HTML"
    )

@router.message(F.text.in_({"🏠 Дома", "✅ Дома"}))
async def handle_houses(message: types.Message, state: FSMContext):
    data = await state.get_data()
    curr = data.get("prop_type")
    new_val = "all" if curr == "Houses" else "Houses"
    await state.update_data(prop_type=new_val)
    
    data = await state.get_data()
    ads = db.get_filtered_ads(category=data.get("category"), prop_type=data.get("prop_type"), district=data.get("district"), rooms=data.get("rooms"))
    
    await message.answer(
        text=render_main_panel(len(ads), data.get("category"), data.get("prop_type"), data.get("district"), data.get("rooms")),
        reply_markup=get_reply_keyboard(data.get("category"), data.get("prop_type")),
        parse_mode="HTML"
    )

@router.message(F.text == "🔄 Сброс фильтров")
async def handle_reset(message: types.Message, state: FSMContext):
    await state.update_data(category="all", prop_type="all", district="all", rooms="all")
    ads = db.get_filtered_ads()
    await message.answer(
        text=render_main_panel(len(ads)),
        reply_markup=get_reply_keyboard(),
        parse_mode="HTML"
    )

@router.message(F.text == "📋 Смотреть каталог")
async def handle_browse_start(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ads = db.get_filtered_ads(
        category=data.get("category", "all"),
        prop_type=data.get("prop_type", "all"),
        district=data.get("district", "all"),
        rooms=data.get("rooms", "all")
    )
    if not ads:
        await message.answer("📭 По вашим фильтрам не найдено объектов.")
        return
    
    ad = ads[0]
    await message.answer(
        text=render_object_panel(ad, 0, len(ads)),
        reply_markup=get_object_keyboard(0, len(ads), str(ad[0])),
        parse_mode="HTML"
    )

@router.message(F.text == "🚪 Комнаты")
async def handle_rooms_menu(message: types.Message):
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
async def handle_district_menu(message: types.Message, state: FSMContext):
    data = await state.get_data()
    districts = db.get_active_districts(
        category=data.get("category", "all"),
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

# --- 5. ОБРАБОТЧИКИ INLINE-КНОПОК (РАЙОНЫ, КОМНАТЫ, ЛИСТАНИЕ, ФОТО) ---

@router.callback_query(F.data.startswith("set_dist:"))
async def set_district(callback: types.CallbackQuery, state: FSMContext):
    dist = callback.data.split(":", 1)[1]
    await state.update_data(district=dist)
    data = await state.get_data()
    ads = db.get_filtered_ads(category=data.get("category"), prop_type=data.get("prop_type"), district=data.get("district"), rooms=data.get("rooms"))
    
    await callback.message.edit_text(
        text=render_main_panel(len(ads), data.get("category"), data.get("prop_type"), data.get("district"), data.get("rooms")),
        parse_mode="HTML"
    )
    await callback.answer(f"Район изменен: {dist}")

@router.callback_query(F.data.startswith("set_rooms:"))
async def set_rooms(callback: types.CallbackQuery, state: FSMContext):
    rooms = callback.data.split(":")[1]
    await state.update_data(rooms=rooms)
    data = await state.get_data()
    ads = db.get_filtered_ads(category=data.get("category"), prop_type=data.get("prop_type"), district=data.get("district"), rooms=data.get("rooms"))
    
    await callback.message.edit_text(
        text=render_main_panel(len(ads), data.get("category"), data.get("prop_type"), data.get("district"), data.get("rooms")),
        parse_mode="HTML"
    )
    await callback.answer(f"Комнатность изменена: {rooms}")

@router.callback_query(F.data.startswith("browse:"))
async def browse_objects(callback: types.CallbackQuery, state: FSMContext):
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    ads = db.get_filtered_ads(
        category=data.get("category", "all"),
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
        caption = f"📸 Медиафайлы к объекту № {ad_num}" if idx == 0 else None

        if ext in ['mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv']:
            media_group.append(InputMediaVideo(media=inp_file, caption=caption))
        else:
            media_group.append(InputMediaPhoto(media=inp_file, caption=caption))

    await callback.message.answer_media_group(media=media_group)
    await callback.answer()

@router.callback_query(F.data == "noop")
async def noop(callback: types.CallbackQuery):
    await callback.answer()