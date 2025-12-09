"""
yo.route - Telegram Utilities
Функции для отправки сообщений водителям через Telegram API.

Использует requests вместо aiogram для избежания конфликтов event loop внутри Flask.
"""

import os
import requests
from typing import Optional
from urllib.parse import quote

# URL для Yandex и Google карт
YANDEX_MAPS_URL = "https://yandex.ru/maps/?text="
GOOGLE_MAPS_URL = "https://www.google.com/maps/search/?api=1&query="


def get_telegram_token() -> Optional[str]:
    """Получение токена бота из переменных окружения"""
    return os.getenv('TG_BOT_TOKEN')


def send_telegram_message(chat_id: str, text: str, parse_mode: str = "Markdown") -> dict:
    """
    Отправка сообщения через Telegram Bot API.
    
    Args:
        chat_id: ID чата Telegram
        text: Текст сообщения
        parse_mode: Режим парсинга (Markdown или HTML)
    
    Returns:
        dict: Ответ от Telegram API
    """
    token = get_telegram_token()
    
    if not token:
        return {"ok": False, "error": "TG_BOT_TOKEN not configured"}
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except requests.RequestException as e:
        return {"ok": False, "error": str(e)}


def format_phone(phone: str) -> str:
    """Форматирование телефона для отображения (скрытие части)"""
    if not phone:
        return "—"
    # Показываем первые 4 и последние 2 цифры
    clean = ''.join(filter(str.isdigit, phone))
    if len(clean) > 6:
        return f"+{clean[:4]}...{clean[-2:]}"
    return phone


def generate_maps_link(address: str, lat: float = None, lon: float = None) -> str:
    """
    Генерация ссылки на карты.
    
    Args:
        address: Адрес точки
        lat: Широта (опционально)
        lon: Долгота (опционально)
    
    Returns:
        str: Ссылка на Yandex Maps
    """
    if lat and lon:
        return f"https://yandex.ru/maps/?pt={lon},{lat}&z=17&l=map"
    return f"{YANDEX_MAPS_URL}{quote(address)}"


