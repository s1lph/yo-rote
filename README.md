# yo.route 



## Установка и запуск
```
pip install -r requirements.txt
```
```
python app.py
```
```
http://localhost:5000
```


## API Endpoints

endpoints:

### Регистрация
- `POST /api/register` - Регистрация новой компании

### Заказы
- `GET /api/orders` - Получение списка заказов
- `POST /api/orders` - Создание нового заказа

### Маршруты
- `GET /api/routes` - Получение маршрутов

### Курьеры
- `GET /api/couriers` - Получение списка курьеров
- `POST /api/couriers` - Добавление курьера

### Точки отправки
- `GET /api/points` - Получение точек отправки
- `POST /api/points` - Добавление точки

### Настройки
- `GET /api/settings` - Получение настроек
- `PUT /api/settings` - Обновление настроек

## Интеграция с Backend

Все API endpoints в `app.py` содержат TODO комментарии, для интеграции с backend. outdated

Пример  для интеграции:

### Регистрация компании
```json
{
  "company_name": "string",
  "activity": "string",
  "email": "string",
  "phone": "string",
  "terms": true
}
```

### Создание заказа
```json
{
  "order_name": "string",
  "destination_point": "string",
  "point_address": "string",
  "visit_date": "YYYY-MM-DD",
  "visit_time": "HH:MM",
  "time_at_point": number,
  "recipient_name": "string",
  "recipient_phone": "string",
  "comment": "string"
}
```

### Добавление курьера
```json
{
  "full_name": "string",
  "phone": "string",
  "telegram": "string",
  "vehicle_type": "car|truck|bicycle|scooter",
  "auth_key": "string"
}
```

### Добавление точки
```json
{
  "address": "string",
  "make_primary": boolean
}
```


