from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile, InputMediaPhoto, InputMediaVideo
from aiogram.fsm.context import FSMContext
import database as db

router = Router()

# --- 1. ВЕРХНЯЯ ИНФОРМАЦИОННАЯ ПАНЕЛЬ (В РАМКЕ) ---

def render_main_panel(count: int, category: str = "all", prop_type: str = "all", district: str = "all", rooms: str = "all") -> str:
    cat_map = {"all": "Все (Аренда и Продажа)", "Rent": "🔑 Аренда", "Sales": "💰 Продажа"}
    type_map = {"all": "Квартиры и Дома", "Apartments": "🏢 Квартиры", "Houses": "🏠 Дома"}
    dist_str = "Все районы" if district == "all" else district
    rooms_str = "Любое" if rooms == "all" else f"{rooms}-комн."

    return (
        "<blockquote>"
        "<b>🏢 TOP REAL ESTATE | БАЗА НЕДВИЖИМОСТИ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Найдено объектов:</b> <code>{count}</code>\n"
        f"🏷 <b>Сделка:</b> {cat_map.get(category, category)}\n"
        f"🏘 <b>Тип жилья:</b> {type_map.get(prop_type, prop_type)}\n"
        f"🚪 <b>Комнат:</b> {rooms_str}\n"
        f"📍 <b>Район:</b> {dist_str}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Выберите параметры ниже или откройте каталог:</i>"
        "</blockquote>"
    )

def render_object_panel(ad: tuple, index: int, total: int) -> str:
    # Распаковка строго по SELECT:
    # ad_number, category, property_type, rooms, district, landmark, area, floor, floors_total, price
    ad_num, category, prop_type, rooms, district, landmark, area, floor, floors_total, price = ad

    cat_label = "Аренда" if category == "Rent" else "Продажа"
    
    # Форматируем цену красиво (без лишних .0, если число целое)
    try:
        price_fmt = f"{int(price):,}".replace(",", " ") if float(price).is_integer() else f"{price:,.2f}".replace(",", " ")
    except Exception:
        price_fmt = str(price)

    if prop_type == "Houses":
        # Карточка для ДОМА
        plot_size = floor if floor not in (None, 0) else (area or "—")
        header = f"🏠 ДОМ № {ad_num}"
        specific_lines = (
            f"🚪 <b>Кол-во комнат:</b> {rooms or '—'}\n"
            f"📐 <b>Площадь участка:</b> {plot_size} сот.\n"
            f"🏗 <b>Этажность дома:</b> {floors_total or '—'}\n"
        )
        footer_type = f"{cat_label} • Дом"
    else:
        # Карточка для КВАРТИРЫ
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

# --- 2. НИЖНЯЯ ПАНЕЛЬ УПРАВЛЕНИЯ (INLINE-КНОПКИ) ---

