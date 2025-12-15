from flask import Flask, render_template, jsonify, request, session, url_for
from flask_cors import CORS
from dotenv import load_dotenv
import os
from functools import wraps
from datetime import datetime, timedelta
import pandas as pd
import jwt
from authlib.integrations.flask_client import OAuth


# Загрузка переменных окружения из .env файла
load_dotenv()

# Импорт моделей и оптимизатора
from models import db, User, Courier, Order, Route, Point
import optimizer

app = Flask(__name__)
CORS(app)

# Конфигурация базы данных
# Railway использует postgres://, но SQLAlchemy требует postgresql://
database_url = os.getenv('DATABASE_URL', 'sqlite:///logistics.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_TYPE'] = 'filesystem'

# Инициализация БД
db.init_app(app)

# Инициализация OAuth
oauth = OAuth(app)
oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# Создание таблиц при первом запуске
with app.app_context():
    db.create_all()
    print("✅ База данных инициализирована")
    
    # Миграция: добавление новых полей для Telegram интеграции User
    if 'postgresql' in database_url:
        from sqlalchemy import text
        try:
            db.session.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(50)'))
            db.session.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_code VARCHAR(20)'))
            db.session.commit()
            print("✅ Миграция User Telegram полей выполнена")
        except Exception as e:
            db.session.rollback()
            print(f"ℹ️  Миграция User: {e}")

# Инициализация Telegram бота (webhook режим для production)
if os.getenv('WEBHOOK_URL'):
    try:
        from bot import init_bot_webhook
        init_bot_webhook(app)
    except Exception as e:
        print(f"⚠️  Ошибка инициализации Telegram бота: {e}")


# Декоратор для проверки JWT токена с валидацией IP
def token_required(f):
    @wraps(f)
    def decorated(current_user=None, *args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'success': False, 'message': 'Токен не предоставлен'}), 401
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'success': False, 'message': 'Пользователь не найден'}), 401
            
            # Проверка IP адреса (если токен содержит IP)
            if 'ip' in data:
                client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
                if client_ip:
                    client_ip = client_ip.split(',')[0].strip()  # Берём первый IP если несколько
                if data['ip'] != client_ip:
                    return jsonify({'success': False, 'message': 'Сессия недействительна (изменился IP)'}), 401
                    
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'message': 'Токен истек'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'success': False, 'message': 'Недействительный токен'}), 401
        
        return f(current_user, *args, **kwargs)
    return decorated


# Старый декоратор для совместимости (session-based)
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Требуется авторизация'}), 401
        return f(*args, **kwargs)
    return decorated_function


