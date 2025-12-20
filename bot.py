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
    ContentType,
    FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Загрузка переменных окружения
load_dotenv()

# Получение токена бота
BOT_TOKEN = os.getenv('TG_BOT_TOKEN')

# IDs администраторов для тревожных уведомлений (через запятую)
# Можно указать несколько ID: 123456789,987654321
ADMIN_IDS_STR = os.getenv('TG_ADMIN_ID', '123456789')
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(',') if x.strip().isdigit()]

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


class AdminStates(StatesGroup):
    """Состояния для админ-панели"""
    waiting_broadcast_message = State()  # Ожидание текста рассылки
    waiting_alert_message = State()      # Ожидание текста тревоги


class OwnerStates(StatesGroup):
    """Состояния для панели владельца"""
    waiting_broadcast_message = State()  # Ожидание текста рассылки
    waiting_alert_message = State()      # Ожидание текста тревоги


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

def get_main_menu_keyboard(is_on_shift: bool = False, user_id: int = None) -> ReplyKeyboardMarkup:
    """
    Главное меню бота (Reply Keyboard).
    
    Args:
        is_on_shift: Находится ли курьер на смене
        user_id: ID пользователя для проверки прав админа
    
    Returns:
        ReplyKeyboardMarkup с кнопками меню
    """
    shift_button = "🏁 Закончил смену" if is_on_shift else "📍 Начал смену"
    
    keyboard_rows = [
        [KeyboardButton(text=shift_button)],
        [KeyboardButton(text="📋 Мои заказы"), KeyboardButton(text="🆘 Проблема")]
    ]
    
    # Добавляем кнопку админ-панели для администраторов
    if user_id and user_id in ADMIN_IDS:
        keyboard_rows.append([KeyboardButton(text="🔐 Админ-панель")])
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=keyboard_rows,
        resize_keyboard=True,
        is_persistent=True
    )
    return keyboard


def get_owner_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Меню владельца бизнеса (Reply Keyboard).
    
    Returns:
        ReplyKeyboardMarkup с кнопками меню владельца
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Панель управления")],
            [KeyboardButton(text="🔗 Отвязать Telegram")]
        ],
        resize_keyboard=True,
        is_persistent=True
    )
    return keyboard


def get_owner_panel_keyboard() -> InlineKeyboardMarkup:
    """
    Inline-клавиатура панели владельца.
    
    Returns:
        InlineKeyboardMarkup с кнопками панели управления
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="owner:stats")],
        [InlineKeyboardButton(text="📢 Рассылка курьерам", callback_data="owner:broadcast")],
        [InlineKeyboardButton(text="🚨 Тревога", callback_data="owner:alert")],
        [InlineKeyboardButton(text="📸 Фото-пруфы", callback_data="owner:proofs")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="owner:close")]
    ])


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


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура админ-панели.
    
    Returns:
        InlineKeyboardMarkup с кнопками админки
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="📸 Фото-пруфы", callback_data="admin:proofs")],
        [InlineKeyboardButton(text="📢 Рассылка курьерам", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="🚨 ТРЕВОГА", callback_data="admin:alert")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="admin:close")]
    ])


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS


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
                reply_markup=get_main_menu_keyboard(courier.is_on_shift, message.from_user.id)
            )
        else:
            # Новый пользователь
            welcome_text = """
👋 *Добро пожаловать в yo.route Bot!*

Этот бот предназначен для водителей и курьеров.

🔐 *Для привязки аккаунта:*
Введите 12-значный код, который вы получили от диспетчера или видите в личном кабинете.

_Пример кода: 123456789012_
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
                reply_markup=get_main_menu_keyboard(courier.is_on_shift, message.from_user.id)
            )
        else:
            await message.answer(
                "❌ Вы не авторизованы. Введите код авторизации.",
                parse_mode="Markdown"
            )


