"""Conexión compartida a MongoDB para las rutas de la aplicación."""
import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "hotel_db")

# MongoClient administra un pool de conexiones y puede compartirse entre rutas.
client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=10000,
    connectTimeoutMS=10000,
)

db = client[DATABASE_NAME]

users_collection = db["users"]
rooms_collection = db["rooms"]
reservations_collection = db["reservations"]
