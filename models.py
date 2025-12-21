"""
yo.route - Database Models
SQLAlchemy модели для базы данных логистического приложения
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    """Модель пользователя/компании"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    company_name = db.Column(db.String(200))
    activity = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Telegram интеграция для владельца
    telegram_chat_id = db.Column(db.String(50), nullable=True)  # ID чата Telegram владельца
    auth_code = db.Column(db.String(20), unique=True, nullable=True)  # Код авторизации для бота
    
    # Relationships
    couriers = db.relationship('Courier', backref='user', lazy=True, cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='user', lazy=True, cascade='all, delete-orphan')
    routes = db.relationship('Route', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Хеширование и сохранение пароля"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Проверка пароля"""
        return check_password_hash(self.password_hash, password)
    
    def generate_auth_code(self, force=False):
        """
        Генерация 12-значного кода авторизации для Telegram-бота.
        Код содержит буквы, цифры и спецсимволы.
        
        Args:
            force: Если True, генерирует новый код даже если старый существует
        """
        import random
        import string
        
        if self.auth_code and not force:
            return self.auth_code
        
        # Генерируем уникальный код
        chars = string.ascii_letters + string.digits + "!@#$%&*?"
        max_attempts = 10
        
        for _ in range(max_attempts):
            code = ''.join(random.choice(chars) for _ in range(12))
            # Проверяем уникальность среди User и Courier
            existing_user = User.query.filter_by(auth_code=code).first()
            from models import Courier
            existing_courier = Courier.query.filter_by(auth_code=code).first()
            if (not existing_user or existing_user.id == self.id) and not existing_courier:
                self.auth_code = code
                return code
        
        # Fallback с timestamp
        import time
        code = ''.join(random.choice(chars) for _ in range(10)) + str(int(time.time()) % 100).zfill(2)
        self.auth_code = code
        return code
    
    def to_dict(self):
        """Сериализация в словарь для JSON (без пароля)"""
        return {
            'id': self.id,
            'email': self.email,
            'company_name': self.company_name,
            'activity': self.activity,
            'phone': self.phone,
            'telegram_chat_id': self.telegram_chat_id,
            'telegram_connected': bool(self.telegram_chat_id),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<User {self.email}>'


class UserSettings(db.Model):
    """Настройки рабочего пространства пользователя"""
    __tablename__ = 'user_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    
    # Внешний вид
    theme = db.Column(db.String(20), default='light')  # light, dark
    
    # Рабочее пространство
    default_page = db.Column(db.String(50), default='orders')  # orders, optimization, points
    planning_mode = db.Column(db.String(20), default='manual')  # manual, smart
    courier_notifications = db.Column(db.String(10), default='off')  # on, off
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связь с пользователем
    user = db.relationship('User', backref=db.backref('settings', uselist=False))
    
    def to_dict(self):
        """Сериализация настроек в словарь"""
        return {
            'theme': self.theme or 'light',
            'default_page': self.default_page or 'orders',
            'planning_mode': self.planning_mode or 'manual',
            'courier_notifications': self.courier_notifications or 'off'
        }
    
    def __repr__(self):
        return f'<UserSettings user_id={self.user_id}>'


class Courier(db.Model):
    """Модель курьера"""
    __tablename__ = 'couriers'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(50), unique=True)
    telegram = db.Column(db.String(100))
    
    # Тип транспорта для отображения (car, truck, bicycle, scooter)
    vehicle_type = db.Column(db.String(50), default='car')
    
    # Профиль транспорта для OpenRouteService
    # driving-car, driving-hgv, cycling-regular, cycling-road, cycling-mountain, foot-walking, foot-hiking
    profile = db.Column(db.String(50), default='driving-car')
    
    # Грузоподъемность/вместимость
    capacity = db.Column(db.Integer, default=100)
    
    # Координаты стартовой точки (склад/депо)
    start_lat = db.Column(db.Float, default=55.7558)  # Москва по умолчанию
    start_lon = db.Column(db.Float, default=37.6173)
    
    auth_key = db.Column(db.String(255))
    
    # Telegram интеграция
    auth_code = db.Column(db.String(6), unique=True, nullable=True)  # 6-значный код авторизации
    telegram_chat_id = db.Column(db.String(50), nullable=True)  # ID чата Telegram
    
    # Live-трекинг курьера
    current_lat = db.Column(db.Float, nullable=True)  # Текущая широта
    current_lon = db.Column(db.Float, nullable=True)  # Текущая долгота
    is_on_shift = db.Column(db.Boolean, default=False)  # Статус смены (на линии / не на линии)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    routes = db.relationship('Route', backref='courier', lazy=True)
    
    def generate_auth_code(self, force=False):
        """
        Генерация 12-значного кода авторизации для Telegram-бота.
        Код содержит буквы, цифры и спецсимволы.
        
        Args:
            force: Если True, генерирует новый код даже если старый существует
        """
        import random
        import string
        
        if self.auth_code and not force:
            return self.auth_code
        
        # Генерируем уникальный код
        chars = string.ascii_letters + string.digits + "!@#$%&*?"
        max_attempts = 10
        
        for _ in range(max_attempts):
            code = ''.join(random.choice(chars) for _ in range(12))
            # Проверяем уникальность среди Courier (User проверяется отдельно)
            existing_courier = Courier.query.filter_by(auth_code=code).first()
            if not existing_courier or existing_courier.id == self.id:
                self.auth_code = code
                return code
        
        # Fallback с timestamp
        import time
        code = ''.join(random.choice(chars) for _ in range(10)) + str(int(time.time()) % 100).zfill(2)
        self.auth_code = code
        return code
    
    def __repr__(self):
        return f'<Courier {self.full_name}>'

    
    def to_dict(self):
        """Сериализация в словарь для JSON"""
        # Находим текущий активный заказ курьера
        current_order = None
        
        # Проверяем заказы в активных маршрутах курьера
        for route in self.routes:
            if route.status == 'active':
                for order in route.orders:
                    if order.status == 'in_progress':
                        current_order = order.order_name
                        break
                if current_order:
                    break
        
        # Если нет активного, показываем первый заказ в активном маршруте
        if not current_order:
            for route in self.routes:
                if route.status == 'active' and route.orders:
                    current_order = f"{route.orders[0].order_name} (ожидает)"
                    break
        
        return {
            'id': self.id,
            'full_name': self.full_name,
            'phone': self.phone,
            'telegram': self.telegram,
            'vehicle_type': self.vehicle_type,
            'profile': self.profile,
            'capacity': self.capacity,
            'start_lat': self.start_lat,
            'start_lon': self.start_lon,
            'current_lat': self.current_lat,
            'current_lon': self.current_lon,
            'is_on_shift': self.is_on_shift,
            'current_order': current_order,
            'auth_code': self.auth_code,
            'telegram_chat_id': self.telegram_chat_id,
            'telegram_connected': bool(self.telegram_chat_id),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }



class Order(db.Model):
    """Модель заказа"""
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Основная информация
    order_name = db.Column(db.String(100), nullable=False)
    destination_point = db.Column(db.String(200))
    address = db.Column(db.String(200), nullable=False)
    
    # Координаты (заполняются через геокодинг)
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    
    # Дата и время
    visit_date = db.Column(db.String(20))
    visit_time = db.Column(db.String(20))
    time_at_point = db.Column(db.Integer, default=15)  # минуты
    
    # Получатель
    recipient_name = db.Column(db.String(100))
    recipient_phone = db.Column(db.String(50))
    
    # Дополнительная информация
    comment = db.Column(db.Text)
    company = db.Column(db.String(200))
    
    # Статус: planned, in_progress, completed, failed
    status = db.Column(db.String(20), default='planned')
    
    # Фото-отчет (Proof of Delivery)
    proof_image = db.Column(db.String(255), nullable=True)  # Путь к файлу фото подтверждения
    
    # Причина отказа (если статус failed)
    failure_reason = db.Column(db.String(255), nullable=True)
    
    # Прямое закрепление курьера за заказом
    courier_id = db.Column(db.Integer, db.ForeignKey('couriers.id'), nullable=True)
    
    # Точка отправления
    point_id = db.Column(db.Integer, db.ForeignKey('points.id'), nullable=True)
    
    # Привязка к маршруту
    route_id = db.Column(db.Integer, db.ForeignKey('routes.id'), nullable=True)
    
    # Позиция заказа в маршруте (для сохранения порядка)
    route_position = db.Column(db.Integer, nullable=True)
    
    # Тип заказа: delivery (доставка) или pickup (забор)
    type = db.Column(db.String(20), default='delivery')
    
    # Жесткая привязка к конкретному курьеру/машине (для VRP Skills)
    required_courier_id = db.Column(db.Integer, db.ForeignKey('couriers.id'), nullable=True)
    
    # Временное окно доставки (формат HH:MM)
    time_window_start = db.Column(db.String(5), nullable=True)
    time_window_end = db.Column(db.String(5), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Order {self.order_name}>'
    
    def to_dict(self):
        """Сериализация в словарь для JSON"""
        # Получаем имя курьера из прямой связи или через маршрут
        courier_name = None
        if self.courier_id:
            courier = Courier.query.get(self.courier_id)
            if courier:
                courier_name = courier.full_name
        elif self.route_id and self.route and self.route.courier:
            courier_name = self.route.courier.full_name
        
        # Получаем адрес точки отправки
        point_address = None
        if self.point_id:
            point = Point.query.get(self.point_id)
            if point:
                point_address = point.address
        
        return {
            'id': self.id,
            'order_name': self.order_name,
            'destination_point': self.destination_point,
            'address': self.address,
            'lat': self.lat,
            'lon': self.lon,
            'visit_date': self.visit_date,
            'visit_time': self.visit_time,
            'time_at_point': self.time_at_point,
            'recipient_name': self.recipient_name,
            'recipient_phone': self.recipient_phone,
            'comment': self.comment,
            'company': self.company,
            'status': self.status,
            'proof_image': self.proof_image,
            'failure_reason': self.failure_reason,
            'courier_id': self.courier_id,
            'point_id': self.point_id,
            'point_address': point_address,
            'route_id': self.route_id,
            'courier_name': courier_name,
            'type': self.type or 'delivery',
            'required_courier_id': self.required_courier_id,
            'time_window_start': self.time_window_start,
            'time_window_end': self.time_window_end,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Route(db.Model):
    """Модель маршрута"""
    __tablename__ = 'routes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    courier_id = db.Column(db.Integer, db.ForeignKey('couriers.id'), nullable=False)
    
    # Название маршрута (автогенерируется)
    name = db.Column(db.String(100))
    
    date = db.Column(db.String(20), nullable=False)
    
    # Статус: active, completed
    status = db.Column(db.String(20), default='active')
    
    # Геометрия маршрута (encoded polyline от OpenRouteService)
    geometry = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    orders = db.relationship('Order', backref='route', lazy=True)
    
    def __repr__(self):
        return f'<Route {self.id} - Courier {self.courier_id} - {self.date}>'
    
    def to_dict(self):
        """Сериализация в словарь для JSON"""
        current_order = None
        if self.orders:
            # Находим первый незавершенный заказ или последний
            for order in self.orders:
                if order.status != 'completed':
                    current_order = {
                        'order_id': order.id,
                        'order_name': order.order_name,
                        'status': order.status
                    }
                    break
            if not current_order and self.orders:
                last_order = self.orders[-1]
                current_order = {
                    'order_id': last_order.id,
                    'order_name': last_order.order_name,
                    'status': last_order.status
                }
        
        return {
            'id': self.id,
            'name': self.name or f'Маршрут #{self.id}',
            'courier_id': self.courier_id,
            'courier_name': self.courier.full_name if self.courier else None,
            'vehicle_type': self.courier.vehicle_type if self.courier else 'car',
            'date': self.date,
            'status': self.status,
            'current_order': current_order,
            'orders': [order.id for order in self.orders],
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Point(db.Model):
    """Модель точки отправки"""
    __tablename__ = 'points'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    address = db.Column(db.String(200), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)
    
    # Координаты
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Point {self.address}>'
    
    def to_dict(self):
        """Сериализация в словарь для JSON"""
        return {
            'id': self.id,
            'address': self.address,
            'is_primary': self.is_primary,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