# ============================================================================
# Admin Panel (Админ-панель)
# ============================================================================

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    """Открыть админ-панель"""
    if not is_admin(message.from_user.id):
        await message.answer(
            "⛔ *Доступ запрещён*\n\n"
            "У вас нет прав для доступа к админ-панели.",
            parse_mode="Markdown"
        )
        return
    
    await message.answer(
        "🔐 *Админ-панель yo.route*\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )


@dp.message(F.text == "🔐 Админ-панель")
async def btn_admin(message: Message):
    """Открыть админ-панель через кнопку меню"""
    if not is_admin(message.from_user.id):
        await message.answer(
            "⛔ *Доступ запрещён*\n\n"
            "У вас нет прав для доступа к админ-панели.",
            parse_mode="Markdown"
        )
        return
    
    await message.answer(
        "🔐 *Админ-панель yo.route*\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )


@dp.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery):
    """Показать статистику"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    app = get_flask_app()
    with app.app_context():
        from models import Courier, Order, Route
        
        # Статистика курьеров
        total_couriers = Courier.query.count()
        on_shift = Courier.query.filter_by(is_on_shift=True).count()
        with_telegram = Courier.query.filter(Courier.telegram_chat_id.isnot(None)).count()
        
        # Статистика заказов за сегодня
        from datetime import date
        today = date.today().isoformat()
        
        active_routes = Route.query.filter_by(status='active').count()
        completed_routes = Route.query.filter_by(status='completed', date=today).count()
        
        pending_orders = Order.query.filter_by(status='planned').count()
        in_progress = Order.query.filter_by(status='in_progress').count()
        completed_today = Order.query.filter_by(status='completed').count()
        failed_today = Order.query.filter_by(status='failed').count()
    
    stats_text = (
        "📊 *Статистика системы*\n\n"
        "👥 *Курьеры:*\n"
        f"  • Всего: {total_couriers}\n"
        f"  • На смене: {on_shift}\n"
        f"  • С Telegram: {with_telegram}\n\n"
        "🚗 *Маршруты:*\n"
        f"  • Активные: {active_routes}\n"
        f"  • Завершено сегодня: {completed_routes}\n\n"
        "📦 *Заказы:*\n"
        f"  • Ожидают: {pending_orders}\n"
        f"  • В работе: {in_progress}\n"
        f"  • Доставлено: {completed_today}\n"
        f"  • Отказы: {failed_today}\n\n"
        f"⏰ Обновлено: {datetime.now().strftime('%H:%M:%S')}"
    )
    
    await callback.message.edit_text(
        stats_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:stats")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:menu")]
        ])
    )
    await callback.answer()


@dp.callback_query(F.data == "admin:broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    """Начать рассылку курьерам"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_broadcast_message)
    
    await callback.message.edit_text(
        "📢 *Рассылка курьерам*\n\n"
        "Введите текст сообщения, которое будет отправлено всем курьерам с привязанным Telegram.\n\n"
        "_Поддерживается Markdown форматирование._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:cancel")]
        ])
    )
    await callback.answer()


