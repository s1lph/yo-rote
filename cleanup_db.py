
from app import app, db
from models import User, Courier, Order, Route

with app.app_context():
    print("Начинаем очистку базы данных...")
    Route.query.delete()
    print("Удалены все маршруты")
    
    Order.query.delete()
    print("Удалены все заказы")
    
    Courier.query.delete()
    print("Удалены все курьеры")
    
    User.query.delete()
    print("Удалены все пользователи")
    
    db.session.commit()
    print("\nБаза данных полностью очищена!")
    print("Теперь вы можете зарегистрировать нового пользователя через /registration")
