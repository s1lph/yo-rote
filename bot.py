"""
yo.route - Advanced Telegram Bot для водителей
Полноценное рабочее место водителя с функциями:
- Интерактивные статусы заказов
- Умная навигация (Deep Links)
- Фото-отчеты (Proof of Delivery)
- Live-трекинг курьера
- Тревожная кнопка

Использование aiogram 3.x
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Optional
from urllib.parse import quote

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    Message, 
    CallbackQuery,
    ReplyKeyboardMarkup, 
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ContentType
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Загрузка переменных окружения
load_dotenv()

# Получение токена бота
BOT_TOKEN = os.getenv('TG_BOT_TOKEN')

# ID администратора для тревожных уведомлений (замените на реальный ID)
ADMIN_ID = os.getenv('TG_ADMIN_ID', '123456789')

# Путь для сохранения фото подтверждений
PROOFS_DIR = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'proofs')

if not BOT_TOKEN:
    print("❌ Ошибка: переменная окружения TG_BOT_TOKEN не установлена!")
    print("   Добавьте TG_BOT_TOKEN=your_token в файл .env")
    sys.exit(1)

# Добавляем путь к проекту для импорта Flask моделей
sys.path.insert(0, os.path.dirname(__file__))

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# ============================================================================
# FSM States
# ============================================================================

class DeliveryStates(StatesGroup):
    """Состояния для процесса доставки"""
    waiting_photo_proof = State()    # Ожидание фото подтверждения
    waiting_failure_reason = State() # Ожидание причины отказа


# ============================================================================
# Helper Functions
# ============================================================================

def get_flask_app():
    """Получение Flask-приложения для работы с контекстом БД"""
    from app import app
    return app


def get_courier_by_chat_id(chat_id: str):
    """Получение курьера по chat_id"""
    app = get_flask_app()
    with app.app_context():
        from models import Courier
        return Courier.query.filter_by(telegram_chat_id=str(chat_id)).first()


def ensure_proofs_dir():
    """Создание директории для фото если не существует"""
    if not os.path.exists(PROOFS_DIR):
        os.makedirs(PROOFS_DIR)


def sanitize_filename(name: str) -> str:
    """
    Очистка строки для использования в имени файла.
    Заменяет недопустимые символы на дефис.
    """
    import re
    # Заменяем недопустимые символы файловой системы на дефис
    safe_name = re.sub(r'[\\/*?"<>|:]+', '-', name)
    # Удаляем пробелы по краям и заменяем множественные пробелы
    safe_name = re.sub(r'\s+', '_', safe_name.strip())
    # Ограничиваем длину
    return safe_name[:50] if len(safe_name) > 50 else safe_name


def check_and_complete_route(route_id: int) -> bool:
    """
    Проверяет, все ли заказы в маршруте завершены (completed или failed).
    Если да, помечает маршрут как completed.
    
    Returns:
        True если маршрут был завершён, False иначе
    """
    app = get_flask_app()
    with app.app_context():
        from models import db, Route, Order
        
        route = Route.query.get(route_id)
        if not route or route.status != 'active':
            return False
        
        # Получаем все заказы маршрута
        orders = Order.query.filter_by(route_id=route_id).all()
        if not orders:
            return False
        
        # Проверяем, все ли заказы завершены
        all_done = all(o.status in ['completed', 'failed'] for o in orders)
        
        if all_done:
            route.status = 'completed'
            db.session.commit()
            print(f"[INFO] Маршрут #{route_id} автоматически завершён - все заказы выполнены")
            return True
        
        return False


# ============================================================================
# Keyboard Generators
# ============================================================================

def get_main_menu_keyboard(is_on_shift: bool = False) -> ReplyKeyboardMarkup:
    """
    Главное меню бота (Reply Keyboard).
    
    Args:
        is_on_shift: Находится ли курьер на смене
    
    Returns:
        ReplyKeyboardMarkup с кнопками меню
    """
    shift_button = "🏁 Закончил смену" if is_on_shift else "📍 Начал смену"
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=shift_button)],
            [KeyboardButton(text="📋 Мои заказы"), KeyboardButton(text="🆘 Проблема")]
        ],
        resize_keyboard=True,
        is_persistent=True
    )
    return keyboard


def generate_order_keyboard(
    order_id: int, 
    lat: Optional[float] = None, 
    lon: Optional[float] = None, 
    phone: Optional[str] = None,
    address: Optional[str] = None
) -> InlineKeyboardMarkup:
    """
    Генерация Inline-клавиатуры для заказа.
    
    Args:
        order_id: ID заказа
        lat: Широта точки доставки
        lon: Долгота точки доставки
        phone: Телефон получателя
        address: Адрес доставки (для навигации если нет координат)
    
    Returns:
        InlineKeyboardMarkup с кнопками действий
    """
    buttons = []
    
    # Первый ряд: Доставлен / Отказ
    buttons.append([
        InlineKeyboardButton(text="✅ Доставлен", callback_data=f"delivered:{order_id}"),
        InlineKeyboardButton(text="❌ Отказ", callback_data=f"failed:{order_id}")
    ])
    
    # Второй ряд: Навигация
    row2 = []
    
    # Кнопка навигации
    if lat and lon:
        # Используем Яндекс карты как универсальный вариант (работает и в браузере)
        yandex_maps_url = f"https://yandex.ru/maps/?rtext=~{lat},{lon}&rtt=auto"
        row2.append(InlineKeyboardButton(text="🗺 Навигатор", url=yandex_maps_url))
    elif address:
        # Если нет координат, используем адрес
        encoded_address = quote(address)
        yandex_maps_url = f"https://yandex.ru/maps/?text={encoded_address}&rtt=auto"
        row2.append(InlineKeyboardButton(text="🗺 Карта", url=yandex_maps_url))
    
    # Примечание: Telegram не поддерживает tel: URLs в inline кнопках
    # Телефон показывается в тексте сообщения
    
    if row2:
        buttons.append(row2)
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def generate_cancel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой отмены"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")]
    ])


# ============================================================================
# Command Handlers
# ============================================================================

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    # Проверяем, привязан ли уже аккаунт
    app = get_flask_app()
    with app.app_context():
        from models import Courier
        courier = Courier.query.filter_by(telegram_chat_id=str(message.chat.id)).first()
        
        if courier:
            # Курьер уже привязан
            await message.answer(
                f"👋 *С возвращением, {courier.full_name}!*\n\n"
                f"Вы готовы к работе. Используйте меню ниже для управления.",
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard(courier.is_on_shift)
            )
        else:
            # Новый пользователь
            welcome_text = """