@dp.callback_query(F.data == "admin:alert")
async def admin_alert(callback: CallbackQuery, state: FSMContext):
    """Начать отправку тревоги"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_alert_message)
    
    await callback.message.edit_text(
        "🚨 *ТРЕВОГА - Экстренное оповещение*\n\n"
        "⚠️ Это сообщение будет отправлено ВСЕМ курьерам на смене как срочное уведомление!\n\n"
        "Введите текст тревоги:\n"
        "_Например: Воздушная тревога! Немедленно найдите укрытие!_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:cancel")]
        ])
    )
    await callback.answer()


@dp.callback_query(F.data == "admin:proofs")
async def admin_proofs(callback: CallbackQuery):
    """Показать список последних фото-пруфов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    app = get_flask_app()
    with app.app_context():
        from models import Order, Courier
        
        # Получаем последние 10 заказов с фото
        orders_with_proofs = Order.query.filter(
            Order.proof_image.isnot(None),
            Order.status == 'completed'
        ).order_by(Order.updated_at.desc()).limit(10).all()
        
        if not orders_with_proofs:
            text = (
                "📸 *Фото-пруфы*\n\n"
                "📭 Пока нет завершённых заказов с фото подтверждением."
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:menu")]
            ])
            
            if callback.message.photo:
                await callback.message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
            else:
                await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
            await callback.answer()
            return
        
        # Формируем список кнопок для каждого заказа
        buttons = []
        for order in orders_with_proofs:
            # Получаем имя курьера
            courier_name = "—"
            if order.route_id:
                from models import Route
                route = Route.query.get(order.route_id)
                if route and route.courier_id:
                    courier = Courier.query.get(route.courier_id)
                    if courier:
                        courier_name = courier.full_name
            
            # Форматируем дату
            date_str = order.updated_at.strftime('%d.%m %H:%M') if order.updated_at else "—"
            
            button_text = f"📦 {order.order_name[:20]} | {courier_name[:15]} | {date_str}"
            buttons.append([InlineKeyboardButton(
                text=button_text, 
                callback_data=f"proof:{order.id}"
            )])
        
        buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:menu")])
        
        text = (
            "📸 *Фото-пруфы*\n\n"
            "Последние 10 подтверждений доставки.\n"
            "Нажмите на заказ, чтобы увидеть фото:"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        # Проверяем, является ли сообщение фото
        if callback.message.photo:
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    
    await callback.answer()


@dp.callback_query(F.data.startswith("proof:"))
async def view_proof(callback: CallbackQuery):
    """Показать фото-пруф конкретного заказа"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    order_id = int(callback.data.split(":")[1])
    
    app = get_flask_app()
    with app.app_context():
        from models import Order, Courier, Route
        
        order = Order.query.get(order_id)
        
        if not order or not order.proof_image:
            await callback.answer("❌ Фото не найдено", show_alert=True)
            return
        
        # Путь к файлу
        photo_path = os.path.join(os.path.dirname(__file__), 'static', order.proof_image)
        
        if not os.path.exists(photo_path):
            await callback.answer("❌ Файл фото не найден на сервере", show_alert=True)
            return
        
        # Получаем информацию о курьере
        courier_name = "—"
        if order.route_id:
            route = Route.query.get(order.route_id)
            if route and route.courier_id:
                courier = Courier.query.get(route.courier_id)
                if courier:
                    courier_name = courier.full_name
        
        # Формируем подпись
        caption = (
            f"📦 *{order.order_name}*\n\n"
            f"📍 Адрес: {order.address or '—'}\n"
            f"👤 Получатель: {order.recipient_name or '—'}\n"
            f"🚗 Курьер: {courier_name}\n"
            f"⏰ Доставлено: {order.updated_at.strftime('%d.%m.%Y %H:%M') if order.updated_at else '—'}"
        )
        
        # Отправляем фото
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📸 Все пруфы", callback_data="admin:proofs")],
                [InlineKeyboardButton(text="◀️ Меню", callback_data="admin:menu")]
            ])
        )
    
    await callback.answer()


@dp.callback_query(F.data == "admin:menu")
async def admin_menu(callback: CallbackQuery, state: FSMContext):
    """Вернуться в меню админки"""
    await state.clear()
    
    # Проверяем, является ли сообщение фото (у него нет текста для редактирования)
    if callback.message.photo:
        # Если это фото, отправляем новое сообщение
        await callback.message.answer(
            "🔐 *Админ-панель yo.route*\n\n"
            "Выберите действие:",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )
    else:
        # Если это текстовое сообщение, редактируем его
        await callback.message.edit_text(
            "🔐 *Админ-панель yo.route*\n\n"
            "Выберите действие:",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )
    await callback.answer()


@dp.callback_query(F.data == "admin:cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена действия в админке"""
    await state.clear()
    await callback.message.edit_text(
        "🔐 *Админ-панель yo.route*\n\n"
        "Действие отменено. Выберите следующее действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "admin:close")
async def admin_close(callback: CallbackQuery, state: FSMContext):
    """Закрыть админ-панель"""
    await state.clear()
    await callback.message.delete()
    await callback.answer("Админ-панель закрыта")


# ============================================================================
# Admin Message Handlers (FSM)
# ============================================================================

@dp.message(AdminStates.waiting_broadcast_message, F.text)
async def process_broadcast_message(message: Message, state: FSMContext):
    """Обработка и отправка рассылки"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    
    broadcast_text = message.text.strip()
    
    app = get_flask_app()
    with app.app_context():
        from models import Courier
        
        # Получаем всех курьеров с Telegram
        couriers = Courier.query.filter(Courier.telegram_chat_id.isnot(None)).all()
        
        sent_count = 0
        failed_count = 0
        
        for courier in couriers:
            try:
                await bot.send_message(
                    chat_id=courier.telegram_chat_id,
                    text=f"📢 *Сообщение от диспетчера*\n\n{broadcast_text}",
                    parse_mode="Markdown"
                )
                sent_count += 1
            except Exception as e:
                print(f"[ERROR] Failed to send broadcast to {courier.full_name}: {e}")
                failed_count += 1
    
    await message.answer(
        f"✅ *Рассылка завершена!*\n\n"
        f"📤 Отправлено: {sent_count}\n"
        f"❌ Ошибок: {failed_count}",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )
    await state.clear()


@dp.message(AdminStates.waiting_alert_message, F.text)
async def process_alert_message(message: Message, state: FSMContext):
    """Обработка и отправка тревоги"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    
    alert_text = message.text.strip()
    
    app = get_flask_app()
    with app.app_context():
        from models import Courier
        
        # Получаем только курьеров на смене
        couriers = Courier.query.filter(
            Courier.telegram_chat_id.isnot(None),
            Courier.is_on_shift == True
        ).all()
        
        sent_count = 0
        failed_count = 0
        
        for courier in couriers:
            try:
                await bot.send_message(
                    chat_id=courier.telegram_chat_id,
                    text=(
                        f"🚨🚨🚨 *ТРЕВОГА!* 🚨🚨🚨\n\n"
                        f"{alert_text}\n\n"
                        f"⚠️ _Это экстренное сообщение от диспетчера!_"
                    ),
                    parse_mode="Markdown"
                )
                sent_count += 1
            except Exception as e:
                print(f"[ERROR] Failed to send alert to {courier.full_name}: {e}")
                failed_count += 1
    
    await message.answer(
        f"🚨 *Тревога отправлена!*\n\n"
        f"📤 Оповещено курьеров на смене: {sent_count}\n"
        f"❌ Ошибок: {failed_count}",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )
    await state.clear()


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
            reply_markup=get_main_menu_keyboard(is_on_shift=True, user_id=message.from_user.id)
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
            reply_markup=get_main_menu_keyboard(is_on_shift=False, user_id=message.from_user.id)
        )


# ============================================================================
# Owner Menu Handlers (Меню владельца)
# ============================================================================

@dp.message(F.text == "📊 Панель управления")
async def owner_panel(message: Message):
    """Открыть панель управления владельца"""
    app = get_flask_app()
    with app.app_context():
        from models import User
        
        user = User.query.filter_by(telegram_chat_id=str(message.chat.id)).first()
        
        if not user:
            await message.answer("❌ Вы не авторизованы как владелец.")
            return
        
        await message.answer(
            f"🔐 *Панель управления*\n\n"
            f"Компания: *{user.company_name or 'Не указана'}*\n\n"
            f"Выберите действие:",
            parse_mode="Markdown",
            reply_markup=get_owner_panel_keyboard()
        )


@dp.callback_query(F.data == "owner:stats")
async def owner_stats(callback: CallbackQuery):
    """Показать статистику владельца"""
    app = get_flask_app()
    with app.app_context():
        from models import User, Courier, Order, Route
        
        user = User.query.filter_by(telegram_chat_id=str(callback.message.chat.id)).first()
        
        if not user:
            await callback.answer("❌ Вы не авторизованы как владелец.", show_alert=True)
            return
        
        # Статистика владельца
        total_couriers = Courier.query.filter_by(user_id=user.id).count()
        on_shift = Courier.query.filter_by(user_id=user.id, is_on_shift=True).count()
        with_telegram = Courier.query.filter(
            Courier.user_id == user.id,
            Courier.telegram_chat_id.isnot(None)
        ).count()
        
        # Заказы владельца
        pending_orders = Order.query.filter_by(user_id=user.id, status='planned').count()
        in_progress = Order.query.filter_by(user_id=user.id, status='in_progress').count()
        completed = Order.query.filter_by(user_id=user.id, status='completed').count()
        failed = Order.query.filter_by(user_id=user.id, status='failed').count()
        
        # Маршруты
        active_routes = Route.query.filter_by(user_id=user.id, status='active').count()
        
        stats_text = (
            f"📊 *Статистика {user.company_name or 'вашей компании'}*\n\n"
            f"👥 *Курьеры:*\n"
            f"  • Всего: {total_couriers}\n"
            f"  • На смене: {on_shift}\n"
            f"  • С Telegram: {with_telegram}\n\n"
            f"📦 *Заказы:*\n"
            f"  • Ожидают: {pending_orders}\n"
            f"  • В работе: {in_progress}\n"
            f"  • Доставлено: {completed}\n"
            f"  • Отказы: {failed}\n\n"
            f"🚗 *Активные маршруты:* {active_routes}\n\n"
            f"⏰ Обновлено: {datetime.now().strftime('%H:%M:%S')}"
        )
        
        await callback.message.edit_text(
            stats_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="owner:stats")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="owner:menu")]
            ])
        )
    await callback.answer()


