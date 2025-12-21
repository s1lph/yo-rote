

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


def solve_vrp(orders, couriers, depot=None, route_date=None):
    """
    Решение задачи маршрутизации (VRP) через OpenRouteService.
    
    Args:
        orders: Список заказов (Order объекты)
        couriers: Список курьеров (Courier объекты)
        depot: Словарь с координатами депо {'lat': float, 'lon': float}
        route_date: Дата маршрута в формате 'YYYY-MM-DD' для расчёта временных окон
    
    Returns:
        Список маршрутов с привязкой к курьерам и порядком заказов
    """
    if not client:
        print("❌ ORS клиент не готов")
        return []

    if not orders or not couriers:
        return []

    if depot and depot.get('lat') and depot.get('lon'):
        depot_coords = [depot['lon'], depot['lat']] 
    else:
        depot_coords = [37.6173, 55.7558]
        print("⚠️ Депо не указано, используется Москва по умолчанию")

    # Функция для конвертации HH:MM в Unix timestamp
    def get_time_windows(order):
        """Вычисляет временное окно в Unix timestamp относительно даты маршрута"""
        from datetime import datetime
        
        # Определяем базовую дату
        if route_date:
            try:
                base_date = datetime.strptime(route_date, '%Y-%m-%d')
            except ValueError:
                base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Проверяем наличие временных окон
        if order.time_window_start and order.time_window_end:
            try:
                start_h, start_m = map(int, order.time_window_start.split(':'))
                end_h, end_m = map(int, order.time_window_end.split(':'))
            except (ValueError, AttributeError):
                # Дефолтное окно смены: 09:00-18:00
                start_h, start_m = 9, 0
                end_h, end_m = 18, 0
        else:
            # Дефолтное окно смены: 09:00-18:00
            start_h, start_m = 9, 0
            end_h, end_m = 18, 0
        
        start_dt = base_date.replace(hour=start_h, minute=start_m)
        end_dt = base_date.replace(hour=end_h, minute=end_m)
        
        return [[int(start_dt.timestamp()), int(end_dt.timestamp())]]

    # 1. Подготовка Jobs (Заказов)
    jobs = []
    valid_orders_map = {}

    for order in orders:
        if not order.lat or not order.lon:
            print(f"⚠️ Пропуск заказа ID {order.id}: нет координат")
            continue
        
        valid_orders_map[order.id] = order
        
        # Время на точке (в секундах). Если не указано, берем 5 минут (300с)
        service_duration = (order.time_at_point or 5) * 60
        
        # Skills: если указан required_courier_id, добавляем требование конкретной машины
        job_skills = None
        if hasattr(order, 'required_courier_id') and order.required_courier_id:
            job_skills = [f'vehicle_{order.required_courier_id}']
        
        # Временные окна доставки
        time_windows = get_time_windows(order)
        
        jobs.append(optimization.Job(
            id=order.id,
            location=[order.lon, order.lat],
            service=service_duration,
            skills=job_skills,
            time_windows=time_windows
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

        # Skills: уникальный skill для каждого курьера (для привязки заказов)
        vehicle_skills = [f'vehicle_{courier.id}']

        vehicles.append(optimization.Vehicle(
            id=courier.id,
            profile=profile,
            start=depot_coords,  # Все курьеры стартуют из депо (Точки отправки)
            end=depot_coords,    # И возвращаются обратно
            capacity=[courier.capacity or 50],  # Вместимость (например, кол-во заказов)
            skills=vehicle_skills
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
