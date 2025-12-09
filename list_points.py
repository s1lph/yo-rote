from app import app, db, Point

with app.app_context():
    points = Point.query.all()
    print(f"Total points: {len(points)}")
    for p in points:
        print(f"ID: {p.id}, Address: {p.address}, Primary: {p.is_primary}")