👋 *Добро пожаловать в yo.route Bot!*

Этот бот предназначен для водителей и курьеров.

🔐 *Для привязки аккаунта:*
Введите 6-значный код, который вы получили от диспетчера или видите в личном кабинете.

_Пример кода: ABC123_
"""
            await message.answer(welcome_text, parse_mode="Markdown")


@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    """Показать главное меню"""
    app = get_flask_app()
    with app.app_context():
        from models import Courier
        courier = Courier.query.filter_by(telegram_chat_id=str(message.chat.id)).first()
        
        if courier:
            await message.answer(
                "📱 *Главное меню*",
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard(courier.is_on_shift)
            )
        else:
            await message.answer(
                "❌ Вы не авторизованы. Введите код авторизации.",
                parse_mode="Markdown"
            )


# ============================================================================
# Shift Management (Начало/Конец смены)
# ============================================================================

@dp.message(F.text == "📍 Начал смену")
async def start_shift(message: Message):
    """Начало смены - запрос Live Location"""
    app = get_flask_app()
    with app.app_context():
        from models import db, Courier
        courier = Courier.query.filter_by(telegram_chat_id=str(message.chat.id)).first()
        
        if not courier:
            await message.answer("❌ Вы не авторизованы в системе.")
            return
        
        courier.is_on_shift = True
        db.session.commit()
        
        await message.answer(
            "🟢 *Смена начата!*\n\n"
            "Для отслеживания вашего местоположения, пожалуйста, отправьте *трансляцию геопозиции*:\n\n"
            "📎 Скрепка → 📍 Геопозиция → *Транслировать* (выберите время)\n\n"
            "_Это позволит диспетчеру видеть ваше местоположение в реальном времени._",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(is_on_shift=True)
        )


@dp.message(F.text == "🏁 Закончил смену")
async def end_shift(message: Message):
    """Конец смены"""
    app = get_flask_app()
    with app.app_context():
        from models import db, Courier
        courier = Courier.query.filter_by(telegram_chat_id=str(message.chat.id)).first()
        
        if not courier:
            await message.answer("❌ Вы не авторизованы в системе.")
            return
        
        courier.is_on_shift = False
        courier.current_lat = None
        courier.current_lon = None
        db.session.commit()
        
        await message.answer(
            "🔴 *Смена завершена!*\n\n"
            "Спасибо за работу! Отдыхайте 🍵",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(is_on_shift=False)
        )


# ============================================================================
# Live Location Tracking
# ============================================================================

@dp.message(F.location)
async def handle_location(message: Message):
    """Обработка геолокации (обычной и Live Location)"""
    app = get_flask_app()
    with app.app_context():
        from models import db, Courier
        courier = Courier.query.filter_by(telegram_chat_id=str(message.chat.id)).first()
        
        if not courier:
            await message.answer("❌ Вы не авторизованы в системе.")
            return
        
        # Обновляем координаты
        courier.current_lat = message.location.latitude
        courier.current_lon = message.location.longitude
        db.session.commit()
        
        # Если это Live Location (есть live_period), подтверждаем один раз
        if message.location.live_period:
            await message.answer(
                f"📍 *Трансляция геопозиции активна*\n\n"
                f"Ваше местоположение обновляется автоматически.\n"
                f"Координаты: `{message.location.latitude:.6f}, {message.location.longitude:.6f}`",
                parse_mode="Markdown"
            )


@dp.edited_message(F.location)
async def handle_location_update(message: Message):
    """Обработка обновления Live Location"""
    app = get_flask_app()
    with app.app_context():
        from models import db, Courier
        courier = Courier.query.filter_by(telegram_chat_id=str(message.chat.id)).first()
        
        if courier:
            courier.current_lat = message.location.latitude
            courier.current_lon = message.location.longitude
            db.session.commit()
            # Не отправляем сообщение при каждом обновлении чтобы не спамить


# ============================================================================
# Emergency Button (Тревожная кнопка)
# ============================================================================

@dp.message(F.text == "🆘 Проблема")
async def emergency_button(message: Message):
    """Тревожная кнопка - уведомление администратору"""
    app = get_flask_app()
    with app.app_context():
        from models import Courier
        courier = Courier.query.filter_by(telegram_chat_id=str(message.chat.id)).first()
        
        if not courier:
            await message.answer("❌ Вы не авторизованы в системе.")
            return
        
        # Формируем сообщение для администратора
        location_info = ""
        if courier.current_lat and courier.current_lon:
            maps_link = f"https://yandex.ru/maps/?pt={courier.current_lon},{courier.current_lat}&z=17"
            location_info = f"\n📍 [Местоположение]({maps_link})"
        
        admin_message = (
            f"🆘 *ТРЕВОГА! Водитель сообщает о проблеме!*\n\n"
            f"👤 *Курьер:* {courier.full_name}\n"
            f"📞 *Телефон:* {courier.phone or 'не указан'}\n"
            f"🚗 *Транспорт:* {courier.vehicle_type}"
            f"{location_info}\n\n"
            f"⏰ Время: {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}"
        )
        
        try:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_message,
                parse_mode="Markdown"
            )
            await message.answer(
                "✅ *Сообщение отправлено диспетчеру!*\n\n"
                "Ожидайте, с вами свяжутся в ближайшее время.",
                parse_mode="Markdown"
            )
        except Exception as e:
            await message.answer(
                "⚠️ Не удалось отправить сообщение диспетчеру.\n"
                "Пожалуйста, позвоните по телефону поддержки.",
                parse_mode="Markdown"
            )


# ============================================================================
# My Orders
# ============================================================================

@dp.message(F.text == "📋 Мои заказы")
async def my_orders(message: Message):
    """Показать активные заказы курьера"""
    print(f"[DEBUG] my_orders handler triggered by chat_id: {message.chat.id}")
    
    app = get_flask_app()
    with app.app_context():
        from models import Courier, Route, Order
        courier = Courier.query.filter_by(telegram_chat_id=str(message.chat.id)).first()
        
        if not courier:
            print(f"[DEBUG] Courier not found for chat_id: {message.chat.id}")
            await message.answer("❌ Вы не авторизованы в системе.")
            return
        
        print(f"[DEBUG] Found courier: {courier.full_name} (id={courier.id})")
        
        # Получаем активные маршруты
        active_routes = Route.query.filter_by(
            courier_id=courier.id, 
            status='active'
        ).all()
        
        print(f"[DEBUG] Active routes count: {len(active_routes)}")
        
        if not active_routes:
            await message.answer(
                "📭 *У вас нет активных заказов*\n\n"
                "Ожидайте назначения маршрута от диспетчера.",
                parse_mode="Markdown"
            )
            return
        
        for route in active_routes:
            orders = Order.query.filter_by(route_id=route.id).order_by(Order.route_position).all()
            
            print(f"[DEBUG] Route {route.id}: {len(orders)} orders")
            
            if not orders:
                continue
            
            # Отправляем информацию о маршруте
            await message.answer(
                f"🚗 *Маршрут на {route.date}*\n"
                f"📦 Заказов: {len(orders)}",
                parse_mode="Markdown"
            )
            
            # Отправляем каждый заказ с кнопками
            for i, order in enumerate(orders, 1):
                status_emoji = {
                    'planned': '⏳',
                    'in_progress': '🔄',
                    'completed': '✅',
                    'failed': '❌'
                }.get(order.status, '❓')
                
                time_str = order.visit_time or "—"
                address = order.address or order.destination_point or "Адрес не указан"
                recipient = order.recipient_name or "—"
                phone = order.recipient_phone or ""
                
                order_text = (
                    f"*{i}. {order.order_name}* {status_emoji}\n\n"
                    f"🕒 Время: {time_str}\n"
                    f"📍 Адрес: {address}\n"
                    f"👤 Получатель: {recipient}\n"
                )
                
                if order.comment:
                    order_text += f"💬 Комментарий: _{order.comment}_\n"
                
                # Кнопки только для незавершенных заказов
                if order.status not in ['completed', 'failed']:
                    print(f"[DEBUG] Sending order {order.id} with keyboard, status={order.status}")
                    keyboard = generate_order_keyboard(
                        order_id=order.id,
                        lat=order.lat,
                        lon=order.lon,
                        phone=phone,
                        address=address
                    )
                    print(f"[DEBUG] Keyboard generated: {keyboard}")
                    await message.answer(order_text, parse_mode="Markdown", reply_markup=keyboard)
                else:
                    print(f"[DEBUG] Sending order {order.id} WITHOUT keyboard, status={order.status}")
                    await message.answer(order_text, parse_mode="Markdown")


# ============================================================================
# Callback Handlers (Inline Buttons)
# ============================================================================

@dp.callback_query(F.data.startswith("delivered:"))
async def callback_delivered(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки 'Доставлен'"""
    order_id = int(callback.data.split(":")[1])
    
    # Сохраняем order_id в состояние FSM
    await state.update_data(order_id=order_id)
    await state.set_state(DeliveryStates.waiting_photo_proof)
    
    await callback.message.answer(
        "📸 *Подтверждение доставки*\n\n"
        "Пожалуйста, отправьте фото подтверждения доставки.\n"
        "_Например: фото посылки у двери, подпись получателя и т.д._",
        parse_mode="Markdown",
        reply_markup=generate_cancel_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("failed:"))