@dp.callback_query(F.data == "owner:broadcast")
async def owner_broadcast(callback: CallbackQuery, state: FSMContext):
    """Начать рассылку курьерам"""
    app = get_flask_app()
    with app.app_context():
        from models import User
        user = User.query.filter_by(telegram_chat_id=str(callback.message.chat.id)).first()
        if not user:
            await callback.answer("❌ Вы не авторизованы", show_alert=True)
            return
        
        await state.update_data(user_id=user.id)
    
    await state.set_state(OwnerStates.waiting_broadcast_message)
    
    await callback.message.edit_text(
        "📢 *Рассылка курьерам*\n\n"
        "Введите текст сообщения, которое будет отправлено вашим курьерам с привязанным Telegram.\n\n"
        "_Поддерживается Markdown форматирование._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="owner:cancel")]
        ])
    )
    await callback.answer()


@dp.callback_query(F.data == "owner:alert")
async def owner_alert(callback: CallbackQuery, state: FSMContext):
    """Начать отправку тревоги"""
    app = get_flask_app()
    with app.app_context():
        from models import User
        user = User.query.filter_by(telegram_chat_id=str(callback.message.chat.id)).first()
        if not user:
            await callback.answer("❌ Вы не авторизованы", show_alert=True)
            return
        
        await state.update_data(user_id=user.id)
    
    await state.set_state(OwnerStates.waiting_alert_message)
    
    await callback.message.edit_text(
        "🚨 *ТРЕВОГА - Экстренное оповещение*\n\n"
        "⚠️ Это сообщение будет отправлено ВСЕМ вашим курьерам на смене как срочное уведомление!\n\n"
        "Введите текст тревоги:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="owner:cancel")]
        ])
    )
    await callback.answer()


