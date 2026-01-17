
import os
import requests
from typing import Optional
from urllib.parse import quote


YANDEX_MAPS_URL = "https://yandex.ru/maps/?text="
GOOGLE_MAPS_URL = "https://www.google.com/maps/search/?api=1&query="


def get_telegram_token() -> Optional[str]:
    return os.getenv('TG_BOT_TOKEN')


def send_telegram_message(chat_id: str, text: str, parse_mode: str = "Markdown") -> dict:

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
    if not phone:
        return "—"
    
    clean = ''.join(filter(str.isdigit, phone))
    if len(clean) > 6:
        return f"+{clean[:4]}...{clean[-2:]}"
    return phone


def generate_maps_link(address: str, lat: float = None, lon: float = None) -> str:

    if lat and lon:
        return f"https://yandex.ru/maps/?pt={lon},{lat}&z=17&l=map"
    return f"{YANDEX_MAPS_URL}{quote(address)}"


def send_route_to_driver(route_id: int) -> dict:

    
    from app import app
    from models import Route, Order, Courier
    
    with app.app_context():
        
        route = Route.query.get(route_id)
        
        if not route:
            return {"success": False, "message": "Маршрут не найден"}
        
        
        courier = Courier.query.get(route.courier_id)
        
        if not courier:
            return {"success": False, "message": "Курьер не найден"}
        
        if not courier.telegram_chat_id:
            return {
                "success": False, 
                "message": f"У курьера {courier.full_name} не привязан Telegram"
            }
        
        
        orders = Order.query.filter_by(route_id=route_id).order_by(Order.route_position).all()
        
        if not orders:
            return {"success": False, "message": "В маршруте нет заказов"}
        
        token = get_telegram_token()
        if not token:
            return {"success": False, "message": "TG_BOT_TOKEN not configured"}
        
        
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
        
        
        sent_count = 1  
        
        for i, order in enumerate(orders, 1):
            time_str = order.visit_time or "—"
            address = order.address or order.destination_point or "Адрес не указан"
            recipient = order.recipient_name or "—"
            phone = format_phone(order.recipient_phone)
            
            
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
            
            
            keyboard = generate_order_inline_keyboard(
                order_id=order.id,
                lat=order.lat,
                lon=order.lon,
                phone=order.recipient_phone,
                address=address
            )
            
            
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
                pass  
        
        
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
    buttons = []
    
    
    buttons.append([
        {"text": "✅ Доставлен", "callback_data": f"delivered:{order_id}"},
        {"text": "❌ Отказ", "callback_data": f"failed:{order_id}"}
    ])
    
    
    row2 = []
    
    
    if lat and lon:
        yandex_maps_url = f"https://yandex.ru/maps/?rtext=~{lat},{lon}&rtt=auto"
        row2.append({"text": "🗺 Навигатор", "url": yandex_maps_url})
    elif address:
        encoded_address = quote(address)
        yandex_maps_url = f"https://yandex.ru/maps/?text={encoded_address}&rtt=auto"
        row2.append({"text": "🗺 Карта", "url": yandex_maps_url})
    
    
    
    
    if row2:
        buttons.append(row2)
    
    return {"inline_keyboard": buttons}