def get_current_user_id():
    """
    Получает user_id из JWT токена в заголовке Authorization.
    Возвращает None если токен отсутствует или недействителен.
    Также проверяет session для обратной совместимости.
    """
    # Сначала проверяем JWT токен
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            return data.get('user_id')
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            pass
    
    # Fallback на session для обратной совместимости
    return session.get('user_id')

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
    
    # Автоматический вход после регистрации - генерация JWT токена
    # Получаем IP клиента для привязки сессии
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip:
        client_ip = client_ip.split(',')[0].strip()
    
    token = jwt.encode({
        'user_id': user.id,
        'ip': client_ip,
        'exp': datetime.utcnow() + timedelta(hours=24)  # 24 часа по умолчанию
    }, app.config['SECRET_KEY'], algorithm='HS256')
    
    return jsonify({
        'success': True,
        'message': 'Регистрация успешна',
        'token': token,
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
    
    # Определяем срок действия токена: 7 дней если "запомнить", иначе 24 часа
    remember = data.get('remember', False)
    if remember:
        token_expiry = timedelta(days=7)
    else:
        token_expiry = timedelta(hours=24)
    
    # Получаем IP клиента для привязки сессии
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip:
        client_ip = client_ip.split(',')[0].strip()  # Берём первый IP если несколько
    
    # Генерация JWT токена с IP для безопасности
    token = jwt.encode({
        'user_id': user.id,
        'ip': client_ip,
        'exp': datetime.utcnow() + token_expiry
    }, app.config['SECRET_KEY'], algorithm='HS256')
    
    return jsonify({
        'success': True,
        'message': 'Вход выполнен успешно',
        'token': token,
        'user': user.to_dict()
    })

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """
    POST /api/logout - Выход из системы
    """
    session.clear()
    return jsonify({'success': True, 'message': 'Выход выполнен'})


# ============================================
# GOOGLE OAUTH 2.0 - Вход через Google
# ============================================

@app.route('/api/login/google')
def api_login_google():
    """
    GET /api/login/google - Перенаправляет на авторизацию Google
    """
    redirect_uri = url_for('api_auth_google', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@app.route('/api/auth/google')
def api_auth_google():
    """
    GET /api/auth/google - Callback от Google OAuth
    
    Получает данные пользователя от Google, создает/находит пользователя в БД,
    генерирует JWT токен и возвращает страницу с JS-редиректом.
    """
    try:
        # Получаем токен от Google
        token = oauth.google.authorize_access_token()
        
        # Получаем информацию о пользователе
        userinfo = token.get('userinfo')
        if not userinfo:
            # Fallback: запрашиваем userinfo отдельно
            resp = oauth.google.get('https://openidconnect.googleapis.com/v1/userinfo')
            userinfo = resp.json()
        
        email = userinfo.get('email')
        if not email:
            return render_template('oauth_callback.html', error='Не удалось получить email от Google')
        
        # Проверяем существует ли пользователь
        user = User.query.filter_by(email=email).first()
        
        if not user:
            # Создаём нового пользователя
            user = User(
                email=email,
                company_name=userinfo.get('name', email.split('@')[0]),
                phone=''
            )
            # Генерируем случайный пароль-заглушку (пользователь не сможет войти по паролю)
            import secrets
            user.set_password(secrets.token_urlsafe(32))
            
            db.session.add(user)
            db.session.commit()
            print(f"✅ Создан новый пользователь через Google OAuth: {email}")
        
        # Генерируем JWT токен (как в обычном логине)
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        jwt_token = jwt.encode({
            'user_id': user.id,
            'ip': client_ip,
            'exp': datetime.utcnow() + timedelta(days=7)  # 7 дней для OAuth
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        return render_template('oauth_callback.html', token=jwt_token, error=None)
        
    except Exception as e:
        print(f"❌ Ошибка Google OAuth: {e}")
        return render_template('oauth_callback.html', error=str(e), token=None)

@app.route('/api/user/current', methods=['GET'])
@token_required
def api_current_user(current_user):
    """
    GET /api/user/current - Получение данных текущего пользователя
    Требует JWT токен в заголовке Authorization: Bearer <token>
    """
    return jsonify({
        'success': True,
        'user': current_user.to_dict()
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
        user_id = get_current_user_id()
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
            user_id=get_current_user_id(),
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

@app.route('/api/orders/import', methods=['POST'])
def import_orders():
    """
    POST /api/orders/import - Импорт заказов из Excel файла
    
    Формат файла: .xlsx или .xls
    Обязательные колонки: Название, Адрес, Дата, Время, Имя клиента, Телефон
    Требуется: point_id (ID точки отправления) в form data
    
    Возвращает:
    {
        "success": true,
        "message": "Импортировано: N",
        "count": N
    }
    """
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Файл не найден'}), 400
    
    # Получаем point_id из формы
    point_id = request.form.get('point_id')
    if not point_id:
        return jsonify({'success': False, 'message': 'Выберите точку отправления'}), 400
    
    try:
        point_id = int(point_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Некорректный ID точки отправления'}), 400
    
    file = request.files['file']
    
    if not file.filename:
        return jsonify({'success': False, 'message': 'Файл не выбран'}), 400
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'message': 'Поддерживаются только Excel файлы (.xlsx, .xls)'}), 400
    
    try:
        # Чтение Excel файла
        df = pd.read_excel(file)
        
        # Проверка обязательных колонок
        required_columns = ['Название', 'Адрес', 'Дата', 'Время', 'Имя клиента', 'Телефон']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return jsonify({
                'success': False,
                'message': f'Отсутствуют обязательные колонки: {", ".join(missing_columns)}'
            }), 400
        
        count = 0
        user_id = get_current_user_id()
        
        for _, row in df.iterrows():
            addr = str(row['Адрес']).strip()
            lat, lon = None, None
            
            # Попытка геокодирования адреса
            try:
                coords = optimizer.geocode_address(addr)
                if coords:
                    lon, lat = coords[0], coords[1]
            except Exception as geo_error:
                print(f"⚠️  Ошибка геокодинга для адреса '{addr}': {geo_error}")
            
            # Обработка даты
            visit_date = str(row['Дата'])
            if ' ' in visit_date:
                visit_date = visit_date.split(' ')[0]
            
            # Создание заказа с привязкой к точке, без курьера (для VRP)
            new_order = Order(
                user_id=user_id,
                point_id=point_id,           # Привязываем к выбранному складу
                courier_id=None,             # Оставляем пустым для авто-распределения VRP
                order_name=str(row['Название']).strip(),
                address=addr,
                destination_point=addr,
                visit_date=visit_date,
                visit_time=str(row['Время']).strip(),
                recipient_name=str(row['Имя клиента']).strip(),
                recipient_phone=str(row['Телефон']).strip(),
                lat=lat,
                lon=lon,
                status='planned'
            )
            
            db.session.add(new_order)
            count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Импортировано: {count}',
            'count': count
        })
        
    except Exception as e:
        print(f"❌ Ошибка импорта Excel: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Ошибка чтения файла: {str(e)}'}), 500

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
        user_id = get_current_user_id()
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
        
        # Генерируем название маршрута
        user_id = get_current_user_id()
        if user_id:
            routes_count = Route.query.filter_by(user_id=user_id).count()
        else:
            routes_count = Route.query.count()
        route_name = data.get('name') or f'Маршрут #{routes_count + 1}'
        
        # Создание маршрута с привязкой к текущему пользователю
        route = Route(
            user_id=user_id,
            courier_id=data['courier_id'],
            name=route_name,
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
        
        return jsonify({'success': True, 'id': route.id, 'name': route_name, 'message': 'Маршрут создан'})

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
    POST /api/routes/optimize - Группировка и расчет маршрутов (VRP)
    Заказы группируются по точкам отправки (point_id)
    """
    data = request.json
    
    # 1. Получаем параметры
    date = data.get('date')
    if not date:
        return jsonify({'success': False, 'message': 'Не указана дата'}), 400
    
    user_id = get_current_user_id()
    
    # 2. Собираем данные из БД - курьеры
    if user_id:
        couriers = Courier.query.filter_by(user_id=user_id).all()
    else:
        couriers = Courier.query.all()
    
    if not couriers:
        return jsonify({'success': False, 'message': 'Нет доступных курьеров. Добавьте курьеров в разделе "Курьеры".'}), 400

    # 3. Берем все нераспределенные заказы на эту дату
    orders_query = Order.query.filter_by(
        visit_date=date,
        status='planned',
        route_id=None
    )
    if user_id:
        orders_query = orders_query.filter_by(user_id=user_id)
    orders = orders_query.all()
    
    if not orders:
        return jsonify({'success': False, 'message': 'Нет свободных заказов на эту дату'}), 400

    # 4. Группируем заказы по point_id (точкам отправки)
    orders_by_point = {}
    default_point = None
    
    # Получаем дефолтную точку отправки
    if user_id:
        default_point = Point.query.filter_by(user_id=user_id, is_primary=True).first()
        if not default_point:
            default_point = Point.query.filter_by(user_id=user_id).first()
    else:
        default_point = Point.query.filter_by(is_primary=True).first()
        if not default_point:
            default_point = Point.query.first()
    
    for order in orders:
        # Определяем точку отправки для заказа
        if order.point_id:
            point = Point.query.get(order.point_id)
            if point and point.latitude and point.longitude:
                point_key = order.point_id
            else:
                point_key = 'default'
        else:
            point_key = 'default'
        
        if point_key not in orders_by_point:
            orders_by_point[point_key] = []
        orders_by_point[point_key].append(order)
    
    # 5. Для каждой группы запускаем VRP
    created_routes_ids = []
    errors = []
    used_courier_ids = set()  # Отслеживаем уже использованных курьеров
    
    for point_key, group_orders in orders_by_point.items():
        # Определяем депо для этой группы
        if point_key == 'default':
            if not default_point or not default_point.latitude or not default_point.longitude:
                errors.append(f'Нет точки отправки для {len(group_orders)} заказов без указанной точки')
                continue
            depot_coords = {'lat': default_point.latitude, 'lon': default_point.longitude}
            depot_id = default_point.id
        else:
            point = Point.query.get(point_key)
            depot_coords = {'lat': point.latitude, 'lon': point.longitude}
            depot_id = point.id
        
        # Фильтруем курьеров - исключаем уже использованных
        available_couriers = [c for c in couriers if c.id not in used_courier_ids]
        
        if not available_couriers:
            errors.append(f'Нет свободных курьеров для точки {point_key} ({len(group_orders)} заказов)')
            continue
        
        # Запускаем VRP для этой группы
        try:
            routes_data = optimizer.solve_vrp(group_orders, available_couriers, depot_coords)
        except Exception as e:
            print(f"Ошибка VRP для точки {point_key}: {e}")
            errors.append(f'Ошибка оптимизации для точки {point_key}')
            continue
        
        if not routes_data:
            errors.append(f'Не удалось построить маршрут для {len(group_orders)} заказов')
            continue
        
        # Сохраняем результаты в БД
        for route_info in routes_data:
            # Отмечаем курьера как использованного
            used_courier_ids.add(route_info['courier_id'])
            
            # Генерируем название маршрута
            if user_id:
                routes_count = Route.query.filter_by(user_id=user_id).count()
            else:
                routes_count = Route.query.count()
            route_name = f'Маршрут #{routes_count + 1 + len(created_routes_ids)}'
            
            new_route = Route(
                user_id=user_id,
                courier_id=route_info['courier_id'],
                name=route_name,
                date=date,
                status='active',
                geometry=route_info['geometry']
            )
            db.session.add(new_route)
            db.session.flush()
            
            created_routes_ids.append(new_route.id)
            
            # Привязываем заказы к маршруту
            for order_id in route_info['order_ids']:
                order = Order.query.get(order_id)
                if order:
                    order.route_id = new_route.id
                    order.status = 'planned'
    
    db.session.commit()
    
    if not created_routes_ids and errors:
        return jsonify({'success': False, 'message': '; '.join(errors)}), 400
    
    message = f'Сформировано маршрутов: {len(created_routes_ids)}'
    if errors:
        message += f' (Предупреждения: {"; ".join(errors)})'
    
    return jsonify({
        'success': True,
        'message': message,
        'routes_ids': created_routes_ids
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
    
    route = Route.query.get(route_id)
    if not route:
        return jsonify({'success': False, 'message': 'Маршрут не найден'}), 404
    
    # Получаем новый порядок заказов
    new_order_ids = data.get('orders', [])
    
    if not new_order_ids:
        return jsonify({'success': False, 'message': 'Не указан порядок заказов'}), 400
    
    # Открепляем все текущие заказы от маршрута и сбрасываем позицию
    for order in route.orders:
        order.route_id = None
        order.route_position = None
    
    # Привязываем заказы в новом порядке с указанием позиции
    for position, order_id in enumerate(new_order_ids):
        order = Order.query.get(order_id)
        if order:
            order.route_id = route_id
            order.route_position = position
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Порядок заказов обновлён', 'route_id': route_id})

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
    
    # Определяем точку отправки (Депо) для этого маршрута
    # Берем point_id из первого заказа в маршруте
    depot_lat = None
    depot_lon = None
    depot_address = None
    
    if route.orders:
        first_order = route.orders[0]
        if first_order.point_id:
            depot = Point.query.get(first_order.point_id)
            if depot and depot.latitude and depot.longitude:
                depot_lat = depot.latitude
                depot_lon = depot.longitude
                depot_address = depot.address
    
    # Fallback на основную точку пользователя
    if not depot_lat and route.user_id:
        depot = Point.query.filter_by(user_id=route.user_id, is_primary=True).first()
        if not depot:
            depot = Point.query.filter_by(user_id=route.user_id).first()
        if depot and depot.latitude and depot.longitude:
            depot_lat = depot.latitude
            depot_lon = depot.longitude
            depot_address = depot.address
    
    # Подготовка данных для визуализации (сортируем по позиции в маршруте)
    orders_data = []
    sorted_orders = sorted(route.orders, key=lambda o: (o.route_position is None, o.route_position or 0))
    for order in sorted_orders:
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
            'start_lat': depot_lat,
            'start_lon': depot_lon
        },
        'depot': {
            'lat': depot_lat,
            'lon': depot_lon,
            'address': depot_address
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
        user_id = get_current_user_id()
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
            user_id=get_current_user_id(),
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
        
        # Генерируем код авторизации для Telegram-бота
        auth_code = courier.generate_auth_code()
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'id': courier.id, 
            'auth_code': auth_code,
            'message': 'Курьер добавлен'
        })


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

@app.route('/api/couriers/<int:courier_id>/regenerate-code', methods=['POST'])
def api_courier_regenerate_code(courier_id):
    """
    POST /api/couriers/<id>/regenerate-code - Генерация нового кода авторизации
    
    Возвращает:
    {
        "success": true,
        "auth_code": "ABC123",
        "message": "Код обновлен"
    }
    """
    courier = Courier.query.get(courier_id)
    if not courier:
        return jsonify({'success': False, 'message': 'Курьер не найден'}), 404
    
    # Сбрасываем привязку Telegram при регенерации кода
    courier.telegram_chat_id = None
    auth_code = courier.generate_auth_code(force=True)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'auth_code': auth_code,
        'message': 'Код обновлен'
    })


@app.route('/api/couriers/locations', methods=['GET'])
def api_courier_locations():
    """
    GET /api/couriers/locations - Получение геолокаций активных курьеров
    
    Query параметры (опционально):
    - route_id: фильтр по конкретному маршруту
    
    Возвращает:
    {
        "couriers": [
            {
                "id": number,
                "full_name": "string",
                "vehicle_type": "car|truck|bicycle|scooter",
                "lat": number,
                "lon": number,
                "is_on_shift": boolean,
                "current_order": "string|null"
            }
        ]
    }
    """
    user_id = get_current_user_id()
    route_id = request.args.get('route_id', None, type=int)
    
    # Базовый запрос - только курьеры на смене с координатами
    if user_id:
        query = Courier.query.filter_by(user_id=user_id)
    else:
        query = Courier.query
    
    # Фильтруем только тех, у кого есть координаты
    query = query.filter(
        Courier.current_lat.isnot(None),
        Courier.current_lon.isnot(None),
        Courier.is_on_shift == True
    )
    
    # Если указан route_id, фильтруем по курьерам с активными маршрутами
    if route_id:
        route = Route.query.get(route_id)
        if route:
            query = query.filter_by(id=route.courier_id)
    
    couriers = query.all()
    
    result = []
    for courier in couriers:
        # Находим текущий заказ курьера
        current_order = None
        for route in courier.routes:
            if route.status == 'active':
                for order in route.orders:
                    if order.status == 'in_progress':
                        current_order = order.order_name
                        break
                    elif order.status == 'planned' and not current_order:
                        current_order = f"{order.order_name} (ожидает)"
                if current_order:
                    break
        
        result.append({
            'id': courier.id,
            'full_name': courier.full_name,
            'vehicle_type': courier.vehicle_type,
            'lat': courier.current_lat,
            'lon': courier.current_lon,
            'is_on_shift': courier.is_on_shift,
            'current_order': current_order
        })
    
    return jsonify({'couriers': result})


@app.route('/api/routes/<int:route_id>/send', methods=['POST'])
def api_route_send(route_id):
    """
    POST /api/routes/<id>/send - Отправка маршрута водителю в Telegram
    
    Возвращает:
    {
        "success": true,
        "message": "Маршрут отправлен курьеру {Имя}"
    }
    """
    from telegram_utils import send_route_to_driver
    
    result = send_route_to_driver(route_id)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400

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
        user_id = get_current_user_id()
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
        
        # Получаем координаты из запроса или геокодируем адрес
        latitude = data.get('latitude') or data.get('lat')
        longitude = data.get('longitude') or data.get('lon')
        
        if not latitude or not longitude:
            # Геокодируем адрес для получения координат
            coords = optimizer.geocode_address(address)
            if coords:
                longitude, latitude = coords  # geocode_address возвращает (lon, lat)
            
        # Если make_primary=true, снимаем флаг с других точек этого пользователя
        user_id = get_current_user_id()
        make_primary = data.get('make_primary', False)
        if make_primary:
            Point.query.filter_by(user_id=user_id).update({Point.is_primary: False})
            
        point = Point(
            user_id=user_id,
            address=address,
            is_primary=make_primary,
            latitude=latitude,
            longitude=longitude
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
        
        # Если адрес изменился, обновляем и координаты
        if 'address' in data:
            point.address = data['address']
            # Если новые координаты не переданы, геокодируем новый адрес
            if 'latitude' not in data and 'longitude' not in data:
                coords = optimizer.geocode_address(data['address'])
                if coords:
                    point.longitude, point.latitude = coords
            
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
    # Получение текущего пользователя из JWT токена или сессии
    user = None
    
    # Сначала проверяем JWT токен
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            user = User.query.get(data['user_id'])
            # Проверка IP если есть в токене
            if user and 'ip' in data:
                client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
                if client_ip:
                    client_ip = client_ip.split(',')[0].strip()
                if data['ip'] != client_ip:
                    user = None  # IP изменился, сессия недействительна
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            user = None
    
    # Fallback на сессию если нет JWT
    if not user and 'user_id' in session:
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
            return jsonify({'success': False, 'message': 'Требуется авторизация'}), 401
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
    # Получаем текущего пользователя из JWT
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': 'Требуется авторизация'}), 401
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404
    
    data = request.json or {}
    
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')
    
    # Проверка обязательных полей
    if not current_password or not new_password or not confirm_password:
        return jsonify({'success': False, 'message': 'Заполните все поля'}), 400
    
    # Проверка текущего пароля
    if not user.check_password(current_password):
        return jsonify({'success': False, 'message': 'Неверный текущий пароль'}), 400
    
    # Проверка совпадения паролей
    if new_password != confirm_password:
        return jsonify({'success': False, 'message': 'Новые пароли не совпадают'}), 400
    
    # Проверка минимальной длины
    if len(new_password) < 6:
        return jsonify({'success': False, 'message': 'Пароль должен содержать минимум 6 символов'}), 400
    
    # Сохраняем новый пароль
    user.set_password(new_password)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Пароль успешно обновлен'})


@app.route('/api/account/telegram-link', methods=['GET'])
def api_account_telegram_link():
    """
    GET /api/account/telegram-link - Генерация ссылки для привязки Telegram
    
    Требует аутентификации (токен в заголовке Authorization)
    
    Возвращает:
    {
        "success": true,
        "link": "https://t.me/yoroutebot?start=COMPLEX_CODE",
        "code": "COMPLEX_CODE",
        "telegram_connected": false
    }
    """
    # Получаем текущего пользователя из JWT
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'message': 'Требуется авторизация'}), 401
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404
    
    # Проверяем, привязан ли уже Telegram
    if user.telegram_chat_id:
        return jsonify({
            'success': True,
            'telegram_connected': True,
            'message': 'Telegram уже привязан к аккаунту'
        })
    
    # Генерируем новый код авторизации
    code = user.generate_auth_code(force=True)
    db.session.commit()
    
    # Получаем имя бота из переменных окружения
    bot_name = os.getenv('TG_BOT_NAME', 'yoroutebot')
    link = f"https://t.me/{bot_name}?start={code}"
    
    return jsonify({
        'success': True,
        'link': link,
        'code': code,
        'telegram_connected': False
    })

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
