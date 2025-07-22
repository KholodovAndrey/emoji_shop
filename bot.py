import os
import json
import asyncio
import random
import string
import logging
import time
from datetime import datetime
from pathlib import Path
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import (
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Настройки бота
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Категории меню
CATEGORIES = {
    "breakfast": "Завтрак 🍳",
    "lunchdinner": "Обед и ужин 🥘",
    "drinks": "Напитки 🥤",
    "outdoor": "Вне дома 🥩",
    "delivery": "Заказать домой 🍱",
    "guests": "Пожрать в гостях🍕",
    "compote": "Как компотик🍹",
    "bichis": "Как бичи 🦴",
    "banquet": "Банкет (для гостей) 👻"
}

# Специальные категории
UNEDITABLE_CATEGORIES = ['outdoor', 'delivery', 'guests', 'compote', 'bichis', 'banquet']

# Пути к файлам
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
PHOTOS_DIR = DATA_DIR / 'photos'

# Генератор ID заказа
def generate_order_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# Инициализация папок
def init_folders():
    try:
        os.makedirs(PHOTOS_DIR, exist_ok=True)
        for file in ['menu.json', 'orders.json', 'active_orders.json']:
            if not (DATA_DIR / file).exists():
                with open(DATA_DIR / file, 'w') as f:
                    json.dump({}, f)
    except Exception as e:
        logger.error(f"Ошибка инициализации папок: {e}")

# Состояния
class MenuStates(StatesGroup):
    main_menu = State()
    categories = State()
    category_items = State()
    view_item = State()
    my_order = State()
    edit_order = State()
    admin_panel = State()
    banquet_guests = State()
    banquet_level = State()

class AdminStates(StatesGroup):
    add_category = State()
    add_item_name = State()
    add_item_desc = State()
    add_item_price = State()
    add_item_photo = State()
    delete_item = State()

# Загрузка данных
def load_db():
    init_folders()
    try:
        with open(DATA_DIR / 'menu.json', 'r') as f:
            menu = json.load(f)
            for cat in CATEGORIES:
                if cat not in menu:
                    menu[cat] = {}
    except Exception as e:
        logger.error(f"Ошибка загрузки menu.json: {e}")
        menu = {cat: {} for cat in CATEGORIES}
    
    try:
        with open(DATA_DIR / 'orders.json', 'r') as f:
            orders = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки orders.json: {e}")
        orders = {}
    
    try:
        with open(DATA_DIR / 'active_orders.json', 'r') as f:
            active_orders = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки active_orders.json: {e}")
        active_orders = {}
    
    return menu, orders, active_orders

# Сохранение данных
def save_db(menu, orders, active_orders):
    try:
        with open(DATA_DIR / 'menu.json', 'w') as f:
            json.dump(menu, f, indent=2)
        with open(DATA_DIR / 'orders.json', 'w') as f:
            json.dump(orders, f, indent=2)
        with open(DATA_DIR / 'active_orders.json', 'w') as f:
            json.dump(active_orders, f, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения данных: {e}")

menu, orders, active_orders = load_db()

# ====================== ОСНОВНЫЕ ХЕНДЛЕРЫ ======================

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id == ADMIN_ID:
        await admin_panel(message, state)
    else:
        await show_user_menu(message)

async def show_user_menu(message: types.Message):
    welcome_text = (
        "Добро пожаловать в кафе «Кацулька» 💗\n"
        "\n"
        "В нашем заведении подают только горячие блюда, как и Вы 🔥\n"
        "\n"
        "Главный шеф-повар и по совместительству владелица кафе - заМУРРРчательная Виктория 💗\n"
        "\n"
        "Заранее предупреждаем, оплата у нас необычная, приятного аппетита 🫶🏻"
    )
    
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text="🍽 Меню",
        callback_data="categories"
    ))
    
    await message.answer(welcome_text, reply_markup=builder.as_markup())

# ====================== ПОЛЬЗОВАТЕЛЬСКИЙ ФУНКЦИОНАЛ ======================

