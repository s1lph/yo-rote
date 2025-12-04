"""
yo.route - API Endpoints для Backend интеграции

Все endpoints готовы для интеграции с backend базой данных.
В каждом endpoint есть TODO комментарии с описанием необходимых операций с БД.

Структура базы данных (рекомендуемая):

Таблицы:
1. users - Пользователи/компании
   - id (PK)
   - email (unique)
   - password_hash
   - company_name
   - activity
   - phone
   - created_at
   - updated_at

2. points - Точки отправки
   - id (PK)
   - user_id (FK -> users.id)
   - address
   - is_primary (boolean)
   - latitude (optional)
   - longitude (optional)
   - created_at
   - updated_at

3. couriers - Курьеры
   - id (PK)
   - user_id (FK -> users.id)
   - full_name
   - phone (unique)
   - telegram
   - vehicle_type (enum: car, truck, bicycle, scooter)
   - auth_key
   - created_at
   - updated_at

4. orders - Заказы
   - id (PK)
   - user_id (FK -> users.id)
   - order_name
   - destination_point
   - point_address
   - visit_date
   - visit_time
   - time_at_point
   - recipient_name
   - recipient_phone
   - comment
   - status (enum: planned, in_progress, completed)
   - company
   - created_at
   - updated_at

5. routes - Маршруты
   - id (PK)
   - user_id (FK -> users.id)
   - courier_id (FK -> couriers.id)
   - date
   - status (enum: active, completed)
   - created_at
   - updated_at

6. route_orders - Связь маршрутов и заказов (many-to-many)
   - route_id (FK -> routes.id)
   - order_id (FK -> orders.id)

7. settings - Настройки компании
   - id (PK)
   - user_id (FK -> users.id, unique)
   - company_name
   - timezone
   - visit_time
   - delivery_time
   - created_at
   - updated_at

8. sessions - Сессии пользователей (для JWT или сессионных токенов)
   - id (PK)
   - user_id (FK -> users.id)
   - token
   - expires_at
   - created_at

Все endpoints возвращают JSON и используют стандартные HTTP методы:
- GET - получение данных
- POST - создание новой записи
- PUT - обновление существующей записи
- DELETE - удаление записи
"""

from flask import Flask, render_template, jsonify, request, session
from flask_cors import CORS
from dotenv import load_dotenv
import os
from functools import wraps

# Загрузка переменных окружения из .env файла
load_dotenv()

# Импорт моделей и оптимизатора
from models import db, User, Courier, Order, Route, Point
import optimizer

app = Flask(__name__)
CORS(app)

# Конфигурация базы данных
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///logistics.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_TYPE'] = 'filesystem'

# Инициализация БД
db.init_app(app)

# Создание таблиц при первом запуске
with app.app_context():
    db.create_all()
    print("✅ База данных инициализирована")


# Декоратор для проверки аутентификации
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Требуется авторизация'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Главная страница - редирект на вход или дашборд
@app.route('/')
def index():
    return render_template('index.html')

# Страница входа
@app.route('/login')
def login():
    return render_template('login.html')

# Страница регистрации
@app.route('/registration')
def registration():
    return render_template('registration.html')

# Страница заказов (создание заказа)
@app.route('/orders')
def orders():
    return render_template('orders.html')

# Страница оптимизации
@app.route('/optimization')
def optimization():
    return render_template('optimization.html')

# Страница точек отправки
@app.route('/points')
def points():
    return render_template('points.html')

# Страница курьеров
@app.route('/couriers')
def couriers():
    return render_template('couriers.html')

# Страница настроек
@app.route('/settings')
def settings():
    return render_template('settings.html')

# Страница настроек аккаунта
@app.route('/account')
def account():
    return render_template('account.html')

# ============================================
# AUTHENTICATION API - Регистрация и вход
# ============================================

@app.route('/api/register', methods=['POST'])
def api_register():
    """
    POST /api/register - Регистрация новой компании
    
    Тело запроса:
    {
        "company_name": "string",
        "activity": "string",
        "email": "string",
        "phone": "string",
        "password": "string",
        "terms": boolean
    }
    """
    data = request.json or {}
    
    # Валидация
    if not data.get('email'):
        return jsonify({'success': False, 'message': 'Email обязателен'}), 400
    if not data.get('password'):
        return jsonify({'success': False, 'message': 'Пароль обязателен'}), 400
    if not data.get('company_name'):
        return jsonify({'success': False, 'message': 'Название компании обязательно'}), 400
    if not data.get('terms'):
        return jsonify({'success': False, 'message': 'Необходимо принять условия использования'}), 400
    
    # Проверка существования пользователя
    existing_user = User.query.filter_by(email=data['email']).first()
    if existing_user:
        return jsonify({'success': False, 'message': 'Пользователь с такой почтой уже существует'}), 400
    
    # Создание нового пользователя
    user = User(
        email=data['email'],
        company_name=data['company_name'],
        activity=data.get('activity', ''),
        phone=data.get('phone', '')
    )
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    # Автоматический вход после регистрации
    session['user_id'] = user.id
    session['user_email'] = user.email
    
    return jsonify({
        'success': True,
        'message': 'Регистрация успешна',
        'user': user.to_dict()
    })

@app.route('/api/login', methods=['POST'])
def api_login():
    """
    POST /api/login - Вход в систему
    
    Тело запроса:
    {
        "email": "string",
        "password": "string",
        "remember": boolean
    }
    """
    data = request.json or {}
    
    email = data.get('email', '')
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'success': False, 'message': 'Пожалуйста, заполните все поля'}), 400
    
    # Поиск пользователя
    user = User.query.filter_by(email=email).first()
    
    # Проверка пароля
    if not user or not user.check_password(password):
        return jsonify({'success': False, 'message': 'Неверный email или пароль'}), 401
    
    # Создание сессии
    session['user_id'] = user.id
    session['user_email'] = user.email
    
    if data.get('remember'):
        session.permanent = True
    
    return jsonify({
        'success': True,
        'message': 'Вход выполнен успешно',
        'user': user.to_dict()
    })

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """
    POST /api/logout - Выход из системы
    """
    session.clear()
    return jsonify({'success': True, 'message': 'Выход выполнен'})

