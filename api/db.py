from pymongo import MongoClient
from django.conf import settings
import ssl

_client = None

def get_db():
    global _client
    if _client is None:
        _client = MongoClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
            maxPoolSize=1,
            minPoolSize=0,
            tls=True,
            tlsAllowInvalidCertificates=True,
        )
    return _client[settings.MONGO_DB_NAME]