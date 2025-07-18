import os
import json
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton
from aiogram.enums import ParseMode
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройки бота
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Инициализация папки данных
def init_data_folder():
    os.makedirs('data/photos', exist_ok=True)
    for file in ['menu.json', 'orders.json', 'active_orders.json']:
        if not os.path.exists(f'data/{file}'):
            with open(f'data/{file}', 'w') as f:
                json.dump({}, f)

# Состояния
class MenuStates(StatesGroup):
    main_menu = State()
    view_item = State()
    my_order = State()
    edit_order = State()
    admin_panel = State()

class AdminStates(StatesGroup):
    add_item_name = State()
    add_item_desc = State()
    add_item_price = State()
    add_item_time = State()
    add_item_photo = State()
    edit_item_select = State()
    edit_item_field = State()
    edit_item_value = State()

# Загрузка данных
def load_db():
    init_data_folder()
    try:
        with open('data/menu.json', 'r') as f:
            menu = json.load(f)
    except:
        menu = {}
    
    try:
        with open('data/orders.json', 'r') as f:
            orders = json.load(f)
    except:
        orders = {}
    
    try:
        with open('data/active_orders.json', 'r') as f:
            active_orders = json.load(f)
    except:
        active_orders = {}
    
    return menu, orders, active_orders

# Сохранение данных
def save_db(menu, orders, active_orders):
    init_data_folder()
    with open('data/menu.json', 'w') as f:
        json.dump(menu, f)
    with open('data/orders.json', 'w') as f:
        json.dump(orders, f)
    with open('data/active_orders.json', 'w') as f:
        json.dump(active_orders, f)

menu, orders, active_orders = load_db()

# Функция для удаления сообщения с эффектом
async def delete_with_effect(message: types.Message, delay: float = 0.5):
    try:
        await asyncio.sleep(delay)
        await message.delete()
    except:
        pass

# Хэндлеры для пользователей
@dp.message(F.text == '/start')
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    
    welcome_text = (
        "🍕 Добро пожаловать в наше шуточное кафе 'Любимка'! 🐾\n\n"
        "Здесь вы можете заказать самые необычные блюда за условные единицы хорошего настроения!\n"
        "Нажмите кнопку 'Меню' ниже, чтобы начать."
    )
    
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text="🍽 Меню",
        callback_data="menu"
    ))
    
    msg = await message.answer(welcome_text, reply_markup=builder.as_markup())
    asyncio.create_task(delete_with_effect(msg, 10))

@dp.callback_query(F.data == "menu")
async def show_menu(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    try:
        await call.message.delete()
    except:
        pass
    
    if not menu:
        msg = await call.message.answer("Меню пока пустое. Администратор скоро его заполнит!")
        asyncio.create_task(delete_with_effect(msg, 5))
        return
    
    builder = InlineKeyboardBuilder()
    for item_id, item in menu.items():
        builder.add(types.InlineKeyboardButton(
            text=item['name'],
            callback_data=f"item_{item_id}"
        ))
    builder.adjust(2)
    
    builder.row(types.InlineKeyboardButton(
        text="🛒 Мой заказ",
        callback_data="my_order"
    ))
    
    await call.message.answer("🍽 Наше меню:", reply_markup=builder.as_markup())
    await state.set_state(MenuStates.main_menu)

@dp.callback_query(F.data.startswith('item_'))
async def show_item(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    try:
        await call.message.delete()
    except:
        pass
    
    item_id = call.data.split('_')[1]
    item = menu[item_id]
    
    text = (
        f"🍽 <b>{item['name']}</b>\n\n"
        f"{item['desc']}\n\n"
        f"⏳ Время приготовления: {item['time']}\n"
        f"💰 Стоимость: {item['price']} условных единиц"
    )
    
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text="➕ Добавить в заказ",
        callback_data=f"add_{item_id}"
    ))
    builder.row(
        types.InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="menu"
        ),
        types.InlineKeyboardButton(
            text="🛒 Мой заказ",
            callback_data="my_order"
        )
    )
    
    photo = FSInputFile(item['photo'])
    await call.message.answer_photo(
        photo,
        caption=text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )
    
    await state.set_state(MenuStates.view_item)
    await state.update_data(current_item=item_id)