async def callback_failed(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки 'Отказ'"""
    order_id = int(callback.data.split(":")[1])
    
    # Сохраняем order_id в состояние FSM
    await state.update_data(order_id=order_id)
    await state.set_state(DeliveryStates.waiting_failure_reason)
    
    await callback.message.answer(
        "📝 *Причина отказа*\n\n"
        "Пожалуйста, опишите причину, по которой заказ не был доставлен.\n"
        "_Например: получатель отсутствует, отказался от получения, неверный адрес и т.д._",
        parse_mode="Markdown",
        reply_markup=generate_cancel_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "cancel_action")
async def callback_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена текущего действия"""
    await state.clear()
    await callback.message.answer(
        "❌ Действие отменено",
        parse_mode="Markdown"
    )
    await callback.answer()


# ============================================================================
# Photo Proof Handler (FSM)
# ============================================================================

@dp.message(DeliveryStates.waiting_photo_proof, F.photo)
async def process_photo_proof(message: Message, state: FSMContext):
    """Обработка фото подтверждения доставки"""
    data = await state.get_data()
    order_id = data.get('order_id')
    
    if not order_id:
        await message.answer("❌ Ошибка: заказ не найден")
        await state.clear()
        return
    
    # Создаем директорию если нет
    ensure_proofs_dir()
    
    # Получаем файл фото (берем самое большое разрешение)
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    
    # Обновляем заказ в БД и получаем имя для файла
    app = get_flask_app()
    route_id = None
    order_name = str(order_id)
    
    with app.app_context():
        from models import db, Order
        order = Order.query.get(order_id)
        
        if order:
            order_name = order.order_name or str(order_id)
            route_id = order.route_id
    
    # Генерируем имя файла с названием заказа
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_name = sanitize_filename(order_name)
    filename = f"{safe_name}_{timestamp}.jpg"
    filepath = os.path.join(PROOFS_DIR, filename)
    
    # Скачиваем файл
    await bot.download_file(file.file_path, filepath)
    
    # Обновляем статус заказа в БД
    with app.app_context():
        from models import db, Order
        order = Order.query.get(order_id)
        
        if order:
            order.status = 'completed'
            order.proof_image = f"uploads/proofs/{filename}"
            db.session.commit()
            
            await message.answer(
                f"✅ *Заказ #{order.order_name} завершен!*\n\n"
                f"Фото подтверждения сохранено.\n"
                f"Отличная работа! 🎉",
                parse_mode="Markdown"
            )
            
            # Проверяем, завершён ли маршрут
            if route_id and check_and_complete_route(route_id):
                await message.answer(
                    "🏁 *Маршрут завершён!*\n\n"
                    "Все заказы выполнены. Отлично поработали! 🎊",
                    parse_mode="Markdown"
                )
        else:
            await message.answer("❌ Ошибка: заказ не найден в базе данных")
    
    await state.clear()


@dp.message(DeliveryStates.waiting_photo_proof)
async def process_photo_proof_invalid(message: Message):
    """Обработка не-фото во время ожидания фото"""
    await message.answer(
        "⚠️ Пожалуйста, отправьте *фото* подтверждения доставки.",
        parse_mode="Markdown",
        reply_markup=generate_cancel_keyboard()
    )


# ============================================================================
# Failure Reason Handler (FSM)
# ============================================================================

@dp.message(DeliveryStates.waiting_failure_reason, F.text)
async def process_failure_reason(message: Message, state: FSMContext):
    """Обработка причины отказа"""
    # Игнорируем команды меню
    if message.text in ["📍 Начал смену", "🏁 Закончил смену", "📋 Мои заказы", "🆘 Проблема"]:
        await message.answer(
            "⚠️ Сначала завершите ввод причины отказа или нажмите 'Отмена'",
            reply_markup=generate_cancel_keyboard()
        )
        return
    
    data = await state.get_data()
    order_id = data.get('order_id')
    
    if not order_id:
        await message.answer("❌ Ошибка: заказ не найден")
        await state.clear()
        return
    
    reason = message.text.strip()
    
    # Обновляем заказ в БД
    app = get_flask_app()
    route_id = None
    
    with app.app_context():
        from models import db, Order
        order = Order.query.get(order_id)
        
        if order:
            order.status = 'failed'
            order.failure_reason = reason
            route_id = order.route_id
            db.session.commit()
            
            await message.answer(
                f"📝 *Заказ #{order.order_name} отмечен как недоставленный*\n\n"
                f"Причина: _{reason}_",
                parse_mode="Markdown"
            )
            
            # Проверяем, завершён ли маршрут
            if route_id and check_and_complete_route(route_id):
                await message.answer(
                    "🏁 *Маршрут завершён!*\n\n"
                    "Все заказы выполнены. Отлично поработали! 🎊",
                    parse_mode="Markdown"
                )
        else:
            await message.answer("❌ Ошибка: заказ не найден в базе данных")
    
    await state.clear()


# ============================================================================
# Auth Code Handler
# ============================================================================

@dp.message(F.text)
async def handle_auth_code(message: Message):
    """Обработчик текстовых сообщений (код авторизации)"""
    # Игнорируем команды меню
    menu_commands = ["📍 Начал смену", "🏁 Закончил смену", "📋 Мои заказы", "🆘 Проблема"]
    if message.text in menu_commands:
        return
    
    code = message.text.strip().upper()
    
    # Проверяем формат кода (6 символов, буквы и цифры)
    if len(code) != 6 or not code.isalnum():
        await message.answer(
            "❌ Неверный формат кода.\n"
            "Код должен состоять из 6 символов (буквы A-Z и цифры 0-9).\n\n"
            "Пример: ABC123"
        )
        return
    
    # Работаем с БД через Flask контекст
    app = get_flask_app()
    
    with app.app_context():
        from models import db, Courier
        
        # Проверяем, не привязан ли уже этот chat_id
        existing = Courier.query.filter_by(telegram_chat_id=str(message.chat.id)).first()
        if existing:
            await message.answer(
                f"ℹ️ Вы уже авторизованы как *{existing.full_name}*\n\n"
                f"Используйте /menu для открытия главного меню.",
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard(existing.is_on_shift)
            )
            return
        
        # Ищем курьера по коду
        courier = Courier.query.filter_by(auth_code=code).first()
        
        if not courier:
            await message.answer(
                "❌ *Код не найден*\n\n"
                "Проверьте правильность введенного кода или обратитесь к диспетчеру.",
                parse_mode="Markdown"
            )
            return
        
        # Сохраняем chat_id
        courier.telegram_chat_id = str(message.chat.id)
        # Очищаем код после успешной привязки
        courier.auth_code = None
        
        db.session.commit()
        
        await message.answer(
            f"✅ *Успешно!*\n\n"
            f"Вы привязаны к профилю: *{courier.full_name}*\n\n"
            f"Теперь вы будете получать уведомления о новых маршрутах! 🚗\n\n"
            f"Используйте меню ниже для управления.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(courier.is_on_shift)
        )


# ============================================================================
# Main Entry Point
# ============================================================================

async def main():
    """Запуск бота"""
    print("🤖 Запуск Telegram бота yo.route...")
    print(f"   Bot: @yoroutebot")
    print(f"   Admin ID: {ADMIN_ID}")
    print("   Нажмите Ctrl+C для остановки")
    
    # Создаем директорию для фото
    ensure_proofs_dir()
    
    # Пропускаем накопившиеся обновления
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запуск polling
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
