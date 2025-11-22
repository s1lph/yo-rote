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

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

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

# API endpoints для backend интеграции
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    # TODO: Интеграция с backend
    # Пример структуры данных:
    # {
    #     "email": "string",
    #     "password": "string",
    #     "remember": boolean
    # }
    # 
    # Backend должен вернуть:
    # {
    #     "success": true,
    #     "message": "Вход выполнен успешно",
    #     "token": "JWT токен или сессионный токен",
    #     "user": {
    #         "id": number,
    #         "email": "string",
    #         "company_name": "string"
    #     }
    # }
    # 
    # При ошибке:
    # {
    #     "success": false,
    #     "message": "Неверная почта или пароль"
    # }
    
    # Пример проверки (заменить на реальную проверку в backend)
    email = data.get('email', '')
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'success': False, 'message': 'Пожалуйста, заполните все поля'}), 400
    
    # TODO: Проверка email и password в базе данных через backend
    # TODO: Генерация JWT токена или сессии
    # TODO: Возврат данных пользователя
    
    return jsonify({
        'success': True,
        'message': 'Вход выполнен успешно',
        'token': 'example_token_here',  # Заменить на реальный токен из backend
        'user': {
            'id': 1,
            'email': email,
            'company_name': 'Example Company'
        }
    })

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.json
    # TODO: Интеграция с backend
    # Пример структуры данных:
    # {
    #     "company_name": "string",
    #     "activity": "string",
    #     "email": "string",
    #     "phone": "string",
    #     "terms": boolean
    # }
    #
    # Backend должен вернуть:
    # {
    #     "success": true,
    #     "message": "Компания создана",
    #     "token": "JWT токен или сессионный токен",
    #     "user": {
    #         "id": number,
    #         "email": "string",
    #         "company_name": "string"
    #     }
    # }
    #
    # При ошибке:
    # {
    #     "success": false,
    #     "message": "Компания с такой почтой уже существует"
    # }
    
    # TODO: Проверка существования email в базе данных
    # TODO: Создание новой компании в базе данных
    # TODO: Генерация JWT токена или сессии
    # TODO: Возврат данных пользователя
    
    return jsonify({
        'success': True,
        'message': 'Компания создана',
        'token': 'example_token_here',  # Заменить на реальный токен из backend
        'user': {
            'id': 1,
            'email': data.get('email', ''),
            'company_name': data.get('company_name', '')
        }
    })

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
        # TODO: Получение списка заказов из БД
        # TODO: Применить фильтры из query параметров
        # TODO: Пагинация
        return jsonify({
            'orders': [],
            'total': 0,
            'page': 1,
            'limit': 50
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
        # TODO: Валидация данных
        # TODO: Создание заказа в БД
        # TODO: Возврат ID созданного заказа
        data = request.json or {}
        if not data.get('order_name'):
            return jsonify({'success': False, 'message': 'Название заказа обязательно'}), 400
        return jsonify({'success': True, 'id': 1, 'message': 'Заказ создан'})

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
        # TODO: Получение заказа из БД по ID
        # TODO: Проверка существования заказа
        return jsonify({
            'id': order_id,
            'order_name': f'Заказ #{order_id}',
            'status': 'planned',
            'courier_id': None,
            'courier_name': None
        })
    elif request.method == 'DELETE':
        """
        DELETE /api/orders/<id> - Удаление заказа
        
        Возвращает:
        {
            "success": true,
            "message": "Заказ удален"
        }
        """
        # TODO: Проверка существования заказа
        # TODO: Удаление заказа из БД
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
        # TODO: Проверка существования заказа
        # TODO: Обновление заказа в БД
        data = request.json
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
        # TODO: Валидация массива ID
        # TODO: Массовое удаление заказов из БД
        # TODO: Возврат количества удаленных записей
        data = request.json
        ids = data.get('ids', [])
        return jsonify({
            'success': True,
            'deleted_count': len(ids),
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
        # TODO: Получение маршрутов из БД
        # TODO: Применить фильтры
        return jsonify({'routes': []})
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
        # TODO: Валидация данных
        # TODO: Создание маршрута в БД
        data = request.json
        return jsonify({'success': True, 'id': 1, 'message': 'Маршрут создан'})

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
        # TODO: Получение маршрута из БД по ID
        return jsonify({'id': route_id, 'status': 'active'})
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
        # TODO: Обновление маршрута в БД
        data = request.json
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
        # TODO: Удаление маршрута из БД
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
    # TODO: Запуск внешнего скрипта/сервиса оптимизации
    # TODO: Сохранение задачи оптимизации и возврат ID
    return jsonify({
        'success': True,
        'message': 'Оптимизация запущена',
        'task_id': 'opt-task-123',
        'estimated_time': '30s',
        'preview_route_id': 1
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
    # TODO: Получение координат маршрута и заказов, подготовка данных для карты
    return jsonify({
        'route_id': route_id,
        'courier': {
            'id': 1,
            'full_name': 'Азымбек Казбек'
        },
        'orders': [],
        'path': []
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
        # TODO: Получение списка курьеров из БД
        return jsonify({'couriers': []})
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
        # TODO: Валидация данных
        # TODO: Проверка уникальности телефона/telegram
        # TODO: Создание курьера в БД
        data = request.json
        return jsonify({'success': True, 'id': 1, 'message': 'Курьер добавлен'})

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
        # TODO: Получение курьера из БД по ID
        return jsonify({'id': courier_id, 'full_name': ''})
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
        # TODO: Проверка существования курьера
        # TODO: Обновление курьера в БД
        data = request.json
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
        # TODO: Проверка существования курьера
        # TODO: Проверка связанных маршрутов (можно ли удалить)
        # TODO: Удаление курьера из БД
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
        # TODO: Получение списка точек из БД
        return jsonify({'points': []})
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
        # TODO: Валидация данных
        # TODO: Если make_primary=true, снять primary с других точек
        # TODO: Создание точки в БД
        data = request.json
        address = data.get('address')
        if not address:
            return jsonify({'success': False, 'message': 'Адрес обязателен'}), 400
        return jsonify({'success': True, 'id': 1, 'message': 'Точка добавлена'})

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
        # TODO: Получение точки из БД по ID
        return jsonify({'id': point_id, 'address': ''})
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
        # TODO: Проверка существования точки
        # TODO: Если make_primary=true, снять primary с других точек
        # TODO: Обновление точки в БД
        data = request.json
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
        # TODO: Проверка существования точки
        # TODO: Проверка, не является ли точка основной
        # TODO: Проверка связанных заказов
        # TODO: Удаление точки из БД
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
    if request.method == 'GET':
        # TODO: Получение данных профиля из БД
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
        # TODO: Валидация данных
        # TODO: Сохранение профиля в БД
        data = request.json
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

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """
    POST /api/logout - Выход из системы
    
    Требует аутентификации (токен в заголовке Authorization)
    
    Возвращает:
    {
        "success": true,
        "message": "Выход выполнен"
    }
    """
    # TODO: Проверка токена аутентификации
    # TODO: Инвалидация токена/сессии в БД
    return jsonify({'success': True, 'message': 'Выход выполнен'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)