@dp.callback_query(F.data == "categories")
async def show_categories(call: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки категорий
    for cat_id, cat_name in CATEGORIES.items():
        builder.add(types.InlineKeyboardButton(
            text=cat_name,
            callback_data=f"category_{cat_id}"
        ))
    
    # Добавляем кнопку "Мой заказ" в отдельный ряд
    builder.row(
        types.InlineKeyboardButton(
            text="🛒 Мой заказ",
            callback_data="my_order"
        )
    )
    
    builder.adjust(2)  # Размещаем категории по 2 в ряд
    
    try:
        await call.message.edit_text(
            "🍽 Выберите категорию:",
            reply_markup=builder.as_markup()
        )
    except Exception:
        await call.message.answer(
            "🍽 Выберите категорию:",
            reply_markup=builder.as_markup()
        )

@dp.callback_query(F.data.startswith('category_'))
async def show_category_items(call: types.CallbackQuery):
    await call.answer()
    try:
        cat_id = call.data.split('_')[1]
        
        if cat_id in UNEDITABLE_CATEGORIES:
            await handle_special_category(call, cat_id)
            return
            
        cat_name = CATEGORIES[cat_id]
        category_menu = menu.get(cat_id, {})
        
        if not category_menu:
            await call.answer("В этой категории пока нет позиций")
            return
        
        builder = InlineKeyboardBuilder()
        for item_id, item in category_menu.items():
            builder.add(types.InlineKeyboardButton(
                text=item['name'],
                callback_data=f"item_{cat_id}_{item_id}"
            ))
        builder.adjust(2)
        
        builder.row(
            types.InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="categories"
            ),
            types.InlineKeyboardButton(
                text="🛒 Мой заказ",
                callback_data="my_order"
            )
        )
        
        await call.message.edit_text(
            f"🍽 {cat_name}:",
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Ошибка показа категории: {e}")
        await call.message.answer("❌ Ошибка загрузки категории")

async def handle_special_category(call: types.CallbackQuery, category: str):
    try:
        if category == 'outdoor':
            text = (
                "Дорогой дневник!\n"
                "Мне не описать эту боль….да кого я обманываю?\n"
                "Едем!\n"
                "Я пока меняю фартук на наряд, ты подыскивай место 😍\n"
                "Оплата: комплимент от шеф-повара - 1 страстный поцелуй и любое желание hot 🔥🔞"
            )
            photo_path = str(PHOTOS_DIR / 'outdoor.jpg')
    
            builder = InlineKeyboardBuilder()
            builder.add(types.InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="categories"
            ))
    
    # Отправляем сообщение пользователю
            await call.message.answer_photo(
                FSInputFile(photo_path),
                caption=text,
                reply_markup=builder.as_markup()
            )
    
    # Уведомление админу с кнопкой
            if ADMIN_ID:
                admin_builder = InlineKeyboardBuilder()
                admin_builder.add(types.InlineKeyboardButton(
                    text="🟢 Погнали!",
                    callback_data=f"outdoor_confirm_{call.from_user.id}"
                ))
        
                await bot.send_message(
                    ADMIN_ID,
                    f"🍽 Кто-то хочет по ресторанам!\n",
                    reply_markup=admin_builder.as_markup()
                )

            
        elif category == 'delivery':
            text = (
                "Ммм, несмотря на то, что вы решили дать отдохнуть заМУРРРчательному повару, "
                "Вы все равно любимая жопа 😏"
            )
            
            builder = InlineKeyboardBuilder()
            builder.add(types.InlineKeyboardButton(
                text="Продолжить",
                callback_data="delivery_continue"
            ))
            
            await call.message.answer(text, reply_markup=builder.as_markup())
            
        elif category == 'guests':
            text = "Дорогой Любимка, ты решил наебать систему 😈"
            
            builder = InlineKeyboardBuilder()
            builder.add(types.InlineKeyboardButton(
                text="Продолжить",
                callback_data="guests_continue"
            ))
            
            await call.message.answer(text, reply_markup=builder.as_markup())
            
        elif category == 'compote':
            text = (
                "Давай нахуяримся!\n"
                "Выбирай настоичную или бар и погнали в ебета 🚀"
            )
            photo_path = str(PHOTOS_DIR / 'compote.jpg')
            
            builder = InlineKeyboardBuilder()
            builder.add(types.InlineKeyboardButton(
                text="Продолжить",
                callback_data="compote_continue"
            ))
            
            await call.message.answer_photo(
                FSInputFile(photo_path),
                caption=text,
                reply_markup=builder.as_markup()
            )
            
        elif category == 'bichis':
            text = "Ну что, сладкий мой, по дошику или шавухе?😵‍💫"
            
            builder = InlineKeyboardBuilder()
            builder.add(types.InlineKeyboardButton(
                text="Шавуха",
                callback_data="bichis_shawarma"
            ))
            builder.add(types.InlineKeyboardButton(
                text="Дошик",
                callback_data="bichis_doshik"
            ))
            
            await call.message.answer(text, reply_markup=builder.as_markup())
            
        elif category == 'banquet':
            text = "Отлично, любимый, готовимся к приему гостей😈"
            
            builder = InlineKeyboardBuilder()
            builder.add(types.InlineKeyboardButton(
                text="Далее",
                callback_data="banquet_continue"
            ))
            
            await call.message.answer(text, reply_markup=builder.as_markup())
        
    except Exception as e:
        logger.error(f"Ошибка обработки специальной категории: {e}")
        await call.message.answer("❌ Ошибка загрузки категории")