def get_main_keyboard(count: int, category: str = "all", prop_type: str = "all") -> InlineKeyboardMarkup:
    rent_txt = "✅ Аренда" if category == "Rent" else "🔑 Аренда"
    sales_txt = "✅ Продажа" if category == "Sales" else "💰 Продажа"
    
    apt_txt = "✅ Квартиры" if prop_type == "Apartments" else "🏢 Квартиры"
    house_txt = "✅ Дома" if prop_type == "Houses" else "🏠 Дома"

    buttons = [
        [
            InlineKeyboardButton(text=rent_txt, callback_data="f_cat:Rent"),
            InlineKeyboardButton(text=sales_txt, callback_data="f_cat:Sales"),
        ],
        [
            InlineKeyboardButton(text=apt_txt, callback_data="f_type:Apartments"),
            InlineKeyboardButton(text=house_txt, callback_data="f_type:Houses"),
        ],
        [
            InlineKeyboardButton(text="📍 Район", callback_data="menu_district"),
            InlineKeyboardButton(text="🚪 Комнаты", callback_data="menu_rooms"),
            InlineKeyboardButton(text="🔄 Сброс", callback_data="f_reset"),
        ],
        [
            InlineKeyboardButton(
                text=f"📋 Смотреть объекты ({count}) ➡️" if count > 0 else "📭 Объектов не найдено",
                callback_data="browse:0" if count > 0 else "noop"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

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
        ],
        [
            InlineKeyboardButton(text="🔙 Назад к фильтрам", callback_data="back_main"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- 3. ОБРАБОТЧИКИ КОМАНД И КНОПОК ---

async def refresh_main_screen(target, state: FSMContext, is_edit: bool = True):
    data = await state.get_data()
    cat = data.get("category", "all")
    ptype = data.get("prop_type", "all")
    dist = data.get("district", "all")
    rooms = data.get("rooms", "all")

    ads = db.get_filtered_ads(category=cat, prop_type=ptype, district=dist, rooms=rooms)
    text = render_main_panel(len(ads), cat, ptype, dist, rooms)
    kb = get_main_keyboard(len(ads), cat, ptype)

    if is_edit:
        await target.edit_text(text=text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.answer(text=text, reply_markup=kb, parse_mode="HTML")

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.update_data(category="all", prop_type="all", district="all", rooms="all")
    await refresh_main_screen(message, state, is_edit=False)

@router.callback_query(F.data.startswith("f_cat:"))
async def filter_category(callback: types.CallbackQuery, state: FSMContext):
    val = callback.data.split(":")[1]
    data = await state.get_data()
    new_val = "all" if data.get("category") == val else val
    await state.update_data(category=new_val)
    await refresh_main_screen(callback.message, state, is_edit=True)
    await callback.answer()

@router.callback_query(F.data.startswith("f_type:"))
async def filter_prop_type(callback: types.CallbackQuery, state: FSMContext):
    val = callback.data.split(":")[1]
    data = await state.get_data()
    new_val = "all" if data.get("prop_type") == val else val
    await state.update_data(prop_type=new_val)
    await refresh_main_screen(callback.message, state, is_edit=True)
    await callback.answer()

@router.callback_query(F.data == "menu_district")
async def menu_district(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    districts = db.get_active_districts(
        category=data.get("category", "all"),
        prop_type=data.get("prop_type", "all")
    )
    kb = []
    for i in range(0, len(districts), 2):
        row = [InlineKeyboardButton(text=f"📍 {d}", callback_data=f"set_dist:{d}") for d in districts[i:i+2]]
        kb.append(row)
    kb.append([InlineKeyboardButton(text="🌍 Все районы", callback_data="set_dist:all")])
    kb.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="back_main")])

    await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("set_dist:"))
async def set_district(callback: types.CallbackQuery, state: FSMContext):
    dist = callback.data.split(":", 1)[1]
    await state.update_data(district=dist)
    await refresh_main_screen(callback.message, state, is_edit=True)
    await callback.answer()

@router.callback_query(F.data == "menu_rooms")
async def menu_rooms(callback: types.CallbackQuery):
    kb = [
        [
            InlineKeyboardButton(text="1-комн.", callback_data="set_rooms:1"),
            InlineKeyboardButton(text="2-комн.", callback_data="set_rooms:2"),
            InlineKeyboardButton(text="3-комн.", callback_data="set_rooms:3"),
        ],
        [
            InlineKeyboardButton(text="4-комн.", callback_data="set_rooms:4"),
            InlineKeyboardButton(text="5-комн.", callback_data="set_rooms:5"),
            InlineKeyboardButton(text="Любое", callback_data="set_rooms:all"),
        ],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_main")]
    ]
    await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("set_rooms:"))
async def set_rooms(callback: types.CallbackQuery, state: FSMContext):
    rooms = callback.data.split(":")[1]
    await state.update_data(rooms=rooms)
    await refresh_main_screen(callback.message, state, is_edit=True)
    await callback.answer()

@router.callback_query(F.data == "f_reset")
async def filter_reset(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(category="all", prop_type="all", district="all", rooms="all")
    await refresh_main_screen(callback.message, state, is_edit=True)
    await callback.answer("Фильтры сброшены")

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
        await callback.answer("Объектов по заданным фильтрам нет", show_alert=True)
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
        await callback.answer(f"У объекта № {ad_num} пока нет фото или видео", show_alert=True)
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

@router.callback_query(F.data == "back_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await refresh_main_screen(callback.message, state, is_edit=True)
    await callback.answer()

@router.callback_query(F.data == "noop")
async def noop(callback: types.CallbackQuery):
    await callback.answer()