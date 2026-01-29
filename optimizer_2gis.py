"""
2GIS Integration Module for Route Optimization
Модуль оптимизации маршрутов через 2GIS TSP API с учётом пробок
"""

import os
import time
import requests
from datetime import datetime


TWOGIS_API_KEY = os.getenv('TWOGIS_API_KEY', '')
TWOGIS_BASE_URL = 'https://routing.api.2gis.com'
TWOGIS_GEOCODER_URL = 'https://catalog.api.2gis.com/3.0/items/geocode'
TWOGIS_ROUTING_URL = 'https://routing.api.2gis.com/routing/7.0.0/global'

VRP_CREATE_ENDPOINT = '/logistics/vrp/1.1.0/create'
VRP_STATUS_ENDPOINT = '/logistics/vrp/1.1.0/status'

VEHICLE_TYPE_MAP = {
    'car': 'driving',
    'truck': 'truck',
    'bicycle': 'bicycle',
    'scooter': 'scooter',
    'walk': 'walking'
}

MAX_POLL_ATTEMPTS = 60
POLL_INTERVAL_SECONDS = 2


def solve_vrp_2gis(orders, couriers, depot=None, route_date=None, consider_traffic=True):
    """
    Решение VRP через 2GIS TSP API с учётом пробок.
    
    Args:
        orders: Список заказов (Order objects)
        couriers: Список курьеров (Courier objects)
        depot: Координаты депо {'lat': ..., 'lon': ...}
        route_date: Дата маршрута (YYYY-MM-DD)
        consider_traffic: Учитывать пробки (True = jam, False = shortest)
    
    Returns:
        Список маршрутов с геометрией
    """
    if not TWOGIS_API_KEY:
        print("❌ TWOGIS_API_KEY не найден")
        return []
    
    if not orders or not couriers:
        print("❌ Нет заказов или курьеров")
        return []
    
    if depot and depot.get('lat') and depot.get('lon'):
        depot_coords = {'lat': depot['lat'], 'lon': depot['lon']}
    else:
        depot_coords = {'lat': 55.7558, 'lon': 37.6173}
        print("⚠️ Депо не указано, используется Москва по умолчанию")
    
    valid_orders = [o for o in orders if o.lat and o.lon]
    if not valid_orders:
        print("❌ Нет заказов с координатами")
        return []
    
    waypoints = _build_waypoints(valid_orders, depot_coords, route_date)
    agents = _build_agents(couriers, depot_coords, route_date)
    
    if route_date:
        try:
            start_time = datetime.strptime(route_date, '%Y-%m-%d').replace(hour=8, minute=0)
            start_time_iso = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            start_time_iso = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
    else:
        start_time_iso = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
    
    routing_type = 'jam' if consider_traffic else 'shortest'
    transport = VEHICLE_TYPE_MAP.get(couriers[0].vehicle_type, 'driving') if couriers else 'driving'
    
    payload = {
        'start_time': start_time_iso,
        'waypoints': waypoints,
        'agents': agents,
        'routing_options': {
            'type': routing_type,
            'transport': transport
        }
    }
    
    print(f"📤 Отправка VRP задачи в 2GIS: {len(valid_orders)} заказов, {len(couriers)} курьеров")
    
    task_id = _create_vrp_task(payload)
    if not task_id:
        return []
    
    solution = _poll_vrp_status(task_id)
    if not solution:
        return []
    
    return _process_vrp_solution(solution, valid_orders, couriers, depot_coords)


def _build_waypoints(orders, depot_coords, route_date):
    """Построение массива waypoints для 2GIS API"""
    waypoints = []
    
    waypoints.append({
        'waypoint_id': 0,
        'point': depot_coords
    })
    
    for order in orders:
        order_type = getattr(order, 'type', 'delivery')
        service_time = (order.time_at_point or 15) * 60
        
        waypoint = {
            'waypoint_id': order.id,
            'point': {'lat': order.lat, 'lon': order.lon},
            'service_time': service_time
        }
        
        if order_type == 'delivery':
            waypoint['delivery_value'] = 1
        else:
            waypoint['pickup_value'] = 1
        
        time_windows = _get_time_windows(order, route_date)
        if time_windows:
            waypoint['time_windows'] = time_windows
        
        waypoints.append(waypoint)
    
    return waypoints


