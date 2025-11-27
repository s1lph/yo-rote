"""
yo.route - Route Optimization Module
Модуль оптимизации маршрутов с использованием OpenRouteService API
"""

import os
import openrouteservice
from openrouteservice import optimization

# Получаем API ключ из переменной окружения
ORS_API_KEY = os.getenv('ORS_API_KEY', '')

# Инициализация клиента ORS
client = None
if ORS_API_KEY:
    try:
        client = openrouteservice.Client(key=ORS_API_KEY)
    except Exception as e:
        print(f"⚠️  Ошибка инициализации ORS клиента: {e}")
else:
    print("⚠️  ORS_API_KEY не установлен. Функции геокодинга и оптимизации будут недоступны.")


def geocode_address(address, country='RU'):
    """
    Геокодирование адреса в координаты через OpenRouteService
    
    Args:
        address (str): Адрес для геокодирования
        country (str): Код страны для фильтрации результатов (по умолчанию 'RU')
    
    Returns:
        tuple: (longitude, latitude) или None если адрес не найден
    """
    if not client:
        print(f"❌ Геокодинг недоступен: ORS клиент не инициализирован")
        return None
    
    try:
        # Pelias Search - геокодинг через ORS
        results = client.pelias_search(text=address, country=country)
        
        if results and 'features' in results and results['features']:
            # Берем первый результат
            coords = results['features'][0]['geometry']['coordinates']
            lon, lat = coords[0], coords[1]
            print(f"✅ Геокодинг успешен: {address} → [{lon}, {lat}]")
            return (lon, lat)
        else:
            print(f"❌ Адрес не найден: {address}")
            return None
            
    except Exception as e:
        print(f"❌ Ошибка геокодинга для адреса '{address}': {e}")
        return None


def build_route(orders, courier):
    """
    Построение оптимального маршрута для курьера с использованием VRP алгоритма
    
    Args:
        orders (list): Список объектов Order для включения в маршрут
        courier (Courier): Объект курьера
    
    Returns:
        tuple: (geometry_string, sorted_orders_list) или (None, []) при ошибке
            - geometry_string: encoded polyline геометрия маршрута
            - sorted_orders_list: список заказов в оптимальном порядке посещения
    """
    if not client:
        print("❌ Оптимизация недоступна: ORS клиент не инициализирован")
        return None, []
    
    jobs = []
    valid_orders = []
    
    # Подготовка заказов для VRP
    for order in orders:
        # Проверяем наличие координат
        if not order.lat or not order.lon:
            # Пытаемся геокодировать адрес
            coords = geocode_address(order.address)
            if coords:
                order.lon, order.lat = coords[0], coords[1]
            else:
                print(f"⚠️  Пропуск заказа {order.order_name}: координаты недоступны")
                continue
        
        valid_orders.append(order)
        
        # Создаем VRP job для заказа
        # Service time указывается в секундах
        service_time = (order.time_at_point or 15) * 60  # конвертируем минуты в секунды
        
        jobs.append(optimization.Job(
            id=order.id,
            location=[order.lon, order.lat],
            service=service_time
        ))
    
    if not jobs:
        print("❌ Нет валидных заказов для оптимизации")
        return None, []
    
    # Создаем транспортное средство (курьера)
    vehicle = optimization.Vehicle(
        id=courier.id,
        profile=courier.profile,
        start=[courier.start_lon, courier.start_lat],
        end=[courier.start_lon, courier.start_lat],  # возвращается на базу
        capacity=[courier.capacity]
    )
    
    try:
        print(f"🔄 Запуск оптимизации для {len(jobs)} заказов...")
        
        # Вызов API ORS Optimization
        response = client.optimization(
            jobs=jobs,
            vehicles=[vehicle],
            geometry=True  # запрашиваем геометрию маршрута
        )
        
        if 'routes' in response and response['routes']:
            route_data = response['routes'][0]
            
            # Получаем отсортированный список заказов согласно оптимальному маршруту
            sorted_orders = []
            for step in route_data['steps']:
                if step['type'] == 'job':
                    # Находим оригинальный заказ по ID
                    original_order = next((o for o in valid_orders if o.id == step['id']), None)
                    if original_order:
                        sorted_orders.append(original_order)
            
            geometry = route_data.get('geometry', '')
            
            print(f"✅ Оптимизация завершена успешно: {len(sorted_orders)} заказов")
            print(f"   Геометрия маршрута: {len(geometry)} символов")
            
            return geometry, sorted_orders
        else:
            print("❌ Ответ ORS не содержит маршрутов")
            return None, []
            
    except Exception as e:
        print(f"❌ Ошибка оптимизации: {e}")
        return None, []


def decode_polyline(encoded):
    """
    Декодирование Google Encoded Polyline в список координат
    
    Args:
        encoded (str): Закодированная строка polyline
    
    Returns:
        list: Список координат [[lat, lon], [lat, lon], ...]
    """
    coords = []
    index = 0
    lat = 0
    lng = 0
    
    while index < len(encoded):
        # Декодируем latitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat
        
        # Декодируем longitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng
        
        coords.append([lat / 1e5, lng / 1e5])
    
    return coords