@dp.callback_query(F.data == "owner:proofs")
async def owner_proofs(callback: CallbackQuery):
    """Показать список последних фото-пруфов владельца"""
    app = get_flask_app()
    with app.app_context():
        from models import User, Order, Courier, Route
        
        user = User.query.filter_by(telegram_chat_id=str(callback.message.chat.id)).first()
        if not user:
            await callback.answer("❌ Вы не авторизованы", show_alert=True)
            return
        
        # Получаем последние 10 заказов владельца с фото
        orders_with_proofs = Order.query.filter(
            Order.user_id == user.id,
            Order.proof_image.isnot(None),
            Order.status == 'completed'
        ).order_by(Order.updated_at.desc()).limit(10).all()
        
        if not orders_with_proofs:
            text = (
                "📸 *Фото-пруфы*\n\n"
                "📭 Пока нет завершённых заказов с фото подтверждением."
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="owner:menu")]
            ])
            
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
            await callback.answer()
            return
        
        # Формируем список кнопок
        buttons = []
        for order in orders_with_proofs:
            courier_name = "—"
            if order.route_id:
                route = Route.query.get(order.route_id)
                if route and route.courier_id:
                    courier = Courier.query.get(route.courier_id)
                    if courier:
                        courier_name = courier.full_name
            
            date_str = order.updated_at.strftime('%d.%m %H:%M') if order.updated_at else "—"
            button_text = f"📦 {order.order_name[:20]} | {courier_name[:15]} | {date_str}"
            buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"ownerproof:{order.id}")])
        
        buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="owner:menu")])
        
        text = (
            "📸 *Фото-пруфы*\n\n"
            "Последние 10 подтверждений доставки.\n"
            "Нажмите на заказ, чтобы увидеть фото:"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data.startswith("ownerproof:"))
async def view_owner_proof(callback: CallbackQuery):
    """Показать фото-пруф конкретного заказа"""
    order_id = int(callback.data.split(":")[1])
    
    app = get_flask_app()
    with app.app_context():
        from models import User, Order, Courier, Route
        
        user = User.query.filter_by(telegram_chat_id=str(callback.message.chat.id)).first()
        if not user:
            await callback.answer("❌ Вы не авторизованы", show_alert=True)
            return
        
        order = Order.query.get(order_id)
        
        if not order or not order.proof_image or order.user_id != user.id:
            await callback.answer("❌ Фото не найдено", show_alert=True)
            return
        
        photo_path = os.path.join(os.path.dirname(__file__), 'static', order.proof_image)
        
        if not os.path.exists(photo_path):
            await callback.answer("❌ Файл фото не найден на сервере", show_alert=True)
            return
        
        courier_name = "—"
        if order.route_id:
            route = Route.query.get(order.route_id)
            if route and route.courier_id:
                courier = Courier.query.get(route.courier_id)
                if courier:
                    courier_name = courier.full_name
        
        caption = (
            f"📦 *{order.order_name}*\n\n"
            f"📍 Адрес: {order.address or '—'}\n"
            f"👤 Получатель: {order.recipient_name or '—'}\n"
            f"🚗 Курьер: {courier_name}\n"
            f"⏰ Доставлено: {order.updated_at.strftime('%d.%m.%Y %H:%M') if order.updated_at else '—'}"
        )
        
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📸 Все пруфы", callback_data="owner:proofs")],
                [InlineKeyboardButton(text="◀️ Меню", callback_data="owner:menu")]
            ])
        )
    await callback.answer()


