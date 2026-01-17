

import os
import openrouteservice
from openrouteservice import optimization


ORS_API_KEY = os.getenv('ORS_API_KEY', '')


client = None
if ORS_API_KEY:
    try:
        client = openrouteservice.Client(key=ORS_API_KEY)
    except Exception as e:
        print(f" Ошибка инициализации ORS: {e}")
else:
    print(" ORS_API_KEY не найден.")


def solve_vrp(orders, couriers, depot=None, route_date=None):
    if not client:
        print(" ORS клиент не готов")
        return []

    if not orders or not couriers:
        return []

    if depot and depot.get('lat') and depot.get('lon'):
        depot_coords = [depot['lon'], depot['lat']] 
    else:
        depot_coords = [37.6173, 55.7558]
        print(" Депо не указано, используется Москва по умолчанию")

    
    def get_time_windows(order):

        from datetime import datetime
        
        
        if route_date:
            try:
                base_date = datetime.strptime(route_date, '%Y-%m-%d')
            except ValueError:
                base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        
        if order.time_window_start and order.time_window_end:
            try:
                start_h, start_m = map(int, order.time_window_start.split(':'))
                end_h, end_m = map(int, order.time_window_end.split(':'))
            except (ValueError, AttributeError):
                
                start_h, start_m = 9, 0
                end_h, end_m = 18, 0
        else:
            
            start_h, start_m = 9, 0
            end_h, end_m = 18, 0
        
        start_dt = base_date.replace(hour=start_h, minute=start_m)
        end_dt = base_date.replace(hour=end_h, minute=end_m)
        
        return [[int(start_dt.timestamp()), int(end_dt.timestamp())]]

    
    valid_orders_map = {o.id: o for o in orders if o.lat and o.lon}
    
    # Prepare final payload for VROOM-compatible ORS endpoint
    payload = {
        "vehicles": [],
        "shipments": [],
        "options": {"g": True}
    }

    for courier in couriers:
        profile = 'driving-car'
        if courier.vehicle_type == 'truck':
            profile = 'driving-hgv'
        elif courier.vehicle_type in ['bicycle', 'scooter']:
            profile = 'cycling-regular'
        elif courier.vehicle_type == 'walk':
            profile = 'foot-walking'

        start_coords = [courier.start_lon, courier.start_lat] if courier.start_lon and courier.start_lat else depot_coords
        
        payload["vehicles"].append({
            "id": courier.id,
            "profile": profile,
            "start": start_coords,
            "end": start_coords,
            "capacity": [courier.capacity or 50],
            "skills": [courier.id]
        })

    for order_id, order in valid_orders_map.items():
        service_duration = (order.time_at_point or 15) * 60
        job_skills = [order.required_courier_id] if getattr(order, 'required_courier_id', None) else ([order.courier_id] if getattr(order, 'courier_id', None) else None)
        time_windows = get_time_windows(order)
        order_type = getattr(order, 'type', 'delivery')
        
        shipment = {
            "id": order.id,
            "amount": [1]
        }
        if job_skills:
            shipment["skills"] = job_skills
        
        if order_type == 'pickup':
            # Customer -> Depot
            shipment["pickup"] = {
                "id": order.id, # Customer visit
                "location": [order.lon, order.lat],
                "service": service_duration,
                "time_windows": time_windows
            }
            shipment["delivery"] = {
                "id": order.id + 1000000, # Depot visit (dummy id)
                "location": depot_coords,
                "service": 300
            }
        else:
            # Delivery: Depot -> Customer
            shipment["pickup"] = {
                "id": order.id + 1000000, # Depot visit (dummy id)
                "location": depot_coords,
                "service": 300
            }
            shipment["delivery"] = {
                "id": order.id, # Customer visit
                "location": [order.lon, order.lat],
                "service": service_duration,
                "time_windows": time_windows
            }
        payload["shipments"].append(shipment)

    if not payload["shipments"]:
        return []

    try:
        print(f" Запуск VRP: {len(payload['shipments'])} заказов, {len(payload['vehicles'])} курьеров")
        # Direct call to bypass SDK object bugs
        response = client.request("/optimization", {}, post_json=payload)
    except Exception as e:
        print(f" Ошибка API оптимизации: {e}")
        return []

    
    results = []
    
    if 'routes' in response:
        for route in response['routes']:
            vehicle_id = route['vehicle']  
            
            
            sorted_order_ids = []
            
            # Record tracking for shipments:
            # VROOM returns 'pickup' and 'delivery' steps for shipments.
            # We want to identify the 'customer visit'.
            # Delivery order -> delivery step is at customer.
            # Pickup order -> pickup step is at customer.
            for step in route['steps']:
                if step['type'] in ['pickup', 'delivery']:
                    shipment_id = step.get('id')
                    if shipment_id in valid_orders_map:
                        order = valid_orders_map[shipment_id]
                        order_type = getattr(order, 'type', 'delivery')
                        if step['type'] == order_type:
                            sorted_order_ids.append(shipment_id)
                elif step['type'] == 'job':
                     sorted_order_ids.append(step['id'])
            
            if not sorted_order_ids:
                continue  

            results.append({
                'courier_id': vehicle_id,
                'geometry': route.get('geometry'),
                'order_ids': sorted_order_ids,
                'summary': {
                    'distance': route.get('distance', 0),
                    'duration': route.get('duration', 0)
                }
            })
            
    print(f" Успешно построено маршрутов: {len(results)}")
    return results


def geocode_address(address, country='RU'):
    if not client:
        print(f" Геокодинг недоступен: ORS клиент не инициализирован")
        return None
    
    try:
        
        results = client.pelias_search(text=address, country=country)
        
        if results and 'features' in results and results['features']:
            
            coords = results['features'][0]['geometry']['coordinates']
            lon, lat = coords[0], coords[1]
            print(f" Геокодинг успешен: {address} → [{lon}, {lat}]")
            return (lon, lat)
        else:
            print(f" Адрес не найден: {address}")
            return None
            
    except Exception as e:
        print(f" Ошибка геокодинга для адреса '{address}': {e}")
        return None


def decode_polyline(encoded):
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