def _build_agents(couriers, depot_coords, route_date):
    """Построение массива agents для 2GIS API"""
    agents = []
    
    base_start = 8 * 3600
    base_end = 20 * 3600
    
    for courier in couriers:
        agent = {
            'agent_id': courier.id,
            'start_waypoint_id': 0,
            'capacity': courier.capacity or 100,
            'work_time_window': {
                'start': base_start,
                'end': base_end
            }
        }
        
        if courier.start_lat and courier.start_lon:
            pass
        
        agents.append(agent)
    
    return agents


def _get_time_windows(order, route_date):
    """Получение временных окон заказа в секундах от полуночи"""
    if not order.time_window_start or not order.time_window_end:
        return None
    
    try:
        start_h, start_m = map(int, order.time_window_start.split(':'))
        end_h, end_m = map(int, order.time_window_end.split(':'))
        
        start_seconds = start_h * 3600 + start_m * 60
        end_seconds = end_h * 3600 + end_m * 60
        
        return [{'start': start_seconds, 'end': end_seconds}]
    except (ValueError, AttributeError):
        return None


def _create_vrp_task(payload):
    """Создание задачи VRP в 2GIS"""
    url = f"{TWOGIS_BASE_URL}{VRP_CREATE_ENDPOINT}?key={TWOGIS_API_KEY}"
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        task_id = data.get('task_id')
        
        if task_id:
            print(f"✅ VRP задача создана: {task_id}")
            return task_id
        else:
            print(f"❌ Ошибка создания задачи: {data}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка запроса к 2GIS: {e}")
        return None


def _poll_vrp_status(task_id):
    """Опрос статуса VRP задачи до завершения"""
    url = f"{TWOGIS_BASE_URL}{VRP_STATUS_ENDPOINT}?task_id={task_id}&key={TWOGIS_API_KEY}"
    
    for attempt in range(MAX_POLL_ATTEMPTS):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            status = data.get('status')
            
            if status == 'Done':
                print(f"✅ VRP задача завершена успешно")
                solution_url = data.get('urls', {}).get('url_vrp_solution')
                if solution_url:
                    return _fetch_solution(solution_url)
                return None
                
            elif status == 'Partial':
                print(f"⚠️ VRP задача завершена частично (некоторые точки исключены)")
                solution_url = data.get('urls', {}).get('url_vrp_solution')
                if solution_url:
                    return _fetch_solution(solution_url)
                return None
                
            elif status == 'Fail':
                print(f"❌ VRP задача завершилась с ошибкой")
                return None
                
            elif status == 'Run':
                time.sleep(POLL_INTERVAL_SECONDS)
            else:
                print(f"⚠️ Неизвестный статус: {status}")
                time.sleep(POLL_INTERVAL_SECONDS)
                
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Ошибка проверки статуса: {e}")
            time.sleep(POLL_INTERVAL_SECONDS)
    
    print(f"❌ Превышено время ожидания VRP задачи")
    return None