@dp.callback_query(F.data.startswith('add_'))
async def add_to_order(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    
    item_id = call.data.split('_')[1]
    user_id = call.from_user.id
    item = menu[item_id]
    
    if str(user_id) not in orders:
        orders[str(user_id)] = []
    
    orders[str(user_id)].append({
        'id': item_id,
        'name': item['name'],
        'price': item['price']
    })
    save_db(menu, orders, active_orders)
    
    msg = await call.message.answer(f"✅ {item['name']} добавлен в ваш заказ!")
    asyncio.create_task(delete_with_effect(msg, 3))

@dp.callback_query(F.data == "my_order")
async def show_order(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    try:
        await call.message.delete()
    except:
        pass
    
    user_id = call.from_user.id
    order = orders.get(str(user_id), [])
    
    if not order:
        builder = InlineKeyboardBuilder()
        builder.add(types.InlineKeyboardButton(
            text="🍽 Меню",
            callback_data="menu"
        ))
        msg = await call.message.answer("Ваш заказ пуст.", reply_markup=builder.as_markup())
        asyncio.create_task(delete_with_effect(msg, 5))
        await state.set_state(MenuStates.main_menu)
        return
    
    order_text = "🛒 Ваш заказ:\n\n"
    for idx, item in enumerate(order, 1):
        order_text += f"{idx}. {item['name']} - {item['price']} усл. ед.\n"
    
    total = sum(item['price'] for item in order)
    order_text += f"\n💵 Итого: {total} условных единиц"
    
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="menu"
        ),
        types.InlineKeyboardButton(
            text="✏️ Редактировать",
            callback_data="edit_order"
        )
    )
    builder.add(types.InlineKeyboardButton(
        text="✅ Оформить заказ",
        callback_data="place_order"
    ))
    
    await call.message.answer(order_text, reply_markup=builder.as_markup())
    await state.set_state(MenuStates.my_order)

@dp.callback_query(F.data == "edit_order")
async def edit_order(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    try:
        await call.message.delete()
    except:
        pass
    
    user_id = call.from_user.id
    order = orders.get(str(user_id), [])
    
    if not order:
        msg = await call.message.answer("Ваш заказ пуст.")
        asyncio.create_task(delete_with_effect(msg, 3))
        await state.set_state(MenuStates.main_menu)
        return
    
    order_text = "✏️ Редактирование заказа:\n\n"
    for idx, item in enumerate(order, 1):
        order_text += f"{idx}. {item['name']} - {item['price']} усл. ед.\n"
    
    builder = InlineKeyboardBuilder()
    for idx, item in enumerate(order, 1):
        builder.add(types.InlineKeyboardButton(
            text=f"❌ Удалить {item['name']}",
            callback_data=f"remove_{idx-1}"
        ))
    
    builder.row(types.InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data="my_order"
    ))
    
    await call.message.answer(order_text, reply_markup=builder.as_markup())
    await state.set_state(MenuStates.edit_order)

@dp.callback_query(F.data.startswith('remove_'))
async def remove_from_order(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    
    item_idx = int(call.data.split('_')[1])
    user_id = call.from_user.id
    
    if str(user_id) in orders and 0 <= item_idx < len(orders[str(user_id)]):
        removed_item = orders[str(user_id)].pop(item_idx)
        save_db(menu, orders, active_orders)
        msg = await call.message.answer(f"❌ {removed_item['name']} удален из заказа.")
        asyncio.create_task(delete_with_effect(msg, 3))
    
    if not orders.get(str(user_id), []):
        msg = await call.message.answer("Ваш заказ теперь пуст.")
        asyncio.create_task(delete_with_effect(msg, 3))
        await state.set_state(MenuStates.main_menu)
        return
    
    await edit_order(call, state)

@dp.callback_query(F.data == "place_order")
async def place_order(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    try:
        await call.message.delete()
    except:
        pass
    
    user_id = call.from_user.id
    order = orders.get(str(user_id), [])
    
    if not order:
        msg = await call.message.answer("Ваш заказ пуст!")
        asyncio.create_task(delete_with_effect(msg, 3))
        return
    
    total = sum(item['price'] for item in order)
    
    # Генерируем ID заказа
    order_id = str(max([int(k) for k in active_orders.keys()] + [0]) + 1) if active_orders else "1"
    
    # Сохраняем заказ в активных
    active_orders[order_id] = {
        'user_id': user_id,
        'username': call.from_user.username or call.from_user.full_name,
        'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'total': total,
        'items': order.copy()
    }
    
    orders[str(user_id)] = []
    save_db(menu, orders, active_orders)
    
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text="🍽 Меню",
        callback_data="menu"
    ))
    
    msg = await call.message.answer(
        f"🎉 Ваш заказ #{order_id} оформлен! Итого: {total} условных единиц.\n"
        "Спасибо за заказ! Мы уведомим вас о готовности.",
        reply_markup=builder.as_markup()
    )
    asyncio.create_task(delete_with_effect(msg, 10))
    
    # Уведомление админа
    order_text = f"📦 Новый заказ #{order_id} от @{call.from_user.username or call.from_user.full_name}:\n\n"
    for item in order:
        order_text += f"- {item['name']} ({item['price']} усл. ед.)\n"
    order_text += f"\n💵 Итого: {total} условных единиц\n"
    order_text += f"\nНапишите 'Готово {order_id}', когда заказ будет готов"
    
    await bot.send_message(ADMIN_ID, order_text)
    
    await state.set_state(MenuStates.main_menu)