@dp.callback_query(F.data == "delivery_continue")
async def delivery_continue_handler(call: types.CallbackQuery):
    try:
        # Отправляем первую картинку с вопросом
        photo_path = str(PHOTOS_DIR / 'delivery.jpg')
        
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(text="🟡", callback_data="delivery_yellow"),
            types.InlineKeyboardButton(text="🟢", callback_data="delivery_green")
        )
        
        await call.message.answer_photo(
            FSInputFile(photo_path),
            caption="Как думаете, кто победит в этой схватке?",
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в delivery_continue: {e}")
        await call.answer("❌ Ошибка загрузки, попробуйте позже")

@dp.callback_query(F.data.startswith("delivery_") & ~F.data.startswith("delivery_confirm_"))
async def delivery_final(call: types.CallbackQuery):
    try:
        # Отправляем финальную картинку пользователю
        await call.message.answer_photo(
            FSInputFile(PHOTOS_DIR / 'nedoljno.jpg'),
            caption="Оплата: комплимент от шеф-повара - 10 чмоков и минетик 👄🔞",
            reply_markup=InlineKeyboardBuilder()
                .button(text="🍽 В меню", callback_data="categories")
                .as_markup()
        )
        
        # Уведомление админу с кнопкой
        if ADMIN_ID:
            builder = InlineKeyboardBuilder()
            builder.add(types.InlineKeyboardButton(
                text="🟢 Отлично!",
                callback_data=f"delivery_confirm_{call.from_user.id}"
            ))
            
            await bot.send_message(
                ADMIN_ID,
                f"🚚 Кто-то хочет доставку!\n",
                reply_markup=builder.as_markup()
            )
            
    except Exception as e:
        logger.error(f"Ошибка в delivery_final: {e}")
        await call.answer("❌ Ошибка загрузки")

@dp.callback_query(F.data == "guests_continue")
async def guests_continue_handler(call: types.CallbackQuery):
    try:
        # Уведомление админу (отправляется сразу)
        if ADMIN_ID:
            await bot.send_message(
                ADMIN_ID,
                f"🍕 Кто-то хочет в гостях пожрать!\n"
                f"User: @{call.from_user.username or call.from_user.full_name}"
            )

        # Остальная логика для пользователя
        await call.message.answer_photo(
            FSInputFile(PHOTOS_DIR / 'guests.jpg'),
            caption="Любой из друзей, кого ты выберешь"
        )
        
        await asyncio.sleep(3)
        msg = await call.message.answer_photo(
            FSInputFile(PHOTOS_DIR / 'guests_reality.jpg'),
            caption="Поэтому будет так"
        )
        
        await asyncio.sleep(3)
        await msg.reply(
            "Так что, хитрожопый кот, возвращайся в меню 🥲\n"
            "Оплата: 100 рублей по номеру телефона 🤣🖕🏻",
            reply_markup=InlineKeyboardBuilder()
                .button(text="🍽 В меню", callback_data="categories")
                .as_markup()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в guests_continue: {e}")
        await call.answer("❌ Ошибка загрузки")

@dp.callback_query(F.data == "compote_continue")
async def compote_handler(call: types.CallbackQuery):
    try:
        # Удаляем кнопку "Продолжить" редактированием сообщения
        await call.message.edit_reply_markup(reply_markup=None)
        
        # Ждем 4 секунды
        await asyncio.sleep(2)
        
        # Отправляем картинку пользователю
        await call.message.answer_photo(
            FSInputFile(PHOTOS_DIR / 'nubla.jpg'),
            caption="Оплата: громкий протяженный крик «Ну бляяяя!» 🫨",
            reply_markup=InlineKeyboardBuilder()
                .button(text="🍽 В меню", callback_data="categories")
                .as_markup()
        )
        
        # Уведомление админу с кнопкой
        if ADMIN_ID:
            builder = InlineKeyboardBuilder()
            builder.add(types.InlineKeyboardButton(
                text="🍻 Давай нахуяримся!",
                callback_data=f"compote_confirm_{call.from_user.id}"
            ))
            
            await bot.send_message(
                ADMIN_ID,
                f"🌳 Кто-то хочет в дрова!\n",
                reply_markup=builder.as_markup()
            )
            
    except Exception as e:
        logger.error(f"Ошибка в compote_handler: {e}")
        await call.answer("❌ Что-то пошло не так...")

@dp.callback_query(F.data == "bichis_shawarma")
async def shawarma_handler(call: types.CallbackQuery):
    try:
        # Отправляем шаурму пользователю
        await call.message.answer_photo(
            FSInputFile(PHOTOS_DIR / 'shawarma.jpg'),
            caption="Че смотришь? Одевайся, идём за шавухой.\nОплата: 1 обнимашка 🤗",
            reply_markup=InlineKeyboardBuilder()
                .button(text="🍽 В меню", callback_data="categories")
                .as_markup()
        )
        
        # Уведомление админу
        if ADMIN_ID:
            user = call.from_user
            await bot.send_message(
                ADMIN_ID,
                "🥙 Кто-то хочет шавуху!"
            )
            
    except Exception as e:
        logger.error(f"Ошибка в shawarma_handler: {e}")
        await call.answer("❌ Шаурма закончилась...")

@dp.callback_query(F.data == "bichis_shawarma")
async def shawarma_handler(call: types.CallbackQuery):
    try:
        # Отправляем шаурму пользователю
        await call.message.answer_photo(
            FSInputFile(PHOTOS_DIR / 'shawarma.jpg'),
            caption="Че смотришь? Одевайся, идём за шавухой.\nОплата: 1 обнимашка 🤗",
            reply_markup=InlineKeyboardBuilder()
                .button(text="🍽 В меню", callback_data="categories")
                .as_markup()
        )
        
        # Уведомление админу с кнопкой
        if ADMIN_ID:
            builder = InlineKeyboardBuilder()
            builder.add(types.InlineKeyboardButton(
                text="🟢 Сифооооон!",
                callback_data=f"bichis_confirm_{call.from_user.id}_shawarma"
            ))
            
            await bot.send_message(
                ADMIN_ID,
                f"🥙 Кто-то хочет шавуху!\n",
                reply_markup=builder.as_markup()
            )
            
    except Exception as e:
        logger.error(f"Ошибка в shawarma_handler: {e}")
        await call.answer("❌ Шаурма закончилась...")

@dp.callback_query(F.data == "bichis_doshik")
async def doshik_handler(call: types.CallbackQuery):
    try:
        # Отправляем дошик пользователю
        await call.message.answer_photo(
            FSInputFile(PHOTOS_DIR / 'doshik.jpg'),
            caption="Оплата: 1 обнимашка 🤗",
            reply_markup=InlineKeyboardBuilder()
                .button(text="🍽 В меню", callback_data="categories")
                .as_markup()
        )
        
        # Уведомление админу с кнопкой
        if ADMIN_ID:
            builder = InlineKeyboardBuilder()
            builder.add(types.InlineKeyboardButton(
                text="🟢 Сифооооон!",
                callback_data=f"bichis_confirm_{call.from_user.id}_doshik"
            ))
            
            await bot.send_message(
                ADMIN_ID,
                f"🍜 Кто-то хочет дошик!\n",
                reply_markup=builder.as_markup()
            )
            
    except Exception as e:
        logger.error(f"Ошибка в doshik_handler: {e}")
        await call.answer("❌ Дошик разлили...")

class BanquetStates(StatesGroup):
    waiting_for_guests = State()
    waiting_for_level = State()

@dp.callback_query(F.data == "banquet_continue")
async def start_banquet(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer(
        "Чтобы я могла накормить гостей, напиши, пожалуйста, количество гостей:",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(BanquetStates.waiting_for_guests)

@dp.message(BanquetStates.waiting_for_guests)
async def process_guests_count(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите число:")
        return
    
    await state.update_data(guests_count=int(message.text))
    
    # Создаем inline-клавиатуру
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="Можно и по дошику",
            callback_data="banquet_level_doshik"
        ),
        types.InlineKeyboardButton(
            text="Норм по домашнему",
            callback_data="banquet_level_home"
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="Тяжелый люкс",
            callback_data="banquet_level_lux"
        )
    )
    
    await message.answer(
        "Выберите уровень сложности готовки:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(BanquetStates.waiting_for_level)

@dp.callback_query(F.data.startswith("banquet_level_"), BanquetStates.waiting_for_level)
async def process_level(call: types.CallbackQuery, state: FSMContext):
    level_mapping = {
        "banquet_level_doshik": "Можно и по дошику",
        "banquet_level_home": "Норм по домашнему",
        "banquet_level_lux": "Тяжелый люкс"
    }
    
    level = level_mapping.get(call.data)
    if not level:
        await call.answer("Неизвестный уровень сложности")
        return
    
    data = await state.get_data()
    guests_count = data['guests_count']
    
    # Редактируем сообщение с кнопками, убирая их
    await call.message.edit_reply_markup(reply_markup=None)
    
    # Отправляем результат
    await call.message.answer_photo(
        FSInputFile(PHOTOS_DIR / 'banquet.jpg'),
        caption=f"Банкет на {guests_count} гостей!\nУровень: {level}",
        reply_markup=InlineKeyboardBuilder()
            .button(text="🍽 В меню", callback_data="categories")
            .as_markup()
    )
    
    # Уведомление админу
    if ADMIN_ID:
        await bot.send_message(
            ADMIN_ID,
            f"🎉 Ахтунг! Банкет!\n\n"
            f"👥 Гостей: {guests_count}\n"
            f"⚡ Уровень: {level}"
        )
    
    await state.clear()

@dp.callback_query(F.data.startswith('item_'))
async def show_item_details(call: types.CallbackQuery):
    await call.answer()
    try:
        _, cat_id, item_id = call.data.split('_', 2)
        full_item_id = f"item_{item_id}" if not item_id.startswith('item_') else item_id
        
        if cat_id not in menu or full_item_id not in menu[cat_id]:
            await call.answer("❌ Товар не найден", show_alert=True)
            return
            
        item = menu[cat_id][full_item_id]
        
        text = f"""
<b>{item['name']}</b>
<i>{item['desc']}</i>
Цена: {item['price']} 💋
        """
        
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(
                text="➕ Добавить в заказ",
                callback_data=f"add_{cat_id}_{item_id}"
            ),
            types.InlineKeyboardButton(
                text="⬅️ В меню",
                callback_data="categories" 
            )
        )
        
        if item.get('photo'):
            photo_path = PHOTOS_DIR / item['photo']
            if photo_path.exists():
                await call.message.answer_photo(
                    FSInputFile(photo_path),
                    caption=text,
                    reply_markup=builder.as_markup(),
                    parse_mode=ParseMode.HTML
                )
                return
        
        await call.message.answer(
            text,
            reply_markup=builder.as_markup(),
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Ошибка показа товара: {e}")
        await call.answer("❌ Не удалось загрузить информацию о товаре", show_alert=True)

@dp.callback_query(F.data.startswith("add_"))
async def add_to_order(call: types.CallbackQuery):
    try:
        # Разбираем callback_data (формат: "add_категория_item_1753030014")
        parts = call.data.split('_', 3)  # Разбиваем на 3 части
        if len(parts) < 3:
            await call.answer("❌ Ошибка формата запроса", show_alert=True)
            return

        cat_id = parts[1]
        item_id = f"item_{parts[2]}" if len(parts) == 3 else f"{parts[2]}_{parts[3]}"
        
        # Проверяем существование категории
        if cat_id not in menu:
            await call.answer(f"❌ Категория {cat_id} не найдена", show_alert=True)
            return

        # Проверяем существование товара
        if item_id not in menu[cat_id]:
            await call.answer(f"❌ Товар {item_id} не найден в категории {cat_id}", show_alert=True)
            return

        item_data = menu[cat_id][item_id]
        user_id = str(call.from_user.id)

        # Инициализируем заказ
        if user_id not in active_orders:
            active_orders[user_id] = {'items': {}, 'created_at': datetime.now().isoformat()}

        # Добавляем товар
        if item_id not in active_orders[user_id]['items']:
            active_orders[user_id]['items'][item_id] = {
                'name': item_data['name'],
                'price': item_data['price'],
                'count': 1
            }
        else:
            active_orders[user_id]['items'][item_id]['count'] += 1

        save_db(menu, orders, active_orders)
        # await call.answer(f"✅ {item_data['name']} добавлен в заказ!")
        await call.answer(f"✅ {item_data['name']} добавлен в заказ!", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка добавления: {str(e)}", exc_info=True)
        await call.answer("❌ Ошибка сервера", show_alert=True)

@dp.callback_query(F.data == "my_order")
async def show_my_order(call: types.CallbackQuery, state: FSMContext = None):
    user_id = str(call.from_user.id)
    
    if user_id not in active_orders or not active_orders[user_id]['items']:
        await call.message.edit_text("🛒 Ваш заказ пуст!")
        return
    
    order = active_orders[user_id]
    total = 0
    items_text = []
    
    for item_id, item in order['items'].items():
        item_total = item['count'] * item['price']
        total += item_total
        items_text.append(f"▪ {item['name']} ×{item['count']} = {item_total}💋")
    
    text = "🛒 *Ваш заказ:*\n\n" + "\n".join(items_text) + f"\n\n*Итого:* {total}💋"
    
    builder = InlineKeyboardBuilder()
    
    # Основные кнопки
    builder.row(
        types.InlineKeyboardButton(
            text="✏️ Изменить",
            callback_data="edit_order"
        ),
        types.InlineKeyboardButton(
            text="✅ Оформить",
            callback_data="confirm_order"
        )
    )
    
    # Кнопка очистки и возврата
    builder.row(
        types.InlineKeyboardButton(
            text="🗑 Очистить корзину",
            callback_data="clear_cart"
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="⬅️ Назад в меню",
            callback_data="categories"
        )
    )
    
    try:
        await call.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
    except Exception:
        await call.message.answer(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )

@dp.callback_query(F.data == "clear_cart")
async def clear_cart_handler(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    
    if user_id in active_orders:
        # Сохраняем копию для сообщения
        items_count = len(active_orders[user_id]['items'])
        active_orders[user_id]['items'] = {}  # Очищаем корзину
        save_db(menu, orders, active_orders)
        
        await call.answer(f"🗑 Удалено {items_count} позиций!")
        
        # Возвращаем в меню категорий
        await show_categories(call)
    else:
        await call.answer("❌ Корзина уже пуста", show_alert=True)

@dp.callback_query(F.data == "confirm_order")
async def confirm_order_handler(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    
    # Проверяем, есть ли активный заказ
    if user_id not in active_orders or not active_orders[user_id]['items']:
        await call.answer("❌ Ваш заказ пуст!", show_alert=True)
        return
    
    order = active_orders[user_id]
    
    # Формируем текст заказа
    order_text = "🍽 *Ваш заказ:*\n\n"
    total = 0
    
    for item_id, item in order['items'].items():
        item_total = item['count'] * item['price']
        total += item_total
        order_text += f"▪ {item['name']} ×{item['count']} = {item_total} 💋\n"
    
    order_text += f"\n*Итого:* {total} 💋"
    
    # Клавиатура с подтверждением
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data="final_confirm"
        ),
        types.InlineKeyboardButton(
            text="✏️ Изменить",
            callback_data="edit_order"
        )
    )
    
    await call.message.edit_text(
        order_text,
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "final_confirm")
async def final_confirmation(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    
    if user_id not in active_orders:
        await call.answer("❌ Заказ не найден!", show_alert=True)
        return
    
    # Формируем текст заказа
    order = active_orders[user_id]
    order_text = "🍽 *Ваш заказ:*\n\n"
    total = 0
    
    for item_id, item in order['items'].items():
        item_total = item['count'] * item['price']
        total += item_total
        order_text += f"▪ {item['name']} ×{item['count']} = {item_total} 💋\n"
    
    order_text += f"\n*Итого:* {total} 💋"
    order_id = generate_order_id()
    
    # Сохраняем заказ
    orders[order_id] = {
        'user_id': user_id,
        'items': order['items'],
        'created_at': datetime.now().isoformat(),
        'status': 'new'
    }
    active_orders.pop(user_id)
    save_db(menu, orders, active_orders)
    
    # Путь к картинке
    photo_path = PHOTOS_DIR / 'bonapetit.jpg'
    
    # Уведомление пользователю с картинкой
    await call.message.delete()  # Удаляем предыдущее сообщение с кнопками
    await call.message.answer_photo(
        FSInputFile(photo_path),
        caption="💝 *Заказ оформлен!*\n\n" +
               order_text +
               "\n\nШеф-повар уже бежит на кухню...",
        parse_mode="Markdown"
    )
    
    # Уведомление админу с кнопкой
    if ADMIN_ID:
        builder = InlineKeyboardBuilder()
        builder.add(types.InlineKeyboardButton(
            text="✅ Готово",
            callback_data=f"order_done_{order_id}"
        ))
        
        await bot.send_message(
            ADMIN_ID,
            f"📦 *Новый заказ от Любимки*\n" +
            order_text,
            parse_mode="Markdown",
            reply_markup=builder.as_markup()
        )

@dp.callback_query(F.data == "edit_order")
async def edit_order_handler(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    
    if user_id not in active_orders or not active_orders[user_id]['items']:
        await call.answer("❌ Заказ пуст!", show_alert=True)
        return
    
    builder = InlineKeyboardBuilder()
    
    # Формируем кнопки для удаления позиций
    for item_id, item in active_orders[user_id]['items'].items():
        builder.add(types.InlineKeyboardButton(
            text=f"❌ Удалить {item['name']} (×{item['count']})",
            callback_data=f"remove_{item_id}"  # Важно: передаём полный item_id
        ))
    
    builder.adjust(1)
    builder.row(
        types.InlineKeyboardButton(
            text="⬅️ Назад к заказу",
            callback_data="my_order"
        )
    )
    
    await call.message.edit_text(
        "✏️ *Редактирование заказа:*\nВыберите позицию для удаления:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("remove_"))
async def remove_item_handler(call: types.CallbackQuery, state: FSMContext):
    user_id = str(call.from_user.id)
    full_item_id = call.data.split('_', 1)[1]
    
    if user_id not in active_orders:
        await call.answer("❌ Заказ не найден!", show_alert=True)
        return
    
    if full_item_id not in active_orders[user_id]['items']:
        await call.answer("❌ Позиция не найдена в заказе!", show_alert=True)
        return
    
    # Удаляем позицию
    item_name = active_orders[user_id]['items'][full_item_id]['name']
    del active_orders[user_id]['items'][full_item_id]
    save_db(menu, orders, active_orders)
    
    await call.answer(f"❌ {item_name} удалён из заказа!")
    
    # Возвращаемся к просмотру заказа с передачей state
    await show_my_order(call, state)


# ====================== АДМИН ПАНЕЛЬ (без изменений) ======================

async def admin_panel(message: types.Message, state: FSMContext):
    await state.clear()
    kb = [
        [KeyboardButton(text="➕ Добавить позицию")],
        [KeyboardButton(text="🗑 Удалить позицию")]
    ]
    markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("👑 Админ-панель", reply_markup=markup)
    await state.set_state(MenuStates.admin_panel)

@dp.message(F.text == "➕ Добавить позицию", MenuStates.admin_panel)
async def admin_add_item(message: types.Message, state: FSMContext):
    builder = InlineKeyboardBuilder()
    for cat_id, cat_name in CATEGORIES.items():
        if cat_id not in UNEDITABLE_CATEGORIES:
            builder.add(types.InlineKeyboardButton(
                text=cat_name,
                callback_data=f"admin_add_to_{cat_id}"
            ))
    builder.adjust(2)
    await message.answer("Выберите категорию:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("admin_add_to_"))
async def process_add_category(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    try:
        cat_id = call.data.replace("admin_add_to_", "")
        
        if cat_id not in CATEGORIES:
            available = ", ".join(f"'{cat}'" for cat in CATEGORIES.keys())
            await call.message.answer(f"❌ Категория '{cat_id}' не найдена. Доступные: {available}")
            return
        
        await state.update_data(category=cat_id)
        await call.message.answer(
            f"Вы выбрали: {CATEGORIES[cat_id]}\nВведите название позиции:",
        )
        await state.set_state(AdminStates.add_item_name)
        
    except Exception as e:
        logger.error(f"Ошибка выбора категории: {e}")
        await call.message.answer("❌ Произошла ошибка при выборе категории")
        await state.clear()

@dp.message(AdminStates.add_item_name)
async def process_item_name(message: types.Message, state: FSMContext):
    if len(message.text) > 100:
        await message.answer("❌ Слишком длинное название (макс. 100 символов)")
        return
    
    await state.update_data(name=message.text)
    await message.answer("Введите описание позиции:")
    await state.set_state(AdminStates.add_item_desc)

@dp.message(AdminStates.add_item_desc)
async def process_item_desc(message: types.Message, state: FSMContext):
    if len(message.text) > 500:
        await message.answer("❌ Слишком длинное описание (макс. 500 символов)")
        return
    
    await state.update_data(desc=message.text)
    await message.answer("Введите цену позиции (только число):")
    await state.set_state(AdminStates.add_item_price)

@dp.message(AdminStates.add_item_price)
async def process_item_price(message: types.Message, state: FSMContext):
    try:
        price = int(message.text)
        if price <= 0:
            raise ValueError
        await state.update_data(price=price)
        await message.answer(
            "Отправьте фото блюда или нажмите 'Пропустить':",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Пропустить")]],
                resize_keyboard=True
            )
        )
        await state.set_state(AdminStates.add_item_photo)
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректную цену (целое положительное число)")

@dp.message(AdminStates.add_item_photo, F.photo)
async def process_item_photo_with_photo(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        cat_id = data['category']
        item_id = f"item_{int(time.time())}"
        
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        
        ext = file.file_path.split('.')[-1] if '.' in file.file_path else 'jpg'
        photo_name = f"{cat_id}_{item_id}.{ext}"
        photo_path = PHOTOS_DIR / photo_name
        
        await bot.download_file(file.file_path, photo_path)
        
        menu[cat_id][item_id] = {
            'name': data['name'],
            'desc': data['desc'],
            'price': int(data['price']),
            'photo': photo_name
        }
        save_db(menu, orders, active_orders)
        
        await message.answer_photo(
            photo.file_id,
            caption=f"✅ {data['name']} добавлено!\nЦена: {data['price']} 💋",
            reply_markup=ReplyKeyboardRemove()
        )
        await admin_panel(message, state)
        
    except Exception as e:
        logger.error(f"Ошибка обработки фото: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")
        await admin_panel(message, state)

@dp.message(AdminStates.add_item_photo, F.text.casefold() == "пропустить")
async def process_item_photo_without_photo(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        cat_id = data['category']
        item_id = f"item_{int(time.time())}"
        
        menu[cat_id][item_id] = {
            'name': data['name'],
            'desc': data['desc'],
            'price': int(data['price']),
            'photo': None
        }
        save_db(menu, orders, active_orders)
        
        await message.answer(
            f"✅ {data['name']} добавлено без фото!\nЦена: {data['price']} 💋",
            reply_markup=ReplyKeyboardRemove()
        )
        await admin_panel(message, state)
        
    except Exception as e:
        logger.error(f"Ошибка добавления позиции: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")
        await admin_panel(message, state)

@dp.message(F.text == "🗑 Удалить позицию", MenuStates.admin_panel)
async def admin_delete_item(message: types.Message, state: FSMContext):
    try:
        all_items = []
        for cat_id, items in menu.items():
            if cat_id in UNEDITABLE_CATEGORIES:
                continue
            for item_id, item in items.items():
                all_items.append((cat_id, item_id, item['name']))
        
        if not all_items:
            await message.answer("ℹ️ Нет позиций для удаления")
            return
        
        builder = InlineKeyboardBuilder()
        for cat_id, item_id, item_name in all_items:
            builder.add(types.InlineKeyboardButton(
                text=f"{CATEGORIES[cat_id]}: {item_name}",
                callback_data=f"delete_item_{cat_id}_{item_id}"
            ))
        builder.adjust(1)
        
        await message.answer(
            "Выберите позицию для удаления:",
            reply_markup=builder.as_markup()
        )
        await state.set_state(AdminStates.delete_item)
    
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")
        await admin_panel(message, state)

@dp.callback_query(F.data.startswith("delete_item_"), AdminStates.delete_item)
async def process_delete_item(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    try:
        parts = call.data.split('_')
        if len(parts) < 4:
            raise ValueError("Неверный формат callback_data")
            
        cat_id = parts[2]
        item_id = '_'.join(parts[3:])
        
        if cat_id not in menu or item_id not in menu[cat_id]:
            await call.answer("❌ Позиция не найдена")
            return
            
        item_name = menu[cat_id][item_id]['name']
        
        if menu[cat_id][item_id].get('photo'):
            photo_path = PHOTOS_DIR / menu[cat_id][item_id]['photo']
            try:
                if photo_path.exists():
                    photo_path.unlink()
            except Exception as e:
                logger.error(f"Ошибка удаления фото: {e}")
        
        del menu[cat_id][item_id]
        save_db(menu, orders, active_orders)
        
        await call.message.answer(f"✅ Позиция '{item_name}' удалена")
        await admin_panel(call.message, state)
        
    except Exception as e:
        logger.error(f"Ошибка удаления: {e}")
        await call.message.answer(f"❌ Ошибка: {str(e)}")
        await admin_panel(call.message, state)

@dp.message(F.text == "❌ Отмена", StateFilter("*"))
async def cancel_handler(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id == ADMIN_ID:
        await admin_panel(message, state)
    else:
        await show_user_menu(message)

@dp.callback_query(F.data.startswith("order_done_"))
async def mark_order_done(call: types.CallbackQuery):
    order_id = call.data.split('_')[2]
    
    if order_id not in orders:
        await call.answer("❌ Заказ не найден!", show_alert=True)
        return
    
    # Обновляем статус заказа
    orders[order_id]['status'] = 'done'
    orders[order_id]['completed_at'] = datetime.now().isoformat()
    save_db(menu, orders, active_orders)
    
    # Уведомляем пользователя
    user_id = orders[order_id]['user_id']
    order_items = orders[order_id]['items']
    
    items_text = "\n".join(
        f"▪ {item['name']} ×{item['count']}" 
        for item in order_items.values()
    )
    
    try:
        await bot.send_message(
            user_id,
            f"🎉 *Ваш заказ готов!*\n\n" +
            items_text +
            "\n\nПриятного аппетита! 💋",
            parse_mode="Markdown"
        )
        await call.answer("✅ Пользователь уведомлён")
    except Exception as e:
        await call.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
    
    # Обновляем сообщение админу
    await call.message.edit_text(
        f"✅ Заказ выполнен\n" +
        call.message.text,
        parse_mode="Markdown"
    )

# Обработчик кнопки "Погнали" у админа
@dp.callback_query(F.data.startswith("outdoor_confirm_"))
async def outdoor_confirmation(call: types.CallbackQuery):
    await call.answer()
    user_id = int(call.data.split('_')[2])
    
    try:
        # Отправляем уведомление пользователю
        await bot.send_message(
            user_id,
            "🎉 Шеф-повар подтвердил - погнали по ресторанам! 🚗💨"
        )
        
        # Обновляем сообщение админу
        await call.message.edit_text(
            f"✅ Вы подтвердили поход по ресторанам с пользователем\n"
            f"{call.message.text}",
            reply_markup=None
        )
    except Exception as e:
        logger.error(f"Ошибка подтверждения похода по ресторанам: {e}")
        await call.answer("❌ Не удалось отправить подтверждение")

@dp.callback_query(F.data.startswith("delivery_confirm_"))
async def confirm_delivery(call: types.CallbackQuery):
    try:
        await call.answer()
        user_id = int(call.data.split('_')[2])
        
        # Отправляем уведомление пользователю
        await bot.send_message(
            user_id,
            "🚀 Ура, не готовить!"
        )
        
        # Редактируем сообщение админа
        await call.message.edit_text(
            f"✅ Подтверждено: {call.message.text}",
            reply_markup=None
        )
        
    except Exception as e:
        logger.error(f"Ошибка подтверждения доставки: {e}")
        await call.answer("❌ Не удалось отправить подтверждение", show_alert=True)

# Обработчик кнопки подтверждения
@dp.callback_query(F.data.startswith("compote_confirm_"))
async def confirm_compote(call: types.CallbackQuery):
    try:
        await call.answer()
        user_id = int(call.data.split('_')[2])
        
        # Отправляем уведомление пользователю
        await bot.send_message(
            user_id,
            "🍾 Го квасить! 🍻"
        )
        
        # Обновляем сообщение админа
        await call.message.edit_text(
            f"✅ Подтверждено: {call.message.text}\n"
            f"Ответ отправлен пользователю",
            reply_markup=None
        )
        
    except Exception as e:
        logger.error(f"Ошибка подтверждения: {e}")
        await call.answer("❌ Не удалось отправить подтверждение", show_alert=True)

# Общий обработчик подтверждения для бичи-меню
@dp.callback_query(F.data.startswith("bichis_confirm_"))
async def confirm_bichis(call: types.CallbackQuery):
    try:
        await call.answer()
        _, _, user_id, item_type = call.data.split('_')
        user_id = int(user_id)
        
        # Отправляем уведомление пользователю
        await bot.send_message(
            user_id,
            "🚀 Сифоооон! " + ("Шавуха уже в пути!" if item_type == "shawarma" else "Дошик замачивается!")
        )
        
        # Обновляем сообщение админа
        await call.message.edit_text(
            f"✅ Подтверждено: {call.message.text}\n"
            f"Тип: {'Шаурма' if item_type == 'shawarma' else 'Дошик'}",
            reply_markup=None
        )
        
    except Exception as e:
        logger.error(f"Ошибка подтверждения: {e}")
        await call.answer("❌ Не удалось отправить подтверждение", show_alert=True)

# ====================== ЗАПУСК БОТА ======================

async def on_startup(bot: Bot):
    init_folders()
    await bot.send_message(ADMIN_ID, "🤖 Бот запущен!")

if __name__ == '__main__':
    dp.startup.register(on_startup)
    dp.run_polling(bot)