def send_route_to_driver(route_id: int) -> dict:
    """
    Отправка маршрута водителю в Telegram с интерактивными кнопками.
    
    Каждый заказ отправляется отдельным сообщением с кнопками:
    - ✅ Доставлен
    - ❌ Отказ
    - 🗺 Навигатор (deep link)
    - 📞 Позвонить
    
    Args:
        route_id: ID маршрута
    
    Returns:
        dict: Результат отправки
            - success: bool
            - message: str
            - sent_count: int (количество отправленных сообщений)
    """
    # Импортируем внутри функции для избежания циклических импортов
    from app import app
    from models import Route, Order, Courier
    
    with app.app_context():
        # Загружаем маршрут
        route = Route.query.get(route_id)
        
        if not route:
            return {"success": False, "message": "Маршрут не найден"}
        
        # Загружаем курьера
        courier = Courier.query.get(route.courier_id)
        
        if not courier:
            return {"success": False, "message": "Курьер не найден"}
        
        if not courier.telegram_chat_id:
            return {
                "success": False, 
                "message": f"У курьера {courier.full_name} не привязан Telegram"
            }
        
        # Загружаем заказы маршрута
        orders = Order.query.filter_by(route_id=route_id).order_by(Order.route_position).all()
        
        if not orders:
            return {"success": False, "message": "В маршруте нет заказов"}
        
        token = get_telegram_token()
        if not token:
            return {"success": False, "message": "TG_BOT_TOKEN not configured"}
        
        # Отправляем заголовок маршрута
        header_text = (
            f"🚗 *Новый маршрут на {route.date}*\n"
            f"📦 Заказов: {len(orders)}\n\n"
            f"Каждый заказ ниже содержит кнопки для управления."
        )
        
        header_response = send_telegram_message(
            chat_id=courier.telegram_chat_id,
            text=header_text,
            parse_mode="Markdown"
        )
        
        if not header_response.get("ok"):
            error = header_response.get("description") or header_response.get("error", "Unknown error")
            return {
                "success": False,
                "message": f"Ошибка отправки в Telegram: {error}",
                "telegram_response": header_response
            }
        
        # Отправляем каждый заказ отдельным сообщением с кнопками
        sent_count = 1  # Учитываем заголовок
        
        for i, order in enumerate(orders, 1):
            time_str = order.visit_time or "—"
            address = order.address or order.destination_point or "Адрес не указан"
            recipient = order.recipient_name or "—"
            phone = format_phone(order.recipient_phone)
            
            # Формируем текст заказа
            order_lines = [
                f"*{i}. {order.order_name}*",
                f"",
                f"🕒 Время: {time_str}",
                f"📍 Адрес: {address}",
                f"👤 Получатель: {recipient}",
                f"📞 Телефон: {phone}",
            ]
            
            if order.comment:
                order_lines.append(f"💬 _{order.comment}_")
            
            order_text = "\n".join(order_lines)
            
            # Генерируем inline keyboard для заказа
            keyboard = generate_order_inline_keyboard(
                order_id=order.id,
                lat=order.lat,
                lon=order.lon,
                phone=order.recipient_phone,
                address=address
            )
            
            # Отправляем сообщение с кнопками
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": courier.telegram_chat_id,
                "text": order_text,
                "parse_mode": "Markdown",
                "reply_markup": keyboard
            }
            
            try:
                print(f"[DEBUG send_route] Sending order {order.id} with keyboard: {keyboard}")
                response = requests.post(url, json=payload, timeout=10)
                result = response.json()
                print(f"[DEBUG send_route] Response: {result}")
                if result.get("ok"):
                    sent_count += 1
                else:
                    print(f"[ERROR send_route] Failed to send order {order.id}: {result}")
            except requests.RequestException as e:
                print(f"[ERROR send_route] Exception: {e}")
                pass  # Продолжаем отправку остальных заказов
        
        # Финальное сообщение
        final_text = "Удачи на маршруте! 🍀"
        send_telegram_message(
            chat_id=courier.telegram_chat_id,
            text=final_text
        )
        
        return {
            "success": True,
            "message": f"Маршрут отправлен курьеру {courier.full_name} ({sent_count} сообщений)",
            "sent_count": sent_count
        }


def generate_order_inline_keyboard(
    order_id: int,
    lat: float = None,
    lon: float = None,
    phone: str = None,
    address: str = None
) -> dict:
    """
    Генерация inline keyboard для заказа (формат Telegram API).
    
    Args:
        order_id: ID заказа
        lat: Широта точки доставки
        lon: Долгота точки доставки
        phone: Телефон получателя
        address: Адрес доставки
    
    Returns:
        dict: Структура reply_markup для Telegram API
    """
    buttons = []
    
    # Первый ряд: Доставлен / Отказ
    buttons.append([
        {"text": "✅ Доставлен", "callback_data": f"delivered:{order_id}"},
        {"text": "❌ Отказ", "callback_data": f"failed:{order_id}"}
    ])
    
    # Второй ряд: Навигация
    row2 = []
    
    # Кнопка навигации
    if lat and lon:
        yandex_maps_url = f"https://yandex.ru/maps/?rtext=~{lat},{lon}&rtt=auto"
        row2.append({"text": "🗺 Навигатор", "url": yandex_maps_url})
    elif address:
        encoded_address = quote(address)
        yandex_maps_url = f"https://yandex.ru/maps/?text={encoded_address}&rtt=auto"
        row2.append({"text": "🗺 Карта", "url": yandex_maps_url})
    
    # Примечание: Telegram не поддерживает tel: URLs в inline кнопках
    # Телефон показывается в тексте сообщения
    
    if row2:
        buttons.append(row2)
    
    return {"inline_keyboard": buttons}