def _fetch_solution(solution_url):
    """Загрузка решения VRP по URL"""
    try:
        response = requests.get(solution_url, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка загрузки решения: {e}")
        return None


def _process_vrp_solution(solution, orders, couriers, depot_coords):
    """Обработка решения VRP и формирование маршрутов"""
    results = []
    
    orders_map = {o.id: o for o in orders}
    couriers_map = {c.id: c for c in couriers}
    
    for route in solution.get('routes', []):
        agent_id = route.get('agent_id')
        points = route.get('points', [])
        
        order_ids = [p for p in points if p != 0 and p in orders_map]
        
        if not order_ids:
            continue
        
        geometry = _get_route_geometry(order_ids, orders_map, depot_coords, couriers_map.get(agent_id))
        
        results.append({
            'courier_id': agent_id,
            'order_ids': order_ids,
            'geometry': geometry,
            'summary': {
                'distance': route.get('distance', 0),
                'duration': route.get('duration', 0)
            }
        })
    
    print(f"✅ Обработано маршрутов: {len(results)}")
    return results


def _get_route_geometry(order_ids, orders_map, depot_coords, courier=None):
    """Получение геометрии маршрута через 2GIS Directions API (POST запрос с JSON)"""
    
    # Формируем массив точек в формате JSON для 2GIS API
    points_json = []
    
    # Депо в начале
    points_json.append({
        'lon': depot_coords['lon'],
        'lat': depot_coords['lat']
    })
    
    # Заказы
    for order_id in order_ids:
        order = orders_map.get(order_id)
        if order and order.lat and order.lon:
            points_json.append({
                'lon': order.lon,
                'lat': order.lat
            })
    
    # Депо в конце (возврат)
    points_json.append({
        'lon': depot_coords['lon'],
        'lat': depot_coords['lat']
    })
    
    if len(points_json) < 2:
        return None

    
    # Определение типа транспорта
    transport = 'car'
    if courier and hasattr(courier, 'vehicle_type'):
        transport = VEHICLE_TYPE_MAP.get(courier.vehicle_type, 'car')
    
    # URL для Directions API
    url = f"{TWOGIS_ROUTING_URL}?key={TWOGIS_API_KEY}"
    
    # Тело запроса
    payload = {
        'points': points_json,
        'type': transport,
        'output': 'detailed',  # Детальный вывод включает геометрию
        'route_mode': 'jam'    # Учёт пробок
    }
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        print(f"🔗 Routing API Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"⚠️ Routing API Error: {response.text[:200]}")
            # Попробуем альтернативный формат без route_mode
            payload.pop('route_mode', None)
            payload['traffic'] = 'jam'
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code != 200:
                print(f"⚠️ Routing API Retry Error: {response.text[:200]}")
                return None
        
        data = response.json()
        
        # Попробуем извлечь геометрию из разных мест ответа
        result = data.get('result', [])
        
        if result and len(result) > 0:
            route_result = result[0]
            
            # Логируем доступные ключи
            print(f"📍 Route result keys: {list(route_result.keys())}")
            
            # Вариант 1: WKT в поле wkt
            wkt = route_result.get('wkt')
            if wkt:
                print(f"✅ Found WKT geometry")
                return _parse_linestring_to_coords(wkt)
            
            # Вариант 2: geometry объект с selection
            geometry = route_result.get('geometry', {})
            selection = geometry.get('selection')
            if selection:
                print(f"✅ Found geometry.selection")
                return _parse_linestring_to_coords(selection)
            
            # Вариант 3: total_geometry
            total_geometry = route_result.get('total_geometry')
            if total_geometry:
                print(f"✅ Found total_geometry")
                return _parse_linestring_to_coords(total_geometry)
            
            # Вариант 4: legs с geometry
            legs = route_result.get('legs', [])
            all_coords = []
            for leg in legs:
                leg_geometry = leg.get('geometry', {})
                leg_selection = leg_geometry.get('selection')
                if leg_selection:
                    coords = _extract_coords_from_linestring(leg_selection)
                    if coords:
                        all_coords.extend(coords)
            
            if all_coords:
                print(f"✅ Found geometry from legs: {len(all_coords)} points")
                return _encode_coords_to_polyline(all_coords)
            
            # Вариант 5: maneuvers с outcoming_path.geometry
            maneuvers = route_result.get('maneuvers', [])
            for maneuver in maneuvers:
                outcoming_path = maneuver.get('outcoming_path', {})
                geometry_list = outcoming_path.get('geometry', [])
                
                # geometry может быть массивом объектов с selection
                for geom_item in geometry_list:
                    selection = geom_item.get('selection') if isinstance(geom_item, dict) else None
                    if selection:
                        coords = _extract_coords_from_linestring(selection)
                        if coords:
                            all_coords.extend(coords)
            
            if all_coords:
                print(f"✅ Found geometry from maneuvers: {len(all_coords)} points")
                return _encode_coords_to_polyline(all_coords)

            
            print(f"⚠️ No geometry found in response, available keys: {list(route_result.keys())}")
        
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Routing request error: {e}")
        return None
    except Exception as e:
        print(f"⚠️ Geometry processing error: {e}")
        return None


def _extract_coords_from_linestring(wkt_string):
    """Извлекает координаты из LINESTRING, возвращает массив [lat, lon]"""
    if not wkt_string:
        return None
    
    try:
        if wkt_string.startswith('LINESTRING'):
            coords_str = wkt_string.replace('LINESTRING(', '').replace(')', '')
            pairs = coords_str.split(',')
            
            coords = []
            for pair in pairs:
                parts = pair.strip().split()
                if len(parts) >= 2:
                    lon = float(parts[0])
                    lat = float(parts[1])
                    coords.append([lat, lon])
            
            return coords if coords else None
        
        return None
    except Exception:
        return None



def _parse_linestring_to_coords(wkt_string):
    """Парсинг LINESTRING WKT в список координат и кодирование в polyline"""
    if not wkt_string:
        return None
    
    try:
        # Извлекаем координаты из LINESTRING(lon lat, lon lat, ...)
        if wkt_string.startswith('LINESTRING'):
            coords_str = wkt_string.replace('LINESTRING(', '').replace(')', '')
            pairs = coords_str.split(',')
            
            coords = []
            for pair in pairs:
                parts = pair.strip().split()
                if len(parts) >= 2:
                    lon = float(parts[0])
                    lat = float(parts[1])
                    coords.append([lat, lon])  # [lat, lon] для polyline
            
            if coords:
                return _encode_coords_to_polyline(coords)
        
        return None
        
    except Exception as e:
        print(f"⚠️ Ошибка парсинга LINESTRING: {e}")
        return None


def _encode_coords_to_polyline(coords):
    """Кодирование координат в Google Polyline формат"""
    if not coords:
        return None
    
    encoded = ''
    prev_lat = 0
    prev_lng = 0
    
    for lat, lng in coords:
        # Масштабирование и округление
        lat_int = round(lat * 1e5)
        lng_int = round(lng * 1e5)
        
        # Разница от предыдущей точки
        d_lat = lat_int - prev_lat
        d_lng = lng_int - prev_lng
        
        prev_lat = lat_int
        prev_lng = lng_int
        
        # Кодирование разницы
        encoded += _encode_number(d_lat)
        encoded += _encode_number(d_lng)
    
    return encoded


def _encode_number(num):
    """Кодирование числа в polyline формат"""
    # Инвертируем отрицательные числа
    if num < 0:
        num = ~num << 1
    else:
        num = num << 1
    
    result = ''
    while num >= 0x20:
        result += chr((0x20 | (num & 0x1f)) + 63)
        num >>= 5
    result += chr(num + 63)
    
    return result


def geocode_address_2gis(address, country='ru'):
    """
    Геокодирование адреса через 2GIS Geocoder API
    
    Args:
        address: Строка адреса
        country: Код страны (ru, kz, etc.)
    
    Returns:
        Tuple (lon, lat) или None
    """
    if not TWOGIS_API_KEY:
        print("❌ TWOGIS_API_KEY не найден для геокодирования")
        return None
    
    params = {
        'key': TWOGIS_API_KEY,
        'q': address,
        'fields': 'items.point',
        'type': 'building,street,adm_div.city'
    }
    
    try:
        response = requests.get(TWOGIS_GEOCODER_URL, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        items = data.get('result', {}).get('items', [])
        
        if items and len(items) > 0:
            point = items[0].get('point')
            if point:
                lon = point.get('lon')
                lat = point.get('lat')
                print(f"✅ Геокодинг: {address} → [{lon}, {lat}]")
                return (lon, lat)
        
        print(f"⚠️ Адрес не найден: {address}")
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка геокодирования: {e}")
        return None


def decode_polyline_2gis(encoded):
    """
    Декодирование polyline (совместимо с Google Polyline Algorithm)
    
    Args:
        encoded: Закодированная строка polyline
    
    Returns:
        Список координат [[lat, lon], ...]
    """
    coords = []
    index = 0
    lat = 0
    lng = 0
    
    while index < len(encoded):
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
