# Importa el cliente de MongoDB desde la librería pymongo
from pymongo import MongoClient

# Importa la configuración del proyecto Django
# Aquí se encuentran variables como MONGO_URI y MONGO_DB_NAME
from django.conf import settings

# Librería usada para manejar seguridad SSL en la conexión
import ssl


# Variable global para guardar la conexión del cliente
# Se inicializa como None para crearla solo cuando se necesite
_client = None


# Función que devuelve la conexión a la base de datos
def get_db():
    # Se usa la variable global _client
    global _client

    # Si todavía no existe una conexión a MongoDB
    if _client is None:

        # Se crea una nueva conexión usando MongoClient
        _client = MongoClient(

            # URI de conexión a MongoDB (se obtiene desde settings.py)
            settings.MONGO_URI,

            # Tiempo máximo para intentar conectarse al servidor
            serverSelectionTimeoutMS=5000,

            # Tiempo máximo para establecer conexión
            connectTimeoutMS=5000,

            # Tiempo máximo para esperar respuesta del servidor
            socketTimeoutMS=5000,

            # Máximo número de conexiones en el pool
            maxPoolSize=1,

            # Mínimo número de conexiones abiertas
            minPoolSize=0,

            # Habilita conexión segura TLS (SSL)
            tls=True,

            # Permite certificados TLS no verificados (útil en algunos entornos)
            tlsAllowInvalidCertificates=True,
        )

    # Devuelve la base de datos definida en settings
    # Ejemplo: planificador_db
    return _client[settings.MONGO_DB_NAME]