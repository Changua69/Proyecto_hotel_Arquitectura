"""Crea las habitaciones iniciales sin borrar ni sobrescribir datos existentes."""
from app.database import rooms_collection


def init_rooms():
    rooms = []

    # HABITACIONES ESTÁNDAR
    for i in range(1, 9):
        rooms.append({
            "number": i,
            "type": "estandar",
            "price": 100000,
            "status": "disponible",
            "description": "Habitación estándar cómoda",
            "services": ["wifi", "tv"],
            "images": [
                f"https://picsum.photos/300/200?random={i}",
                f"https://picsum.photos/300/200?random={i + 50}"
            ],
            "capacity": 2,
            "floor": 1,
            "rating": 4.2,
            "reviews": 120,
            "size": "20m2",
            "beds": "1 cama doble"
        })

    # HABITACIONES FAMILIARES
    for i in range(9, 17):
        rooms.append({
            "number": i,
            "type": "familiar",
            "price": 180000,
            "status": "disponible",
            "description": "Habitación familiar amplia",
            "services": ["wifi", "tv", "aire acondicionado"],
            "images": [
                f"https://picsum.photos/300/200?random={i}",
                f"https://picsum.photos/300/200?random={i + 50}"
            ],
            "capacity": 4,
            "floor": 2,
            "rating": 4.5,
            "reviews": 95,
            "size": "35m2",
            "beds": "2 camas dobles"
        })

    # SUITES
    for i in range(17, 25):
        rooms.append({
            "number": i,
            "type": "suite",
            "price": 300000,
            "status": "disponible",
            "description": "Suite de lujo con jacuzzi",
            "services": ["wifi", "tv", "aire acondicionado", "jacuzzi"],
            "images": [
                f"https://picsum.photos/300/200?random={i}",
                f"https://picsum.photos/300/200?random={i + 50}"
            ],
            "capacity": 2,
            "floor": 3,
            "rating": 4.9,
            "reviews": 60,
            "size": "50m2",
            "beds": "1 cama king"
        })

    # Solo inserta las habitaciones que todavía no existen.
    # No modifica reservas, estados, precios ni datos que ya estén guardados.
    for room in rooms:
        rooms_collection.update_one(
            {"number": room["number"]},
            {"$setOnInsert": room},
            upsert=True
        )
