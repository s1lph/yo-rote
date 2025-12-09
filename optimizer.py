"""
yo.route - Route Optimization Module
Модуль оптимизации маршрутов с использованием OpenRouteService API (VRP)
"""

import os
import openrouteservice
from openrouteservice import optimization

# Получаем API ключ
ORS_API_KEY = os.getenv('ORS_API_KEY', '')

# Инициализация клиента
client = None
if ORS_API_KEY:
    try:
        client = openrouteservice.Client(key=ORS_API_KEY)
    except Exception as e:
        print(f"⚠️ Ошибка инициализации ORS: {e}")
else:
    print("⚠️ ORS_API_KEY не найден.")


def solve_vrp(orders, couriers, depot=None):
    """
    Решает задачу маршрутизации (VRP): распределяет заказы по курьерам.
    
    Args:
        orders (list): Список объектов Order (SQLAlchemy models)
        couriers (list): Список объектов Courier (SQLAlchemy models)
        depot (dict): Координаты точки отправки {'lat': float, 'lon': float}
        
    Returns:
        list: Список словарей с результатами для каждого маршрута:
        [
            {
                'courier_id': int,
                'geometry': str (encoded polyline),
                'order_ids': list[int] (в порядке посещения),
                'summary': dict (distance, duration)
            },
            ...
        ]
    """
    if not client:
        print("❌ ORS клиент не готов")
        return []

    if not orders or not couriers:
        return []

    # Координаты депо (точки отправки)
    if depot and depot.get('lat') and depot.get('lon'):
        depot_coords = [depot['lon'], depot['lat']]  # ORS использует [lon, lat]
    else:
        # Дефолт: Москва
        depot_coords = [37.6173, 55.7558]
        print("⚠️ Депо не указано, используется Москва по умолчанию")

    # 1. Подготовка Jobs (Заказов)
    jobs = []
    valid_orders_map = {}  # id -> order object

    for order in orders:
        if not order.lat or not order.lon:
            print(f"⚠️ Пропуск заказа ID {order.id}: нет координат")
            continue
        
        valid_orders_map[order.id] = order
        
        # Время на точке (в секундах). Если не указано, берем 5 минут (300с)
        service_duration = (order.time_at_point or 5) * 60
        
        jobs.append(optimization.Job(
            id=order.id,
            location=[order.lon, order.lat],
            service=service_duration,
            # Можно добавить time_windows, если они есть в модели
            # time_windows=[[start_sec, end_sec]] 
        ))

    if not jobs:
        return []

    # 2. Подготовка Vehicles (Курьеров)
    vehicles = []
    courier_map = {}  # vehicle_id -> courier object

    for courier in couriers:
        courier_map[courier.id] = courier
        
        # Профиль транспорта (конвертация из вашей модели в ORS)
        # Ваши типы: car, truck, bicycle, scooter
        # ORS профили: driving-car, driving-hgv, cycling-regular
        profile = 'driving-car'
        if courier.vehicle_type == 'truck':
            profile = 'driving-hgv'
        elif courier.vehicle_type in ['bicycle', 'scooter']:
            profile = 'cycling-regular'
        elif courier.vehicle_type == 'walk':
            profile = 'foot-walking'

        vehicles.append(optimization.Vehicle(
            id=courier.id,
            profile=profile,
            start=depot_coords,  # Все курьеры стартуют из депо (Точки отправки)
            end=depot_coords,    # И возвращаются обратно
            capacity=[courier.capacity or 50],  # Вместимость (например, кол-во заказов)
            # time_window=[start_work_sec, end_work_sec] # Можно добавить график работы
        ))

    # 3. Отправка запроса в ORS
    try:
        print(f"🚀 Запуск VRP: {len(jobs)} заказов, {len(vehicles)} курьеров")
        response = client.optimization(
            jobs=jobs,
            vehicles=vehicles,
            geometry=True
        )
    except Exception as e:
        print(f"❌ Ошибка API оптимизации: {e}")
        return []

    # 4. Разбор ответа
    results = []
    
    if 'routes' in response:
        for route in response['routes']:
            vehicle_id = route['vehicle']  # Это ID нашего курьера
            
            # Собираем ID заказов в порядке следования
            sorted_order_ids = []
            for step in route['steps']:
                if step['type'] == 'job':
                    sorted_order_ids.append(step['id'])
            
            if not sorted_order_ids:
                continue  # Пустой маршрут (курьер не задействован)

            results.append({
                'courier_id': vehicle_id,
                'geometry': route.get('geometry'),
                'order_ids': sorted_order_ids,
                'summary': {
                    'distance': route.get('distance', 0),
                    'duration': route.get('duration', 0)
                }
            })
            
    print(f"✅ Успешно построено маршрутов: {len(results)}")
    return results


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