# Админ-панель
@dp.message(F.text == '/admin')
async def admin_panel(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        msg = await message.answer("У вас нет прав администратора.")
        asyncio.create_task(delete_with_effect(msg, 3))
        return
    
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="➕ Добавить позицию"))
    builder.add(KeyboardButton(text="✏️ Редактировать позицию"))
    builder.add(KeyboardButton(text="📊 Активные заказы"))
    builder.adjust(2)
    
    await message.answer(
        "Админ-панель:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )
    await state.set_state(MenuStates.admin_panel)

@dp.message(F.text == "➕ Добавить позицию", MenuStates.admin_panel)
async def admin_add_item(message: types.Message, state: FSMContext):
    await message.answer("Введите название новой позиции:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(AdminStates.add_item_name)

@dp.message(AdminStates.add_item_name)
async def process_item_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите описание позиции:")
    await state.set_state(AdminStates.add_item_desc)

@dp.message(AdminStates.add_item_desc)
async def process_item_desc(message: types.Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await message.answer("Введите стоимость позиции (в условных единицах):")
    await state.set_state(AdminStates.add_item_price)

@dp.message(AdminStates.add_item_price)
async def process_item_price(message: types.Message, state: FSMContext):
    try:
        price = int(message.text)
        await state.update_data(price=price)
        await message.answer("Введите время приготовления (например, '10-15 минут'):")
        await state.set_state(AdminStates.add_item_time)
    except ValueError:
        msg = await message.answer("Пожалуйста, введите число:")
        asyncio.create_task(delete_with_effect(msg, 3))

@dp.message(AdminStates.add_item_time)
async def process_item_time(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text)
    await message.answer("Отправьте фото для позиции:")
    await state.set_state(AdminStates.add_item_photo)

@dp.message(AdminStates.add_item_photo, F.photo)
async def process_item_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    data = await state.get_data()
    
    # Сохраняем фото
    item_id = str(len(menu) + 1)
    photo_path = f"data/photos/menu_{item_id}.jpg"
    await bot.download(photo, destination=photo_path)
    
    # Добавляем позицию в меню
    menu[item_id] = {
        'name': data['name'],
        'desc': data['desc'],
        'price': data['price'],
        'time': data['time'],
        'photo': photo_path
    }
    save_db(menu, orders, active_orders)
    
    msg = await message.answer(
        f"Позиция '{data['name']}' успешно добавлена в меню!",
        reply_markup=types.ReplyKeyboardRemove()
    )
    asyncio.create_task(delete_with_effect(msg, 5))
    await state.clear()
    await admin_panel(message, state)

@dp.message(F.text == "✏️ Редактировать позицию", MenuStates.admin_panel)
async def admin_edit_item(message: types.Message, state: FSMContext):
    if not menu:
        msg = await message.answer("Меню пустое, нечего редактировать.", reply_markup=types.ReplyKeyboardRemove())
        asyncio.create_task(delete_with_effect(msg, 3))
        return
    
    builder = InlineKeyboardBuilder()
    for item_id, item in menu.items():
        builder.add(types.InlineKeyboardButton(
            text=item['name'],
            callback_data=f"admin_edit_{item_id}"
        ))
    
    await message.answer(
        "Выберите позицию для редактирования:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(AdminStates.edit_item_select)

@dp.callback_query(F.data.startswith('admin_edit_'), AdminStates.edit_item_select)
async def admin_edit_item_select(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    try:
        await call.message.delete()
    except:
        pass
    
    item_id = call.data.split('_')[2]
    item = menu[item_id]
    
    await state.update_data(edit_item_id=item_id)
    
    text = (
        f"Редактирование: {item['name']}\n\n"
        f"1. Название: {item['name']}\n"
        f"2. Описание: {item['desc']}\n"
        f"3. Цена: {item['price']}\n"
        f"4. Время приготовления: {item['time']}\n"
        f"5. Фото: {item['photo']}\n\n"
        "Введите номер поля для редактирования:"
    )
    
    await call.message.answer(text, reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(AdminStates.edit_item_field)

@dp.message(AdminStates.edit_item_field)
async def admin_edit_item_field(message: types.Message, state: FSMContext):
    try:
        field_num = int(message.text)
        if 1 <= field_num <= 5:
            fields = ['name', 'desc', 'price', 'time', 'photo']
            await state.update_data(edit_field=fields[field_num-1])
            
            if field_num == 5:
                await message.answer("Отправьте новое фото:")
            else:
                await message.answer(f"Введите новое значение для {fields[field_num-1]}:")
            
            await state.set_state(AdminStates.edit_item_value)
        else:
            msg = await message.answer("Пожалуйста, введите число от 1 до 5:")
            asyncio.create_task(delete_with_effect(msg, 3))
    except ValueError:
        msg = await message.answer("Пожалуйста, введите число:")
        asyncio.create_task(delete_with_effect(msg, 3))

@dp.message(AdminStates.edit_item_value)
async def admin_edit_item_value(message: types.Message, state: FSMContext):
    data = await state.get_data()
    item_id = data['edit_item_id']
    field = data['edit_field']
    
    if field == 'photo' and message.photo:
        photo = message.photo[-1]
        photo_path = f"data/photos/menu_{item_id}.jpg"
        await bot.download(photo, destination=photo_path)
        menu[item_id]['photo'] = photo_path
    elif field != 'photo' and message.text:
        if field == 'price':
            try:
                menu[item_id][field] = int(message.text)
            except ValueError:
                msg = await message.answer("Пожалуйста, введите число:")
                asyncio.create_task(delete_with_effect(msg, 3))
                return
        else:
            menu[item_id][field] = message.text
    
    save_db(menu, orders, active_orders)
    msg = await message.answer("Изменения сохранены!")
    asyncio.create_task(delete_with_effect(msg, 3))
    await state.clear()
    await admin_panel(message, state)

@dp.message(F.text == "📊 Активные заказы", MenuStates.admin_panel)
async def show_active_orders(message: types.Message):
    if not active_orders:
        msg = await message.answer("Нет активных заказов", reply_markup=types.ReplyKeyboardRemove())
        asyncio.create_task(delete_with_effect(msg, 3))
        return
    
    text = "📊 Активные заказы:\n\n"
    for order_id, order_data in active_orders.items():
        text += f"🔹 Заказ #{order_id}\n"
        text += f"👤 Пользователь: @{order_data['username']}\n"
        text += f"📅 Время заказа: {order_data['time']}\n"
        text += f"💵 Сумма: {order_data['total']} усл. ед.\n"
        text += "🍽 Состав:\n"
        for item in order_data['items']:
            text += f"- {item['name']} ({item['price']} усл. ед.)\n"
        text += "\n"
    
    await message.answer(text, reply_markup=types.ReplyKeyboardRemove())

@dp.message(F.text.startswith("Готово "), MenuStates.admin_panel)
async def order_ready(message: types.Message):
    try:
        order_id = message.text.split()[1]
        if order_id in active_orders:
            user_id = active_orders[order_id]['user_id']
            await bot.send_message(
                user_id,
                f"🎉 Ваш заказ #{order_id} готов! Приятного аппетита! 😊"
            )
            
            msg = await message.answer(f"Уведомление отправлено для заказа #{order_id}")
            asyncio.create_task(delete_with_effect(msg, 3))
            
            del active_orders[order_id]
            save_db(menu, orders, active_orders)
        else:
            msg = await message.answer("Заказ не найден")
            asyncio.create_task(delete_with_effect(msg, 3))
    except Exception as e:
        msg = await message.answer(f"Ошибка: {str(e)}")
        asyncio.create_task(delete_with_effect(msg, 3))

# Запуск бота
async def on_startup(bot: Bot):
    init_data_folder()
    try:
        await bot.send_message(ADMIN_ID, "🤖 Бот запущен и готов к работе!")
    except Exception as e:
        print(f"Не удалось отправить сообщение администратору: {e}")

if __name__ == '__main__':
    dp.startup.register(on_startup)
    dp.run_polling(bot)