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
    
    def to_dict(self):
        """Сериализация в словарь для JSON (без пароля)"""
        return {
            'id': self.id,
            'email': self.email,
            'company_name': self.company_name,
            'activity': self.activity,
            'phone': self.phone,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<User {self.email}>'


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    routes = db.relationship('Route', backref='courier', lazy=True)
    
    def __repr__(self):
        return f'<Courier {self.full_name}>'
    
    def to_dict(self):
        """Сериализация в словарь для JSON"""
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
    
    # Статус: planned, in_progress, completed
    status = db.Column(db.String(20), default='planned')
    
    # Прямое закрепление курьера за заказом
    courier_id = db.Column(db.Integer, db.ForeignKey('couriers.id'), nullable=True)
    
    # Точка отправления
    point_id = db.Column(db.Integer, db.ForeignKey('points.id'), nullable=True)
    
    # Привязка к маршруту
    route_id = db.Column(db.Integer, db.ForeignKey('routes.id'), nullable=True)
    
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
            'courier_id': self.courier_id,
            'point_id': self.point_id,
            'route_id': self.route_id,
            'courier_name': courier_name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Route(db.Model):
    """Модель маршрута"""
    __tablename__ = 'routes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    courier_id = db.Column(db.Integer, db.ForeignKey('couriers.id'), nullable=False)
    
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
            'courier_id': self.courier_id,
            'courier_name': self.courier.full_name if self.courier else None,
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
