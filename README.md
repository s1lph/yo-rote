# yo.route — Логистическая платформа для малого бизнеса

<p align="center">
  <img src="static/img/logo.svg" alt="yo.route Logo" width="180">
</p>

**yo.route** — это современная веб-платформа для автоматизации доставки, оптимизации маршрутов и управления курьерами. Система использует алгоритмы VRP (Vehicle Routing Problem) для построения оптимальных маршрутов и интеграцию с Telegram для управления курьерами в реальном времени.

---

## Содержание

- [Возможности](#возможности)
- [Технологический стек](#технологический-стек)
- [Быстрый старт](#быстрый-старт)
- [Конфигурация](#конфигурация)
- [Структура проекта](#структура-проекта)
- [Модели базы данных](#модели-базы-данных)
- [API Reference](#api-reference)
- [Telegram-бот для курьеров](#telegram-бот-для-курьеров)
- [Утилиты и скрипты](#утилиты-и-скрипты)
- [Лицензия](#лицензия)

---

## Возможности

### Основные функции

| Функция | Описание |
|---------|----------|
| **Управление заказами** | Создание, редактирование, удаление заказов с автоматическим геокодированием адресов |
| **Оптимизация маршрутов** | VRP-алгоритм для распределения заказов между курьерами |
| **Импорт из Excel** | Массовый импорт заказов из `.xlsx` и `.xls` файлов |
| **Точки отправки** | Управление множеством складов/точек отправки |
| **Управление курьерами** | Добавление курьеров с различными типами транспорта |
| **Telegram-интеграция** | Мобильное рабочее место водителя с фото-подтверждениями |
| **Интерактивная карта** | Визуализация маршрутов на Leaflet.js с отображением геолокации курьеров |
| **Аутентификация** | JWT-токены + Google OAuth 2.0 |

### Безопасность

- JWT-токены с привязкой к IP-адресу клиента
- Хеширование паролей через Werkzeug
- Изоляция данных пользователей (multi-tenant)
- Google OAuth 2.0 для быстрой авторизации

---

## Технологический стек

### Backend
| Технология | Назначение |
|------------|------------|
| **Flask 3.0** | Веб-фреймворк |
| **Flask-SQLAlchemy** | ORM для работы с БД |
| **SQLite** | База данных |
| **OpenRouteService** | Геокодинг + VRP оптимизация |
| **PyJWT** | Аутентификация через токены |
| **Authlib** | Google OAuth 2.0 |
| **aiogram 3.x** | Telegram-бот |

### Frontend
| Технология | Назначение |
|------------|------------|
| **Leaflet.js** | Интерактивные карты |
| **Vanilla JavaScript** | Логика клиента |
| **CSS3** | Стилизация (без фреймворков) |

---

## Быстрый старт

### 1. Клонирование репозитория

```bash
git clone https://github.com/your-repo/yorote.git
cd yorote
```

### 2. Создание виртуального окружения

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

Создайте файл `.env` на основе `.env.example`:

```env
# Обязательные
ORS_API_KEY=your_openrouteservice_api_key
SECRET_KEY=your-secret-key-for-jwt

# База данных
DATABASE_URL=sqlite:///logistics.db

# Режим разработки
FLASK_ENV=development

# Google OAuth (опционально)
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

# Telegram-бот (опционально)
TG_BOT_TOKEN=your_telegram_bot_token
TG_ADMIN_ID=123456789
```

> **Важно:** Без `ORS_API_KEY` геокодинг и оптимизация маршрутов работать не будут!
> Получите бесплатный ключ на [openrouteservice.org](https://openrouteservice.org/dev/#/signup)

### 5. Запуск приложения

```bash
# Запуск веб-сервера
python app.py
```

Откройте http://localhost:5000

### 6. Запуск Telegram-бота (опционально)

```bash
# В отдельном терминале
python bot.py
```

---

## Конфигурация

### Переменные окружения

| Переменная | Описание | Обязательная |
|------------|----------|--------------|
| `ORS_API_KEY` | API ключ OpenRouteService для геокодинга и VRP | Да |
| `SECRET_KEY` | Секретный ключ для JWT-токенов | Да |
| `DATABASE_URL` | URL базы данных (по умолчанию SQLite) | Нет |
| `FLASK_ENV` | Окружение: `development` или `production` | Нет |
| `GOOGLE_CLIENT_ID` | Client ID для Google OAuth | Нет |
| `GOOGLE_CLIENT_SECRET` | Client Secret для Google OAuth | Нет |
| `TG_BOT_TOKEN` | Токен Telegram-бота | Нет |
| `TG_ADMIN_ID` | ID администраторов бота (через запятую) | Нет |

---

## Структура проекта

```
yorote/
├── app.py              # Главное Flask-приложение с REST API
├── bot.py              # Telegram-бот для водителей (aiogram 3.x)
├── models.py           # SQLAlchemy модели базы данных
├── optimizer.py        # Модуль VRP-оптимизации маршрутов
├── telegram_utils.py   # Утилиты для Telegram-уведомлений
├── requirements.txt    # Python-зависимости
├── .env.example        # Пример конфигурации
├── logistics.db        # SQLite база данных (создается автоматически)
│
├── templates/          # HTML-шаблоны (Jinja2)
│   ├── base.html           # Базовый шаблон
│   ├── index.html          # Главная страница
│   ├── login.html          # Страница входа
│   ├── registration.html   # Страница регистрации
│   ├── orders.html         # Управление заказами
│   ├── couriers.html       # Управление курьерами
│   ├── points.html         # Управление точками отправки
│   ├── optimization.html   # Оптимизация маршрутов + карта
│   ├── account.html        # Настройки аккаунта
│   └── settings.html       # Настройки системы
│
├── static/
│   ├── css/            # Стили
│   └── img/            # Изображения и иконки
│
└── instance/           # Локальные данные экземпляра
```

---

## Модели базы данных

### User (Пользователь/Компания)

```python
class User:
    id: int                 # Уникальный ID
    email: str              # Email (уникальный)
    password_hash: str      # Хеш пароля
    company_name: str       # Название компании
    activity: str           # Вид деятельности
    phone: str              # Телефон
    created_at: datetime    # Дата создания
    updated_at: datetime    # Дата обновления
```

**Методы:**
- `set_password(password)` — Хеширование и сохранение пароля
- `check_password(password)` — Проверка пароля
- `to_dict()` — Сериализация в JSON

---

### Courier (Курьер)

```python
class Courier:
    id: int                 # Уникальный ID
    user_id: int            # ID владельца (компании)
    full_name: str          # ФИО курьера
    phone: str              # Телефон
    telegram: str           # Telegram username
    vehicle_type: str       # Тип транспорта (car/truck/bicycle/scooter)
    profile: str            # Профиль маршрутизации OpenRouteService
    capacity: int           # Грузоподъемность
    start_lat: float        # Начальная широта
    start_lon: float        # Начальная долгота
    auth_code: str          # 6-значный код для Telegram-авторизации
    telegram_chat_id: str   # ID чата Telegram (после авторизации)
    is_on_shift: bool       # Находится ли на смене
    current_lat: float      # Текущая широта (геолокация)
    current_lon: float      # Текущая долгота (геолокация)
```

**Методы:**
- `generate_auth_code(force=False)` — Генерация кода авторизации для Telegram
- `to_dict()` — Сериализация в JSON

---

### Order (Заказ)

```python
class Order:
    id: int                 # Уникальный ID
    user_id: int            # ID владельца
    order_name: str         # Название заказа (обязательное)
    destination_point: str  # Название точки назначения
    address: str            # Адрес доставки
    lat: float              # Широта
    lon: float              # Долгота
    visit_date: str         # Дата посещения (YYYY-MM-DD)
    visit_time: str         # Время посещения (HH:MM)
    time_at_point: int      # Время на точке (минуты)
    recipient_name: str     # Имя получателя
    recipient_phone: str    # Телефон получателя
    comment: str            # Комментарий
    company: str            # Компания-отправитель
    courier_id: int         # ID назначенного курьера
    point_id: int           # ID точки отправления
    route_id: int           # ID маршрута
    route_position: int     # Позиция в маршруте
    status: str             # Статус (planned/in_progress/completed/failed)
```

**Статусы заказа:**
| Статус | Описание |
|--------|----------|
| `planned` | Запланирован |
| `in_progress` | В процессе доставки |
| `completed` | Доставлен |
| `failed` | Не доставлен |

---

### Route (Маршрут)

```python
class Route:
    id: int             # Уникальный ID
    user_id: int        # ID владельца
    courier_id: int     # ID курьера
    name: str           # Название маршрута
    date: str           # Дата маршрута (YYYY-MM-DD)
    status: str         # Статус (active/completed)
    geometry: str       # Encoded polyline геометрии
    orders: List[Order] # Заказы в маршруте
```

---

### Point (Точка отправки)

```python
class Point:
    id: int             # Уникальный ID
    user_id: int        # ID владельца
    name: str           # Название точки
    address: str        # Адрес
    latitude: float     # Широта
    longitude: float    # Долгота
    is_primary: bool    # Основная точка
```

---

## API Reference

Все API-эндпоинты возвращают JSON. Для защищенных маршрутов требуется заголовок:
```
Authorization: Bearer <JWT_TOKEN>
```

### Аутентификация

#### POST /api/register
Регистрация новой компании.

**Тело запроса:**
```json
{
    "company_name": "ООО Доставка",
    "activity": "Курьерская служба",
    "email": "admin@delivery.ru",
    "phone": "+79001234567",
    "password": "secure_password",
    "terms": true
}
```

**Ответ:**
```json
{
    "success": true,
    "message": "Регистрация успешна",
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "user": { ... }
}
```

---

#### POST /api/login
Вход в систему.

**Тело запроса:**
```json
{
    "email": "admin@delivery.ru",
    "password": "secure_password",
    "remember": true
}
```

**Ответ:**
```json
{
    "success": true,
    "message": "Вход выполнен успешно",
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "user": { ... }
}
```

---

#### GET /api/login/google
Перенаправление на авторизацию через Google OAuth 2.0.

---

#### GET /api/user/current
Получение данных текущего пользователя (требует JWT).

---

### Заказы

#### GET /api/orders
Получение списка заказов.

**Query параметры:**
| Параметр | Описание |
|----------|----------|
| `page` | Номер страницы (default: 1) |
| `limit` | Количество на странице (default: 50) |
| `status` | Фильтр по статусу |
| `visit_date` | Фильтр по дате (YYYY-MM-DD) |
| `search` | Поиск по адресу/названию/получателю |

---

#### POST /api/orders
Создание нового заказа с автоматическим геокодингом.

**Тело запроса:**
```json
{
    "order_name": "Заказ #1001",
    "destination_point": "ул. Ленина, 25, Москва",
    "visit_date": "2024-12-15",
    "visit_time": "14:00",
    "time_at_point": 15,
    "recipient_name": "Иван Иванов",
    "recipient_phone": "+79001112233",
    "comment": "Домофон 25#",
    "point_id": 1,
    "courier_id": null
}
```

---

#### PUT /api/orders/{id}
Обновление заказа.

---

#### DELETE /api/orders/{id}
Удаление заказа.

---

#### DELETE /api/orders/batch
Массовое удаление заказов.

**Тело запроса:**
```json
{
    "ids": [1, 2, 3, 4, 5]
}
```

---

#### POST /api/orders/import
Импорт заказов из Excel файла.

**Form Data:**
- `file`: Excel-файл (.xlsx или .xls)
- `point_id`: ID точки отправления

**Обязательные колонки в Excel:**
| Колонка | Описание |
|---------|----------|
| Название | Название заказа |
| Адрес | Адрес доставки |
| Дата | Дата посещения |
| Время | Время посещения |
| Имя клиента | Имя получателя |
| Телефон | Телефон получателя |

---

### Курьеры

#### GET /api/couriers
Получение списка курьеров.

---

#### POST /api/couriers
Добавление нового курьера.

**Тело запроса:**
```json
{
    "full_name": "Петр Петров",
    "phone": "+79001234567",
    "telegram": "@petrov",
    "vehicle_type": "car",
    "profile": "driving-car",
    "capacity": 100
}
```

**Типы транспорта:**
| Тип | OpenRouteService Profile | Описание |
|-----|----------|----------|
| `car` | `driving-car` | Легковой автомобиль |
| `truck` | `driving-hgv` | Грузовик |
| `bicycle` | `cycling-regular` | Велосипед |
| `scooter` | `driving-car` | Скутер/мопед |

---

#### PUT /api/couriers/{id}
Обновление курьера.

---

#### DELETE /api/couriers/{id}
Удаление курьера (только если нет активных маршрутов).

---

#### POST /api/couriers/{id}/regenerate-code
Генерация нового кода авторизации для Telegram.

---

#### GET /api/couriers/locations
Получение текущих геолокаций курьеров на смене.

---

### Маршруты

#### GET /api/routes
Получение списка маршрутов.

**Query параметры:**
| Параметр | Описание |
|----------|----------|
| `date` | Фильтр по дате (YYYY-MM-DD) |
| `courier_id` | Фильтр по курьеру |
| `status` | Фильтр по статусу |

---

#### POST /api/routes
Создание нового маршрута вручную.

---

#### POST /api/routes/optimize
**Оптимизация маршрутов (VRP)**

Автоматически группирует заказы по точкам отправки и распределяет между курьерами с оптимальным порядком посещения.

**Тело запроса:**
```json
{
    "date": "2024-12-15"
}
```

**Алгоритм работы:**
1. Получает все нераспределенные заказы на указанную дату
2. Группирует заказы по точкам отправки (`point_id`)
3. Для каждой группы запускает VRP-оптимизацию через OpenRouteService
4. Создает маршруты и привязывает заказы

---

#### GET /api/routes/{id}/optimize-view
Получение данных маршрута для визуализации на карте.

**Ответ:**
```json
{
    "route_id": 1,
    "courier": {
        "id": 1,
        "full_name": "Петр Петров",
        "start_lat": 55.7558,
        "start_lon": 37.6173
    },
    "depot": {
        "lat": 55.7558,
        "lon": 37.6173,
        "address": "ул. Складская, 1"
    },
    "orders": [
        {
            "order_id": 1,
            "order_name": "Заказ #1001",
            "address": "ул. Ленина, 25",
            "lat": 55.758,
            "lng": 37.615,
            "status": "planned"
        }
    ],
    "path": [
        {"lat": 55.7558, "lng": 37.6173},
        {"lat": 55.758, "lng": 37.615}
    ]
}
```

---

#### POST /api/routes/{id}/edit
Изменение порядка заказов в маршруте вручную.

**Тело запроса:**
```json
{
    "orders": [3, 1, 2, 4]
}
```

---

#### POST /api/routes/{id}/send-to-driver
Отправка маршрута водителю в Telegram.

---

### Точки отправки

#### GET /api/points
Получение списка точек отправки.

---

#### POST /api/points
Создание новой точки отправки.

**Тело запроса:**
```json
{
    "name": "Основной склад",
    "address": "ул. Складская, 1, Москва",
    "is_primary": true
}
```

---

#### PUT /api/points/{id}
Обновление точки.

---

#### DELETE /api/points/{id}
Удаление точки.

---

### Геокодинг

#### GET /api/geocode/search
Поиск адресов для автокомплита.

**Query параметры:**
| Параметр | Описание |
|----------|----------|
| `q` | Поисковый запрос (минимум 3 символа) |
| `limit` | Максимум результатов (default: 8) |

**Ответ:**
```json
{
    "suggestions": [
        {
            "label": "Красная площадь, 1, Москва",
            "lat": 55.7539,
            "lon": 37.6208
        }
    ]
}
```

---

#### POST /api/routes/preview
Предпросмотр маршрута между двумя точками.

**Тело запроса:**
```json
{
    "origin_lat": 55.7558,
    "origin_lon": 37.6173,
    "destination_lat": 55.758,
    "destination_lon": 37.615,
    "profile": "driving-car"
}
```

---

## Telegram-бот для курьеров

Бот предоставляет мобильное рабочее место для водителей с возможностью:

### Функции для водителей

| Функция | Описание |
|---------|----------|
| **Авторизация** | Вход по 6-значному коду из веб-панели |
| **Мои заказы** | Просмотр назначенных заказов |
| **Статусы заказов** | Отметка «Доставлено» / «Не доставлено» |
| **Фото-подтверждения** | Отправка фото при доставке |
| **Навигация** | Deep-links в Яндекс.Карты/2ГИС |
| **Звонок клиенту** | Быстрый звонок по нажатию кнопки |
| **Смена** | Начало/завершение рабочей смены |
| **Геолокация** | Отправка координат в реальном времени |

### Функции для администраторов

| Функция | Описание |
|---------|----------|
| **Статистика** | Общая статистика по курьерам и заказам |
| **Рассылка** | Массовая рассылка сообщений курьерам |
| **Тревога** | Экстренные уведомления |
| **Фото-пруфы** | Просмотр фотографий подтверждения |

### Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Начало работы, ввод кода авторизации |
| `/menu` | Главное меню |
| `/orders` | Список заказов |
| `/shift` | Начать/завершить смену |
| `/admin` | Админ-панель (только для админов) |

### Инлайн-кнопки для заказов

При получении маршрута, каждый заказ приходит с интерактивными кнопками:

- **Доставлено** — Отметить успешную доставку (с запросом фото)
- **Не доставлено** — Указать причину неудачи
- **Позвонить** — Звонок получателю
- **Навигатор** — Открыть адрес в картах

---

## Утилиты и скрипты

### optimizer.py — Оптимизация маршрутов

**Функции:**

#### `solve_vrp(orders, couriers, depot)`
Решает задачу Vehicle Routing Problem.

```python
from optimizer import solve_vrp

routes = solve_vrp(
    orders=[order1, order2, order3],
    couriers=[courier1, courier2],
    depot={'lat': 55.7558, 'lon': 37.6173}
)
# Возвращает:
# [
#     {
#         'courier_id': 1,
#         'order_ids': [1, 3, 2],  # порядок посещения
#         'geometry': 'encoded_polyline...',
#         'summary': {'distance': 15000, 'duration': 3600}
#     }
# ]
```

#### `geocode_address(address, country='RU')`
Геокодирование адреса в координаты.

```python
from optimizer import geocode_address

coords = geocode_address("Красная площадь, Москва")
# Возвращает: (37.6208, 55.7539) — (lon, lat)
```

#### `decode_polyline(encoded)`
Декодирование Google Encoded Polyline.

```python
from optimizer import decode_polyline

path = decode_polyline("_p~iF~ps|U...")
# Возвращает: [[55.75, 37.61], [55.76, 37.62], ...]
```

---

### telegram_utils.py — Telegram-утилиты

#### `send_route_to_driver(route_id)`
Отправляет маршрут водителю в Telegram с интерактивными кнопками.

```python
from telegram_utils import send_route_to_driver

result = send_route_to_driver(route_id=1)
# {'success': True, 'message': 'Маршрут отправлен', 'sent_count': 5}
```

#### `send_telegram_message(chat_id, text, parse_mode='Markdown')`
Отправка сообщения через Telegram Bot API.

---

### Скрипты миграций

| Скрипт | Описание |
|--------|----------|
| `update_db_schema.py` | Добавление новых полей в существующую БД |
| `migrate_db.py` | Миграция структуры базы данных |
| `migrate_bot_fields.py` | Миграция полей для Telegram-бота |
| `cleanup_db.py` | Очистка тестовых данных |

---

## Roadmap

- [x] Аутентификация пользователей (JWT + Google OAuth)
- [x] Telegram-бот для курьеров
- [x] Импорт заказов из Excel
- [x] Фото-подтверждения доставки
- [x] Отображение геолокации курьеров на карте
- [ ] Статистика и аналитика
- [ ] Push-уведомления
- [ ] Мобильное приложение для курьеров (React Native)
- [ ] Интеграция с CRM-системами(это программное обеспечение для бизнеса, которое автоматизирует и систематизирует работу с клиентами, объединяя все процессы продаж, маркетинга и обслуживания в едином месте, чтобы повысить лояльность клиентов, увеличить продажи и сделать работу компании более прозрачной и эффективной)

---

## Лицензия

MIT License

**Автор:** yo.route team

---

<p align="center">
  Built with love for small business delivery
</p>