@dp.callback_query(F.data == "owner:menu")
async def owner_menu(callback: CallbackQuery, state: FSMContext):
    """Вернуться в меню панели владельца"""
    await state.clear()
    
    app = get_flask_app()
    with app.app_context():
        from models import User
        user = User.query.filter_by(telegram_chat_id=str(callback.message.chat.id)).first()
        company = user.company_name if user else "—"
    
    if callback.message.photo:
        await callback.message.answer(
            f"🔐 *Панель управления*\n\nКомпания: *{company}*\n\nВыберите действие:",
            parse_mode="Markdown",
            reply_markup=get_owner_panel_keyboard()
        )
    else:
        await callback.message.edit_text(
            f"🔐 *Панель управления*\n\nКомпания: *{company}*\n\nВыберите действие:",
            parse_mode="Markdown",
            reply_markup=get_owner_panel_keyboard()
        )
    await callback.answer()


@dp.callback_query(F.data == "owner:cancel")
async def owner_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена действия"""
    await state.clear()
    await callback.message.edit_text(
        "🔐 *Панель управления*\n\nДействие отменено. Выберите следующее действие:",
        parse_mode="Markdown",
        reply_markup=get_owner_panel_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "owner:close")
async def owner_close(callback: CallbackQuery, state: FSMContext):
    """Закрыть панель владельца"""
    await state.clear()
    await callback.message.delete()
    await callback.answer("Панель закрыта")


@dp.message(F.text == "🔗 Отвязать Telegram")
async def owner_unlink_telegram(message: Message):
    """Отвязка Telegram от аккаунта владельца"""
    app = get_flask_app()
    with app.app_context():
        from models import db, User
        
        user = User.query.filter_by(telegram_chat_id=str(message.chat.id)).first()
        
        if not user:
            await message.answer("❌ Вы не авторизованы как владелец.")
            return
        
        user.telegram_chat_id = None
        db.session.commit()
        
        await message.answer(
            "✅ *Telegram успешно отвязан от аккаунта.*\n\n"
            "Вы больше не будете получать уведомления.\n"
            "Для повторной привязки используйте код из личного кабинета yo.route.",
            parse_mode="Markdown"
        )


# ============================================================================
# Owner Message Handlers (FSM)
# ============================================================================

@dp.message(OwnerStates.waiting_broadcast_message, F.text)
async def process_owner_broadcast(message: Message, state: FSMContext):
    """Обработка и отправка рассылки от владельца только своим курьерам"""
    data = await state.get_data()
    user_id = data.get('user_id')
    
    if not user_id:
        await state.clear()
        return
    
    broadcast_text = message.text.strip()
    
    app = get_flask_app()
    with app.app_context():
        from models import Courier
        
        # Получаем только курьеров этого владельца
        couriers = Courier.query.filter(
            Courier.user_id == user_id,
            Courier.telegram_chat_id.isnot(None)
        ).all()
        
        sent_count = 0
        failed_count = 0
        
        for courier in couriers:
            try:
                await bot.send_message(
                    chat_id=courier.telegram_chat_id,
                    text=f"📢 *Сообщение от диспетчера*\n\n{broadcast_text}",
                    parse_mode="Markdown"
                )
                sent_count += 1
            except Exception as e:
                print(f"[ERROR] Failed to send broadcast to {courier.full_name}: {e}")
                failed_count += 1
    
    await message.answer(
        f"✅ *Рассылка завершена!*\n\n"
        f"📤 Отправлено: {sent_count}\n"
        f"❌ Ошибок: {failed_count}",
        parse_mode="Markdown",
        reply_markup=get_owner_panel_keyboard()
    )
    await state.clear()


@dp.message(OwnerStates.waiting_alert_message, F.text)
async def process_owner_alert(message: Message, state: FSMContext):
    """Обработка и отправка тревоги от владельца только своим курьерам на смене"""
    data = await state.get_data()
    user_id = data.get('user_id')
    
    if not user_id:
        await state.clear()
        return
    
    alert_text = message.text.strip()
    
    app = get_flask_app()
    with app.app_context():
        from models import Courier
        
        # Получаем только курьеров этого владельца на смене
        couriers = Courier.query.filter(
            Courier.user_id == user_id,
            Courier.telegram_chat_id.isnot(None),
            Courier.is_on_shift == True
        ).all()
        
        sent_count = 0
        failed_count = 0
        
        for courier in couriers:
            try:
                await bot.send_message(
                    chat_id=courier.telegram_chat_id,
                    text=f"🚨🚨🚨 *ТРЕВОГА!* 🚨🚨🚨\n\n{alert_text}\n\n"
                         f"_Срочное сообщение от диспетчера_",
                    parse_mode="Markdown"
                )
                sent_count += 1
            except Exception as e:
                print(f"[ERROR] Failed to send alert to {courier.full_name}: {e}")
                failed_count += 1
    
    await message.answer(
        f"🚨 *Тревога отправлена!*\n\n"
        f"📤 Получили: {sent_count} курьеров на смене\n"
        f"❌ Ошибок: {failed_count}",
        parse_mode="Markdown",
        reply_markup=get_owner_panel_keyboard()
    )
    await state.clear()


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
    """Тревожная кнопка - уведомление владельцу бизнеса (через courier.user)"""
    app = get_flask_app()
    with app.app_context():
        from models import Courier
        courier = Courier.query.filter_by(telegram_chat_id=str(message.chat.id)).first()
        
        if not courier:
            await message.answer("❌ Вы не авторизованы в системе.")
            return
        
        # Формируем сообщение для владельца
        location_info = ""
        if courier.current_lat and courier.current_lon:
            maps_link = f"https://yandex.ru/maps/?pt={courier.current_lon},{courier.current_lat}&z=17"
            location_info = f"\n📍 [Местоположение]({maps_link})"
        
        alert_message = (
            f"🆘 *ТРЕВОГА! Водитель сообщает о проблеме!*\n\n"
            f"👤 *Курьер:* {courier.full_name}\n"
            f"📞 *Телефон:* {courier.phone or 'не указан'}\n"
            f"🚗 *Транспорт:* {courier.vehicle_type}"
            f"{location_info}\n\n"
            f"⏰ Время: {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}"
        )
        
        # Получаем владельца курьера через relationship
        owner = courier.user
        
        if owner and owner.telegram_chat_id:
            # Отправляем владельцу
            try:
                await bot.send_message(
                    chat_id=owner.telegram_chat_id,
                    text=alert_message,
                    parse_mode="Markdown"
                )
                await message.answer(
                    "✅ *Сообщение отправлено вашему диспетчеру!*\n\n"
                    "Ожидайте, с вами свяжутся в ближайшее время.",
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"[ERROR] Failed to send emergency to owner {owner.id}: {e}")
                await message.answer(
                    "⚠️ Не удалось отправить сообщение диспетчеру.\n"
                    "Пожалуйста, позвоните по телефону поддержки.",
                    parse_mode="Markdown"
                )
        else:
            # Владелец не привязал Telegram
            await message.answer(
                "⚠️ *Ваш диспетчер не привязал Telegram.*\n\n"
                "Пожалуйста, свяжитесь с ним по телефону или сообщите о необходимости "
                "привязать Telegram в личном кабинете yo.route.",
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
    """Обработчик текстовых сообщений (код авторизации для User или Courier)"""
    # Игнорируем команды меню
    menu_commands = [
        "📍 Начал смену", "🏁 Закончил смену", "📋 Мои заказы", "🆘 Проблема",
        "📊 Панель управления", "🔗 Отвязать Telegram", "🔐 Админ-панель"
    ]
    if message.text in menu_commands:
        return
    
    code = message.text.strip()
    
    # Проверяем формат кода (12 символов, буквы, цифры, спецсимволы)
    # Разрешаем буквы, цифры и символы !@#$%&*?
    import re
    if len(code) != 12 or not re.match(r'^[A-Za-z0-9!@#$%&*?]+$', code):
        await message.answer(
            "❌ Неверный формат кода.\n"
            "Код должен состоять из 12 символов (буквы, цифры и символы !@#$%&*?).\n\n"
            "Получите код в личном кабинете yo.route."
        )
        return
    
    # Работаем с БД через Flask контекст
    app = get_flask_app()
    
    with app.app_context():
        from models import db, User, Courier
        
        # Проверяем, не привязан ли уже этот chat_id как Владелец
        existing_user = User.query.filter_by(telegram_chat_id=str(message.chat.id)).first()
        if existing_user:
            await message.answer(
                f"ℹ️ Вы уже авторизованы как владелец *{existing_user.company_name or existing_user.email}*\n\n"
                f"Используйте меню ниже.",
                parse_mode="Markdown",
                reply_markup=get_owner_menu_keyboard()
            )
            return
        
        # Проверяем, не привязан ли уже этот chat_id как Курьер
        existing_courier = Courier.query.filter_by(telegram_chat_id=str(message.chat.id)).first()
        if existing_courier:
            await message.answer(
                f"ℹ️ Вы уже авторизованы как *{existing_courier.full_name}*\n\n"
                f"Используйте /menu для открытия главного меню.",
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard(existing_courier.is_on_shift, message.from_user.id)
            )
            return
        
        # Сначала ищем код в User (Владелец бизнеса)
        user = User.query.filter_by(auth_code=code).first()
        if user:
            user.telegram_chat_id = str(message.chat.id)
            user.auth_code = None  # Очищаем код после использования
            db.session.commit()
            
            await message.answer(
                f"✅ *Добро пожаловать, {user.company_name or 'Владелец'}!*\n\n"
                f"Вы успешно привязали Telegram к аккаунту.\n"
                f"Теперь вы будете получать уведомления от ваших курьеров.\n\n"
                f"Используйте меню ниже для управления.",
                parse_mode="Markdown",
                reply_markup=get_owner_menu_keyboard()
            )
            return
        
        # Если не найден в User, ищем в Courier
        courier = Courier.query.filter_by(auth_code=code).first()
        
        if not courier:
            await message.answer(
                "❌ *Код не найден*\n\n"
                "Проверьте правильность введенного кода или обратитесь к диспетчеру.",
                parse_mode="Markdown"
            )
            return
        
        # Сохраняем chat_id для курьера
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
            reply_markup=get_main_menu_keyboard(courier.is_on_shift, message.from_user.id)
        )


# ============================================================================
# Main Entry Point
# ============================================================================

async def main():
    """Запуск бота в polling режиме (для локальной разработки)"""
    print("🤖 Запуск Telegram бота yo.route (POLLING)...")
    print(f"   Bot: @yoroutebot")
    print(f"   Admin IDs: {ADMIN_IDS}")
    print("   Админ-панель: /admin")
    print("   Нажмите Ctrl+C для остановки")
    
    # Создаем директорию для фото
    ensure_proofs_dir()
    
    # Удаляем webhook и пропускаем накопившиеся обновления
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запуск polling
    await dp.start_polling(bot)


# Webhook режим для Railway
WEBHOOK_PATH = f"/webhook/telegram/{BOT_TOKEN}"
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # Например: https://your-app.up.railway.app

# Глобальный event loop для webhook режима
_webhook_loop = None
_webhook_thread = None


def _run_async_loop(loop):
    """Запуск event loop в отдельном потоке"""
    asyncio.set_event_loop(loop)
    loop.run_forever()


def get_webhook_loop():
    """Получение или создание event loop для webhook"""
    global _webhook_loop, _webhook_thread
    
    if _webhook_loop is None or _webhook_loop.is_closed():
        _webhook_loop = asyncio.new_event_loop()
        _webhook_thread = threading.Thread(target=_run_async_loop, args=(_webhook_loop,), daemon=True)
        _webhook_thread.start()
    
    return _webhook_loop


async def setup_webhook():
    """Установка webhook для Telegram"""
    if WEBHOOK_URL:
        webhook_full_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
        await bot.set_webhook(url=webhook_full_url, drop_pending_updates=True)
        print(f"✅ Webhook установлен: {webhook_full_url}")
        return True
    return False


async def process_webhook_update(update_data: dict):
    """Обработка входящего update от Telegram"""
    from aiogram.types import Update
    update = Update.model_validate(update_data, context={"bot": bot})
    await dp.feed_update(bot=bot, update=update)


def init_bot_webhook(flask_app):
    """
    Интеграция бота с Flask приложением через webhook.
    Вызывается из app.py при старте сервера.
    """
    import threading
    import concurrent.futures
    from flask import request, Response
    
    # Создаем директорию для фото
    ensure_proofs_dir()
    
    # Инициализируем постоянный event loop
    loop = get_webhook_loop()
    
    @flask_app.route(WEBHOOK_PATH, methods=['POST'])
    def telegram_webhook():
        """Endpoint для приёма обновлений от Telegram"""
        if request.headers.get('content-type') == 'application/json':
            update_data = request.get_json()
            
            # Запускаем обработку в постоянном event loop
            future = asyncio.run_coroutine_threadsafe(
                process_webhook_update(update_data),
                loop
            )
            
            try:
                # Ждём выполнения с таймаутом 25 секунд
                future.result(timeout=25)
            except concurrent.futures.TimeoutError:
                print("[WARN] Webhook update processing timeout")
            except Exception as e:
                print(f"[ERROR] Webhook processing error: {e}")
            
            return Response('OK', status=200)
        return Response('Bad Request', status=400)
    
    # Устанавливаем webhook
    if WEBHOOK_URL:
        future = asyncio.run_coroutine_threadsafe(setup_webhook(), loop)
        try:
            future.result(timeout=10)
            print(f"🤖 Telegram бот (WEBHOOK режим) готов")
        except Exception as e:
            print(f"⚠️  Ошибка установки webhook: {e}")
    else:
        print("⚠️  WEBHOOK_URL не установлен, бот не активирован")
    
    return True


# Импорт threading в начало модуля нужен
import threading


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