@app.route('/api/user/current', methods=['GET'])
def api_current_user():
    """
    GET /api/user/current - Получение данных текущего пользователя
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'}), 401
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404
    
    return jsonify({
        'success': True,
        'user': user.to_dict()
     })

# ============================================
# GEOCODING & ROUTING API - Автокомплит и предпросмотр маршрутов
# ============================================

@app.route('/api/geocode/search', methods=['GET'])
def api_geocode_search():
    """
    GET /api/geocode/search - Поиск адресов для автокомплита
    
    Query параметры:
    - q: поисковый запрос (строка адреса)
    - limit: максимальное количество результатов (default: 8)
    
    Возвращает:
    {
        "suggestions": [
            {
                "label": "Красная площадь, Москва",
                "lat": 55.7558,
                "lon": 37.6173
            }
        ]
    }
    """
    query = request.args.get('q', '')
    limit = request.args.get('limit', 8, type=int)
    
    if not query or len(query) < 3:
        return jsonify({'suggestions': []})
    
    try:
        # Вызов OpenRouteService Pelias Search API
        import openrouteservice
        client = openrouteservice.Client(key=os.getenv('ORS_API_KEY', ''))
        
        results = client.pelias_search(text=query, country='RU', size=limit)
        
        suggestions = []
        if results and 'features' in results:
            for feature in results['features']:
                coords = feature['geometry']['coordinates']
                label = feature['properties'].get('label', query)
                
                suggestions.append({
                    'label': label,
                    'lon': coords[0],
                    'lat': coords[1]
                })
        
        return jsonify({'suggestions': suggestions})
    
    except Exception as e:
        print(f"Ошибка геокодинга: {e}")
        return jsonify({'suggestions': [], 'error': str(e)}), 500

@app.route('/api/routes/preview', methods=['POST'])
def api_route_preview():
    """
    POST /api/routes/preview - Предпросмотр маршрута между двумя точками
    
    Тело запроса:
    {
        "origin_lat": number,
        "origin_lon": number,
        "destination_lat": number,
        "destination_lon": number,
        "profile": "driving-car" (optional)
    }
    
    Возвращает:
    {
        "geometry": "encoded polyline",
        "distance": number (метры),
        "duration": number (секунды)
    }
    """
    data = request.json or {}
    
    # Валидация
    required_fields = ['origin_lat', 'origin_lon', 'destination_lat', 'destination_lon']
    for field in required_fields:
        if field not in data:
            return jsonify({'success': False, 'message': f'Поле {field} обязательно'}), 400
    
    try:
        import openrouteservice
        client = openrouteservice.Client(key=os.getenv('ORS_API_KEY', ''))
        
        # Координаты в формате [lon, lat]
        coords = [
            [data['origin_lon'], data['origin_lat']],
            [data['destination_lon'], data['destination_lat']]
        ]
        
        profile = data.get('profile', 'driving-car')
        
        # Запрос маршрута через OpenRouteService Directions API
        route = client.directions(
            coordinates=coords,
            profile=profile,
            format='geojson',
            geometry=True
        )
        
        if route and 'features' in route and route['features']:
            feature = route['features'][0]
            geometry = feature['geometry']['coordinates']
            properties = feature['properties']
            summary = properties.get('summary', {})
            
            # Конвертируем координаты в encoded polyline
            # Для упрощения возвращаем просто массив координат
            path = [[coord[1], coord[0]] for coord in geometry]  # [lat, lon]
            
            return jsonify({
                'success': True,
                'path': path,
                'distance': summary.get('distance', 0),  # метры
                'duration': summary.get('duration', 0)   # секунды
            })
        else:
            return jsonify({'success': False, 'message': 'Не удалось построить маршрут'}), 500
    
    except Exception as e:
        print(f"Ошибка построения маршрута: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================
# ORDERS API - Работа с заказами
# ============================================

@app.route('/api/orders', methods=['GET', 'POST'])
def api_orders():
    """
    GET /api/orders - Получение списка заказов
    
    Query параметры (опционально):
    - page: номер страницы (default: 1)
    - limit: количество на странице (default: 50)
    - status: фильтр по статусу (planned, in_progress, completed)
    - date_from: фильтр с даты (YYYY-MM-DD)
    - date_to: фильтр до даты (YYYY-MM-DD)
    - search: поиск по адресу/получателю
    
    Возвращает:
    {
        "orders": [
            {
                "id": number,
                "order_name": "string",
                "destination_point": "string",
                "point_address": "string",
                "visit_date": "YYYY-MM-DD",
                "visit_time": "HH:MM",
                "time_at_point": number,
                "recipient_name": "string",
                "recipient_phone": "string",
                "comment": "string",
                "courier_id": number|null,
                "courier_name": "string|null",
                "status": "planned|in_progress|completed",
                "company": "string",
                "created_at": "ISO datetime",
                "updated_at": "ISO datetime"
            }
        ],
        "total": number,
        "page": number,
        "limit": number
    }

    order_name является обязательным полем и используется как основной идентификатор заказа во всех интерфейсах.
    """
    if request.method == 'GET':
        # Получение параметров запроса
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        status = request.args.get('status', None)
        visit_date = request.args.get('visit_date', None)
        search = request.args.get('search', None)
        
        # Базовый запрос - фильтрация по текущему пользователю
        user_id = session.get('user_id')
        if user_id:
            query = Order.query.filter_by(user_id=user_id)
        else:
            query = Order.query  # Для неавторизованных - все данные
        
        # Применение фильтров
        if status:
            query = query.filter_by(status=status)
        if visit_date:
            query = query.filter_by(visit_date=visit_date)
        if search:
            query = query.filter(
                (Order.order_name.like(f'%{search}%')) |
                (Order.address.like(f'%{search}%')) |
                (Order.recipient_name.like(f'%{search}%'))
            )
        
        # Пагинация
        total = query.count()
        orders = query.offset((page - 1) * limit).limit(limit).all()
        
        return jsonify({
            'orders': [order.to_dict() for order in orders],
            'total': total,
            'page': page,
            'limit': limit
        })
    else:
        """
        POST /api/orders - Создание нового заказа
        
        Тело запроса:
        {
            "order_name": "string",
            "destination_point": "string",
            "point_address": "string",
            "visit_date": "YYYY-MM-DD",
            "visit_time": "HH:MM",
            "time_at_point": number,
            "recipient_name": "string",
            "recipient_phone": "string",
            "comment": "string",
            "courier_id": number|null
        }
        
        Возвращает:
        {
            "success": true,
            "id": number,
            "message": "Заказ создан"
        }
        """
        data = request.json or {}
        
        # Валидация обязательных полей
        if not data.get('order_name'):
            return jsonify({'success': False, 'message': 'Название заказа обязательно'}), 400
        
        address = data.get('destination_point') or data.get('address')
        if not address:
            return jsonify({'success': False, 'message': 'Адрес обязателен'}), 400
        
        # Преобразование courier_id и point_id в int, если они есть
        courier_id = None
        if data.get('courier_id'):
            try:
                courier_id = int(data['courier_id'])
            except (ValueError, TypeError):
                courier_id = None
        
        point_id = None
        if data.get('point_id'):
            try:
                point_id = int(data['point_id'])
            except (ValueError, TypeError):
                point_id = None
        
        # Создание заказа с привязкой к текущему пользователю
        order = Order(
            user_id=session.get('user_id'),
            order_name=data.get('order_name'),
            destination_point=data.get('destination_point', ''),
            address=address,
            visit_date=data.get('visit_date'),
            visit_time=data.get('visit_time'),
            time_at_point=data.get('time_at_point', 15),
            recipient_name=data.get('recipient_name'),
            recipient_phone=data.get('recipient_phone'),
            comment=data.get('comment'),
            company=data.get('company'),
            courier_id=courier_id,
            point_id=point_id,
            status='planned'
        )
        
        # Если координаты уже переданы с фронтенда, используем их
        if data.get('destination_lat') and data.get('destination_lon'):
            try:
                order.lat = float(data['destination_lat'])
                order.lon = float(data['destination_lon'])
            except (ValueError, TypeError):
                pass
        
        # Если координат нет, пробуем геокодировать
        if not order.lat or not order.lon:
            coords = optimizer.geocode_address(address)
            if coords:
                order.lon, order.lat = coords[0], coords[1]
            else:
                # Если геокодирование не удалось, все равно создаем заказ
                print(f"⚠️  Заказ создан без координат: {address}")
        
        db.session.add(order)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'id': order.id,
            'message': 'Заказ создан',
            'lat': order.lat,
            'lon': order.lon
        })

@app.route('/api/orders/<int:order_id>', methods=['GET', 'DELETE', 'PUT'])
def api_order(order_id):
    """
    GET /api/orders/<id> - Получение конкретного заказа
    
    Возвращает:
    {
        "id": number,
        "order_name": "string",
        "destination_point": "string",
        "point_address": "string",
        "visit_date": "YYYY-MM-DD",
        "visit_time": "HH:MM",
        "time_at_point": number,
        "recipient_name": "string",
        "recipient_phone": "string",
        "comment": "string",
        "status": "planned|in_progress|completed",
        "company": "string",
        "created_at": "ISO datetime",
        "updated_at": "ISO datetime"
    }
    """
    if request.method == 'GET':
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'success': False, 'message': 'Заказ не найден'}), 404
        return jsonify({'success': True, 'order': order.to_dict()})
    elif request.method == 'DELETE':
        """
        DELETE /api/orders/<id> - Удаление заказа
        
        Возвращает:
        {
            "success": true,
            "message": "Заказ удален"
        }
        """
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'success': False, 'message': 'Заказ не найден'}), 404
        
        db.session.delete(order)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Заказ удален'})
    else:
        """
        PUT /api/orders/<id> - Обновление заказа
        
        Тело запроса (все поля опциональны):
        {
            "order_name": "string",
            "destination_point": "string",
            "point_address": "string",
            "visit_date": "YYYY-MM-DD",
            "visit_time": "HH:MM",
            "time_at_point": number,
            "recipient_name": "string",
            "recipient_phone": "string",
            "comment": "string",
            "status": "planned|in_progress|completed",
            "courier_id": number|null
        }
        
        Возвращает:
        {
            "success": true,
            "message": "Заказ обновлен"
        }
        """
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'success': False, 'message': 'Заказ не найден'}), 404
        
        data = request.json
        
        # Обновление полей
        if 'order_name' in data:
            order.order_name = data['order_name']
        
        if 'address' in data or 'destination_point' in data:
            new_address = data.get('destination_point') or data.get('address')
            order.address = new_address
            order.destination_point = data.get('destination_point', new_address)
            
            # Используем координаты с фронтенда если они есть
            if data.get('destination_lat') and data.get('destination_lon'):
                try:
                    order.lat = float(data['destination_lat'])
                    order.lon = float(data['destination_lon'])
                except (ValueError, TypeError):
                    pass
            else:
                # Иначе перегеокодируем адрес
                coords = optimizer.geocode_address(new_address)
                if coords:
                    order.lon, order.lat = coords[0], coords[1]
        
        if 'visit_date' in data:
            order.visit_date = data['visit_date']
        if 'visit_time' in data:
            order.visit_time = data['visit_time']
        if 'time_at_point' in data:
            order.time_at_point = data['time_at_point']
        if 'status' in data:
            order.status = data['status']
        if 'comment' in data:
            order.comment = data['comment']
        if 'recipient_name' in data:
            order.recipient_name = data['recipient_name']
        if 'recipient_phone' in data:
            order.recipient_phone = data['recipient_phone']
        if 'company' in data:
            order.company = data['company']
        
        # Обработка courier_id
        if 'courier_id' in data:
            if data['courier_id']:
                try:
                    order.courier_id = int(data['courier_id'])
                except (ValueError, TypeError):
                    order.courier_id = None
            else:
                order.courier_id = None
        
        # Обработка point_id
        if 'point_id' in data:
            if data['point_id']:
                try:
                    order.point_id = int(data['point_id'])
                except (ValueError, TypeError):
                    order.point_id = None
            else:
                order.point_id = None
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Заказ обновлен'})

@app.route('/api/orders/batch', methods=['DELETE', 'PUT'])
def api_orders_batch():
    """
    DELETE /api/orders/batch - Массовое удаление заказов
    
    Тело запроса:
    {
        "ids": [number, number, ...]
    }
    
    Возвращает:
    {
        "success": true,
        "deleted_count": number,
        "message": "Заказы удалены"
    }
    """
    if request.method == 'DELETE':
        data = request.json
        ids = data.get('ids', [])
        
        if not ids:
            return jsonify({'success': False, 'message': 'Не указаны ID заказов'}), 400
        
        deleted_count = Order.query.filter(Order.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': 'Заказы удалены'
        })
    else:
        """
        PUT /api/orders/batch - Массовое обновление заказов
        
        Тело запроса:
        {
            "ids": [number, number, ...],
            "updates": {
                "status": "planned|in_progress|completed",
                // другие поля для обновления
            }
        }
        
        Возвращает:
        {
            "success": true,
            "updated_count": number,
            "message": "Заказы обновлены"
        }
        """
        # TODO: Валидация данных
        # TODO: Массовое обновление заказов в БД
        data = request.json
        ids = data.get('ids', [])
        return jsonify({
            'success': True,
            'updated_count': len(ids),
            'message': 'Заказы обновлены'
        })

# ============================================
# COURIER ASSIGNMENTS API - Привязка заказов к курьерам
# ============================================

@app.route('/api/courier-assignments', methods=['GET', 'POST'])
def api_courier_assignments():
    """
    GET /api/courier-assignments - Получение списка назначений заказов курьерам
    
    Query параметры (опционально):
    - courier_id: фильтр по курьеру
    - order_id: фильтр по заказу
    - status: active|completed
    - date: YYYY-MM-DD (по дате назначения)
    
    Возвращает:
    {
        "assignments": [
            {
                "id": number,
                "courier_id": number,
                "courier_name": "string",
                "order_id": number,
                "order_name": "string",
                "status": "active|completed",
                "assigned_at": "ISO datetime",
                "completed_at": "ISO datetime|null"
            }
        ]
    }
    """
    if request.method == 'GET':
        # TODO: Получение назначений из БД с учетом фильтров
        return jsonify({'assignments': []})
    else:
        """
        POST /api/courier-assignments - Создание/обновление назначения
        
        Тело запроса:
        {
            "courier_id": number,
            "order_id": number,
            "status": "active",
            "assigned_at": "ISO datetime (optional, default now)"
        }
        
        Возвращает:
        {
            "success": true,
            "id": number,
            "message": "Заказ закреплен за курьером"
        }
        """
        data = request.json
        # TODO: Проверка что заказ и курьер существуют
        # TODO: Проверка что заказ не закреплен за другим активным курьером
        # TODO: Сохранение назначения в БД
        return jsonify({'success': True, 'id': 1, 'message': 'Заказ закреплен за курьером'})

@app.route('/api/courier-assignments/<int:assignment_id>', methods=['PUT', 'DELETE'])
def api_courier_assignment(assignment_id):
    if request.method == 'PUT':
        """
        PUT /api/courier-assignments/<id> - Обновление назначения
        
        Тело запроса:
        {
            "status": "active|completed",
            "completed_at": "ISO datetime (optional)"
        }
        
        Возвращает:
        {
            "success": true,
            "message": "Назначение обновлено"
        }
        """
        data = request.json
        # TODO: Обновление назначения (смена статуса, завершение маршрута и т.д.)
        return jsonify({'success': True, 'message': 'Назначение обновлено'})
    else:
        """
        DELETE /api/courier-assignments/<id> - Снятие назначения
        
        Возвращает:
        {
            "success": true,
            "message": "Назначение удалено"
        }
        """
        # TODO: Удаление записи назначения (или пометка как отменено)
        return jsonify({'success': True, 'message': 'Назначение удалено'})

# ============================================
# ROUTES API - Работа с маршрутами
# ============================================

@app.route('/api/routes', methods=['GET', 'POST'])
def api_routes():
    """
    GET /api/routes - Получение списка маршрутов
    
    Query параметры (опционально):
    - date: фильтр по дате (YYYY-MM-DD)
    - courier_id: фильтр по курьеру
    - status: фильтр по статусу (active, completed)
    
    Возвращает:
    {
        "routes": [
            {
                "id": number,
                "courier_id": number,
                "courier_name": "string",
                "date": "YYYY-MM-DD",
                "orders": [number, ...],  # массив ID заказов
                "current_order": {
                    "order_id": number,
                    "order_name": "string",
                    "status": "planned|in_progress|completed"
                },
                "status": "active|completed",
                "created_at": "ISO datetime",
                "updated_at": "ISO datetime"
            }
        ]
    }
    """
    if request.method == 'GET':
        # Получение параметров фильтрации
        date = request.args.get('date', None)
        courier_id = request.args.get('courier_id', None, type=int)
        status = request.args.get('status', None)
        
        # Базовый запрос - фильтрация по текущему пользователю
        user_id = session.get('user_id')
        if user_id:
            query = Route.query.filter_by(user_id=user_id)
        else:
            query = Route.query  # Для неавторизованных - все данные
        
        # Применение фильтров
        if date:
            query = query.filter_by(date=date)
        if courier_id:
            query = query.filter_by(courier_id=courier_id)
        if status:
            query = query.filter_by(status=status)
        
        routes = query.all()
        
        return jsonify({
            'routes': [route.to_dict() for route in routes]
        })
    else:
        """
        POST /api/routes - Создание нового маршрута
        
        Тело запроса:
        {
            "courier_id": number,
            "date": "YYYY-MM-DD",
            "orders": [number, ...],  # массив ID заказов
            "status": "active"
        }
        
        Возвращает:
        {
            "success": true,
            "id": number,
            "message": "Маршрут создан"
        }
        """
        data = request.json
        
        if not data.get('courier_id') or not data.get('date'):
            return jsonify({'success': False, 'message': 'Не указан курьер или дата'}), 400
        
        courier = Courier.query.get(data['courier_id'])
        if not courier:
            return jsonify({'success': False, 'message': 'Курьер не найден'}), 404
        
        # Создание маршрута с привязкой к текущему пользователю
        route = Route(
            user_id=session.get('user_id'),
            courier_id=data['courier_id'],
            date=data['date'],
            status=data.get('status', 'active')
        )
        
        db.session.add(route)
        db.session.commit()
        
        # Привязка заказов если указаны
        if 'orders' in data and data['orders']:
            for order_id in data['orders']:
                order = Order.query.get(order_id)
                if order:
                    order.route_id = route.id
            db.session.commit()
        
        return jsonify({'success': True, 'id': route.id, 'message': 'Маршрут создан'})

@app.route('/api/routes/<int:route_id>', methods=['GET', 'PUT', 'DELETE'])
def api_route(route_id):
    """
    GET /api/routes/<id> - Получение конкретного маршрута
    
    Возвращает:
    {
        "id": number,
        "courier_id": number,
        "courier_name": "string",
        "date": "YYYY-MM-DD",
        "orders": [number, ...],
        "status": "active|completed",
        "created_at": "ISO datetime",
        "updated_at": "ISO datetime"
    }
    """
    if request.method == 'GET':
        route = Route.query.get(route_id)
        if not route:
            return jsonify({'success': False, 'message': 'Маршрут не найден'}), 404
        return jsonify(route.to_dict())
    elif request.method == 'PUT':
        """
        PUT /api/routes/<id> - Обновление маршрута
        
        Тело запроса:
        {
            "courier_id": number,
            "orders": [number, ...],
            "status": "active|completed"
        }
        
        Возвращает:
        {
            "success": true,
            "message": "Маршрут обновлен"
        }
        """
        route = Route.query.get(route_id)
        if not route:
            return jsonify({'success': False, 'message': 'Маршрут не найден'}), 404
        
        data = request.json
        
        if 'status' in data:
            route.status = data['status']
        if 'courier_id' in data:
            route.courier_id = data['courier_id']
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Маршрут обновлен'})
    else:
        """
        DELETE /api/routes/<id> - Удаление маршрута
        
        Возвращает:
        {
            "success": true,
            "message": "Маршрут удален"
        }
        """
        route = Route.query.get(route_id)
        if not route:
            return jsonify({'success': False, 'message': 'Маршрут не найден'}), 404
        
        # Открепляем заказы от маршрута
        for order in route.orders:
            order.route_id = None
        
        db.session.delete(route)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Маршрут удален'})

@app.route('/api/routes/optimize', methods=['POST'])
def api_routes_optimize():
    """
    POST /api/routes/optimize - Запуск скрипта оптимизации маршрутов
    
    Тело запроса:
    {
        "date": "YYYY-MM-DD",
        "orders": [number, ...],      # массив ID заказов для оптимизации
        "couriers": [number, ...],    # массив ID курьеров
        "strategy": "string"          # (опционально) стратегия оптимизации
    }
    
    Возвращает:
    {
        "success": true,
        "message": "Оптимизация запущена",
        "task_id": "string",
        "estimated_time": "string",
        "preview_route_id": number    # ID маршрута, который можно открыть на карте
    }
    """
    data = request.json
    
    # Валидация входных данных
    if not data.get('date'):
        return jsonify({'success': False, 'message': 'Не указана дата'}), 400
    
    date = data['date']
    courier_id = data.get('courier_id')
    user_id = session.get('user_id')
    
    # Если курьер не указан, берем первого доступного курьера текущего пользователя
    if not courier_id:
        if user_id:
            courier = Courier.query.filter_by(user_id=user_id).first()
        else:
            courier = Courier.query.first()  # Для неавторизованных - любой курьер
        if not courier:
            return jsonify({'success': False, 'message': 'Нет доступных курьеров'}), 400
        courier_id = courier.id
    else:
        courier = Courier.query.get(courier_id)
        if not courier:
            return jsonify({'success': False, 'message': 'Курьер не найден'}), 404
    
    # Выборка нераспределенных заказов на дату для текущего пользователя
    orders_query = Order.query.filter_by(
        visit_date=date,
        route_id=None,
        status='planned'
    )
    if user_id:
        orders_query = orders_query.filter_by(user_id=user_id)
    # Для неавторизованных - все заказы без фильтрации по user_id
    orders = orders_query.all()
    
    if not orders:
        return jsonify({
            'success': False,
            'message': 'Нет нераспределенных заказов на указанную дату'
        }), 400
    
    # Вызов оптимизатора
    geometry, sorted_orders = optimizer.build_route(orders, courier)
    
    if not geometry or not sorted_orders:
        return jsonify({
            'success': False,
            'message': 'Не удалось построить маршрут. Проверьте настройки ORS API.'
        }), 500
    
    # Создание маршрута в БД с привязкой к текущему пользователю
    route = Route(
        user_id=user_id,
        courier_id=courier.id,
        date=date,
        status='active',
        geometry=geometry
    )
    
    db.session.add(route)
    db.session.commit()
    
    # Привязка заказов к маршруту в оптимальном порядке
    for order in sorted_orders:
        order.route_id = route.id
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Маршрут оптимизирован',
        'route_id': route.id,
        'orders_count': len(sorted_orders),
        'preview_route_id': route.id
    })

@app.route('/api/routes/<int:route_id>/edit', methods=['POST'])
def api_route_edit(route_id):
    """
    POST /api/routes/<id>/edit - Изменение маршрута вручную
    
    Тело запроса:
    {
        "orders": [number, ...],      # новый порядок заказов
        "notes": "string"             # комментарий диспетчера
    }
    
    Возвращает:
    {
        "success": true,
        "message": "Маршрут обновлен вручную",
        "route_id": number
    }
    """
    data = request.json
    # TODO: Сохранить изменения порядка заказов, зафиксировать комментарий
    return jsonify({'success': True, 'message': 'Маршрут обновлен вручную', 'route_id': route_id})

@app.route('/api/routes/<int:route_id>/optimize-view', methods=['GET'])
def api_route_optimize_view(route_id):
    """
    GET /api/routes/<id>/optimize-view - Получение данных для визуализации маршрута на карте
    
    Возвращает:
    {
        "route_id": number,
        "courier": {
            "id": number,
            "full_name": "string"
        },
        "orders": [
            {
                "order_id": number,
                "order_name": "string",
                "address": "string",
                "lat": number,
                "lng": number,
                "status": "planned|in_progress|completed"
            }
        ],
        "path": [
            {
                "lat": number,
                "lng": number
            }
        ]
    }
    """
    route = Route.query.get(route_id)
    if not route:
        return jsonify({'success': False, 'message': 'Маршрут не найден'}), 404
    
    # Подготовка данных для визуализации
    orders_data = []
    for order in route.orders:
        if order.lat and order.lon:
            orders_data.append({
                'order_id': order.id,
                'order_name': order.order_name,
                'address': order.address,
                'lat': order.lat,
                'lng': order.lon,
                'status': order.status
            })
    
    # Декодирование геометрии маршрута в координаты
    path = []
    if route.geometry:
        try:
            decoded = optimizer.decode_polyline(route.geometry)
            path = [{'lat': coord[0], 'lng': coord[1]} for coord in decoded]
        except Exception as e:
            print(f"Ошибка декодирования polyline: {e}")
    
    return jsonify({
        'route_id': route.id,
        'courier': {
            'id': route.courier.id,
            'full_name': route.courier.full_name,
            'start_lat': route.courier.start_lat,
            'start_lon': route.courier.start_lon
        },
        'orders': orders_data,
        'path': path,
        'geometry': route.geometry  # также отдаем encoded для фронтенда
    })

# ============================================
# COURIERS API - Работа с курьерами
# ============================================

@app.route('/api/couriers', methods=['GET', 'POST'])
def api_couriers():
    """
    GET /api/couriers - Получение списка курьеров
    
    Возвращает:
    {
        "couriers": [
            {
                "id": number,
                "full_name": "string",
                "phone": "string",
                "telegram": "string",
                "vehicle_type": "car|truck|bicycle|scooter",
                "auth_key": "string (замаскированный)",
                "current_order": {
                    "order_id": number,
                    "order_name": "string",
                    "status": "planned|in_progress|completed"
                },
                "created_at": "ISO datetime",
                "updated_at": "ISO datetime"
            }
        ]
    }
    """
    if request.method == 'GET':
        # Фильтрация по текущему пользователю
        user_id = session.get('user_id')
        if user_id:
            couriers = Courier.query.filter_by(user_id=user_id).all()
        else:
            couriers = Courier.query.all()  # Для неавторизованных - все данные
        return jsonify({
            'couriers': [courier.to_dict() for courier in couriers]
        })
    else:
        """
        POST /api/couriers - Добавление курьера
        
        Тело запроса:
        {
            "full_name": "string",
            "phone": "string",
            "telegram": "string",
            "vehicle_type": "car|truck|bicycle|scooter",
            "auth_key": "string"
        }
        
        Возвращает:
        {
            "success": true,
            "id": number,
            "message": "Курьер добавлен"
        }
        
        При ошибке:
        {
            "success": false,
            "message": "Курьер с таким телефоном уже существует"
        }
        """
        data = request.json
        
        if not data.get('full_name'):
            return jsonify({'success': False, 'message': 'Имя курьера обязательно'}), 400
        
        # Проверка уникальности телефона
        if data.get('phone'):
            existing = Courier.query.filter_by(phone=data['phone']).first()
            if existing:
                return jsonify({'success': False, 'message': 'Курьер с таким телефоном уже существует'}), 400
        
        courier = Courier(
            user_id=session.get('user_id'),
            full_name=data['full_name'],
            phone=data.get('phone'),
            telegram=data.get('telegram'),
            vehicle_type=data.get('vehicle_type', 'car'),
            auth_key=data.get('auth_key'),
            profile=data.get('profile', 'driving-car'),
            capacity=data.get('capacity', 100),
            start_lat=data.get('start_lat', 55.7558),
            start_lon=data.get('start_lon', 37.6173)
        )
        
        db.session.add(courier)
        db.session.commit()
        
        return jsonify({'success': True, 'id': courier.id, 'message': 'Курьер добавлен'})

@app.route('/api/couriers/<int:courier_id>', methods=['GET', 'PUT', 'DELETE'])
def api_courier(courier_id):
    """
    GET /api/couriers/<id> - Получение конкретного курьера
    
    Возвращает:
    {
        "id": number,
        "full_name": "string",
        "phone": "string",
        "telegram": "string",
        "vehicle_type": "car|truck|bicycle|scooter",
        "auth_key": "string (замаскированный)",
        "created_at": "ISO datetime",
        "updated_at": "ISO datetime"
    }
    """
    if request.method == 'GET':
        courier = Courier.query.get(courier_id)
        if not courier:
            return jsonify({'success': False, 'message': 'Курьер не найден'}), 404
        return jsonify(courier.to_dict())
    elif request.method == 'PUT':
        """
        PUT /api/couriers/<id> - Обновление курьера
        
        Тело запроса (все поля опциональны):
        {
            "full_name": "string",
            "phone": "string",
            "telegram": "string",
            "vehicle_type": "car|truck|bicycle|scooter",
            "auth_key": "string"
        }
        
        Возвращает:
        {
            "success": true,
            "message": "Курьер обновлен"
        }
        """
        courier = Courier.query.get(courier_id)
        if not courier:
            return jsonify({'success': False, 'message': 'Курьер не найден'}), 404
        
        data = request.json
        
        if 'full_name' in data:
            courier.full_name = data['full_name']
        if 'phone' in data:
            courier.phone = data['phone']
        if 'telegram' in data:
            courier.telegram = data['telegram']
        if 'vehicle_type' in data:
            courier.vehicle_type = data['vehicle_type']
        if 'auth_key' in data:
            courier.auth_key = data['auth_key']
        if 'profile' in data:
            courier.profile = data['profile']
        if 'capacity' in data:
            courier.capacity = data['capacity']
        if 'start_lat' in data:
            courier.start_lat = data['start_lat']
        if 'start_lon' in data:
            courier.start_lon = data['start_lon']
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Курьер обновлен'})
    else:
        """
        DELETE /api/couriers/<id> - Удаление курьера
        
        Возвращает:
        {
            "success": true,
            "message": "Курьер удален"
        }
        """
        courier = Courier.query.get(courier_id)
        if not courier:
            return jsonify({'success': False, 'message': 'Курьер не найден'}), 404
        
        # Проверка активных маршрутов
        active_routes = Route.query.filter_by(courier_id=courier_id, status='active').count()
        if active_routes > 0:
            return jsonify({
                'success': False,
                'message': f'Нельзя удалить курьера с активными маршрутами ({active_routes})'
            }), 400
        
        db.session.delete(courier)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Курьер удален'})

# ============================================
# POINTS API - Работа с точками отправки
# ============================================

@app.route('/api/points', methods=['GET', 'POST'])
def api_points():
    """
    GET /api/points - Получение списка точек отправки
    
    Возвращает:
    {
        "points": [
            {
                "id": number,
                "address": "string",
                "is_primary": boolean,
                "latitude": number (опционально),
                "longitude": number (опционально),
                "created_at": "ISO datetime",
                "updated_at": "ISO datetime"
            }
        ]
    }
    """
    if request.method == 'GET':
        # Фильтрация по текущему пользователю
        user_id = session.get('user_id')
        if user_id:
            points = Point.query.filter_by(user_id=user_id).all()
        else:
            points = Point.query.all()  # Для неавторизованных - все данные
        return jsonify({'points': [point.to_dict() for point in points]})
    else:
        """
        POST /api/points - Добавление точки отправки
        
        Тело запроса:
        {
            "address": "string",
            "make_primary": boolean,
            "latitude": number (опционально),
            "longitude": number (опционально)
        }
        
        Возвращает:
        {
            "success": true,
            "id": number,
            "message": "Точка добавлена"
        }
        
        При ошибке:
        {
            "success": false,
            "message": "Точка с таким адресом уже существует"
        }
        """
        data = request.json
        address = data.get('address')
        if not address:
            return jsonify({'success': False, 'message': 'Адрес обязателен'}), 400
            
        # Если make_primary=true, снимаем флаг с других точек этого пользователя
        user_id = session.get('user_id')
        make_primary = data.get('make_primary', False)
        if make_primary:
            Point.query.filter_by(user_id=user_id).update({Point.is_primary: False})
            
        point = Point(
            user_id=user_id,
            address=address,
            is_primary=make_primary,
            latitude=data.get('latitude') or data.get('lat'),
            longitude=data.get('longitude') or data.get('lon')
        )
        
        db.session.add(point)
        db.session.commit()
        
        return jsonify({'success': True, 'id': point.id, 'message': 'Точка добавлена'})

@app.route('/api/points/<int:point_id>', methods=['GET', 'PUT', 'DELETE'])
def api_point(point_id):
    """
    GET /api/points/<id> - Получение конкретной точки
    
    Возвращает:
    {
        "id": number,
        "address": "string",
        "is_primary": boolean,
        "latitude": number,
        "longitude": number,
        "created_at": "ISO datetime",
        "updated_at": "ISO datetime"
    }
    """
    if request.method == 'GET':
        point = Point.query.get(point_id)
        if not point:
            return jsonify({'success': False, 'message': 'Точка не найдена'}), 404
        return jsonify({'success': True, 'point': point.to_dict()})
    elif request.method == 'PUT':
        """
        PUT /api/points/<id> - Обновление точки отправки
        
        Тело запроса (все поля опциональны):
        {
            "address": "string",
            "make_primary": boolean,
            "latitude": number,
            "longitude": number
        }
        
        Возвращает:
        {
            "success": true,
            "message": "Точка обновлена"
        }
        """
        point = Point.query.get(point_id)
        if not point:
            return jsonify({'success': False, 'message': 'Точка не найдена'}), 404
            
        data = request.json
        
        if 'address' in data:
            point.address = data['address']
            
        if 'make_primary' in data:
            make_primary = data['make_primary']
            point.is_primary = make_primary
            if make_primary:
                # Снимаем флаг с других точек этого пользователя
                Point.query.filter(Point.id != point_id, Point.user_id == point.user_id).update({Point.is_primary: False})
                
        if 'latitude' in data:
            point.latitude = data['latitude']
        if 'longitude' in data:
            point.longitude = data['longitude']
            
        db.session.commit()
        return jsonify({'success': True, 'message': 'Точка обновлена'})
    else:
        """
        DELETE /api/points/<id> - Удаление точки отправки
        
        Возвращает:
        {
            "success": true,
            "message": "Точка удалена"
        }
        
        При ошибке:
        {
            "success": false,
            "message": "Нельзя удалить основную точку" или "Точка используется в заказах"
        }
        """
        point = Point.query.get(point_id)
        if not point:
            return jsonify({'success': False, 'message': 'Точка не найдена'}), 404
            
        if point.is_primary:
             # Проверяем, есть ли другие точки
            other_points_count = Point.query.filter(Point.id != point_id).count()
            if other_points_count > 0:
                 return jsonify({'success': False, 'message': 'Нельзя удалить основную точку, назначьте другую точку основной'}), 400
        
        db.session.delete(point)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Точка удалена'})

# ============================================
# SETTINGS API - Работа с настройками
# ============================================

@app.route('/api/settings', methods=['GET', 'PUT'])
def api_settings():
    """
    GET /api/settings - Получение настроек компании
    
    Возвращает:
    {
        "settings": {
            "theme": "light|dark",
            "default_page": "orders|optimization|points",
            "planning_mode": "manual|smart",
            "courier_notifications": "on|off"
        }
    }
    """
    if request.method == 'GET':
        # TODO: Получение настроек из БД для текущего пользователя
        return jsonify({
            'settings': {
                'theme': 'light',
                'default_page': 'orders',
                'planning_mode': 'manual',
                'courier_notifications': 'off'
            }
        })
    else:
        """
        PUT /api/settings - Обновление настроек
        
        Тело запроса (все поля опциональны):
        {
            "theme": "light|dark",
            "default_page": "orders|optimization|points",
            "planning_mode": "manual|smart",
            "courier_notifications": "on|off"
        }
        
        Возвращает:
        {
            "success": true,
            "message": "Настройки обновлены"
        }
        """
        # TODO: Валидация данных
        # TODO: Обновление настроек в БД
        data = request.json
        return jsonify({'success': True, 'message': 'Настройки обновлены'})

# ============================================
# ACCOUNT API - Настройки аккаунта
# ============================================

@app.route('/api/account/profile', methods=['GET', 'PUT'])
def api_account_profile():
    """
    GET /api/account/profile - Получение профиля компании
    
    Возвращает:
    {
        "profile": {
            "company_name": "string",
            "email": "string",
            "phone": "string",
            "activity": "string"
        }
    }
    """
    # Получение текущего пользователя из сессии
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    
    if request.method == 'GET':
        if user:
            return jsonify({
                'profile': {
                    'company_name': user.company_name or '',
                    'email': user.email or '',
                    'phone': user.phone or '',
                    'activity': user.activity or ''
                }
            })
        else:
            return jsonify({
                'profile': {
                    'company_name': '',
                    'email': '',
                    'phone': '',
                    'activity': ''
                }
            })
    else:
        """
        PUT /api/account/profile - Обновление данных профиля
        
        Тело запроса (все поля опциональны):
        {
            "company_name": "string",
            "email": "string",
            "phone": "string",
            "activity": "string"
        }
        """
        if not user:
            return jsonify({'success': False, 'message': 'Требуется авторизация'}), 401
        
        data = request.json or {}
        
        # Обновление данных профиля
        if 'company_name' in data:
            user.company_name = data['company_name']
        if 'email' in data:
            user.email = data['email']
        if 'phone' in data:
            user.phone = data['phone']
        if 'activity' in data:
            user.activity = data['activity']
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Профиль обновлен'})

@app.route('/api/account/security', methods=['PUT'])
def api_account_security():
    """
    PUT /api/account/security - Обновление настроек безопасности
    
    Тело запроса:
    {
        "current_password": "string",
        "new_password": "string",
        "confirm_password": "string"
    }
    
    Возвращает:
    {
        "success": true,
        "message": "Пароль обновлен"
    }
    """
    # TODO: Проверка текущего пароля
    # TODO: Валидация нового пароля
    # TODO: Сохранение нового пароля в БД
    data = request.json
    return jsonify({'success': True, 'message': 'Пароль обновлен'})

# ============================================
# USER API - Работа с пользователем
# ============================================

@app.route('/api/user', methods=['GET', 'PUT'])
def api_user():
    """
    GET /api/user - Получение данных текущего пользователя
    
    Требует аутентификации (токен в заголовке Authorization)
    
    Возвращает:
    {
        "id": number,
        "email": "string",
        "company_name": "string",
        "activity": "string",
        "phone": "string",
        "created_at": "ISO datetime"
    }
    """
    if request.method == 'GET':
        # TODO: Проверка токена аутентификации
        # TODO: Получение данных пользователя из БД
        return jsonify({
            'id': 1,
            'email': '',
            'company_name': '',
            'activity': '',
            'phone': ''
        })
    else:
        """
        PUT /api/user - Обновление данных пользователя
        
        Тело запроса (все поля опциональны):
        {
            "email": "string",
            "phone": "string",
            "company_name": "string",
            "activity": "string"
        }
        
        Возвращает:
        {
            "success": true,
            "message": "Данные обновлены"
        }
        """
        # TODO: Проверка токена аутентификации
        # TODO: Валидация данных
        # TODO: Обновление данных пользователя в БД
        data = request.json
        return jsonify({'success': True, 'message': 'Данные обновлены'})
if __name__ == '__main__':
    app.run(debug=True, port=5000)
