import paho.mqtt.client as mqtt
import pymongo
import ssl
import json
from datetime import datetime, timedelta 
import os
import sys


# CONFIGURACIÓN MQTT SEGURA 
MQTT_BROKER = "33882d7d491e471ab755cad33c886d4a.s1.eu.hivemq.cloud" 
MQTT_PORT = 8883
MQTT_TOPIC = "rastreador/alerta/caida" 
MQTT_USERNAME = "canelita" 
MQTT_PASSWORD = "Canelita123" 

#CONFIGURACIÓN DE MONGODB ATLAS
MONGO_URI = "mongodb+srv://canelita:1234@gps.4npa1tv.mongodb.net/?retryWrites=true&w=majority&appName=GPS"
DB_NAME = "GPS" 
COLLECTION_NAME = "fall_alerts" 

#CONFIGURACIÓN DE ZONA HORARIA (UTC-4)
TIMEZONE_OFFSET_HOURS = -4


#CONFIGURACIÓN DE LOG LOCAL (JSON LINES)
LOCAL_LOG_FILE = "fall_alerts_local_log.jsonl"



# Variables globales
db_client = None
db_collection = None

def setup_mongodb():
    """Inicializa la conexión a MongoDB Atlas y la colección."""
    global db_client, db_collection
    try:
        print("[MONGO] Intentando conectar a MongoDB Atlas...")
        db_client = pymongo.MongoClient(MONGO_URI)
        db = db_client[DB_NAME]
        db_collection = db[COLLECTION_NAME]
        _ = db.name 
        
        print(f"[MONGO] Conectado. Base de datos: {DB_NAME}. Colección: {COLLECTION_NAME}")
    except Exception as e:
        print(f"[MONGO] ERROR al conectar a MongoDB. ¿Es correcta la IP en Network Access de Atlas? Error: {e}")
        sys.exit(1)


def on_connect(client, userdata, flags, rc):
    """Función que se llama al establecer la conexión MQTT."""
    if rc == 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Conectado al broker seguro: {MQTT_BROKER}")
        client.subscribe(MQTT_TOPIC)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Escuchando en el tópico: {MQTT_TOPIC}")
        print("-" * 50)
        print("Esperando alertas de caída...")
        print("-" * 50)
    else:
        print(f"[MQTT] Fallo en la conexión. Código de retorno: {rc}")

def log_to_local_json(document):
    """Guarda el documento de alerta en un archivo JSON local (formato JSON Lines)."""
    try:
        log_document = document.copy()
        if '_id' in log_document:
            log_document['_id'] = str(log_document['_id'])
            
        if 'received_at_utc' in log_document:
            log_document['received_at_utc'] = log_document['received_at_utc'].isoformat()
        if 'received_at_local' in log_document:
            log_document['received_at_local'] = log_document['received_at_local'].isoformat()

        json_line = json.dumps(log_document)
        with open(LOCAL_LOG_FILE, 'a') as f:
            f.write(json_line + '\n')
            
        local_time = datetime.now() + timedelta(hours=TIMEZONE_OFFSET_HOURS)
        print(f"[{local_time.strftime('%H:%M:%S -4')}] Guardado en log local: {LOCAL_LOG_FILE}")
        
    except Exception as e:
        print(f"[ERROR] Fallo al escribir en el log local: {e}")


def on_message(client, userdata, msg):
    """Función que se llama al recibir un mensaje y lo guarda en MongoDB y localmente."""
    global db_collection
    
    try:
        payload_str = msg.payload.decode('utf-8')
        data = json.loads(payload_str)
        
        utc_now = datetime.utcnow()
        local_time = utc_now + timedelta(hours=TIMEZONE_OFFSET_HOURS)
        document = {
            "device_id": data.get("device_id"),
            "event_type": data.get("event", "FALL"),
            "impact_G": data.get("impact_G"),
            "timestamp_unix": data.get("timestamp"),
            "location": data.get("location"), 
            "received_at_utc": utc_now,
            "received_at_local": local_time 
        }
        
        if db_collection is not None:
            result = db_collection.insert_one(document)
            document['_id'] = result.inserted_id
            
            lat = document['location'].get('lat') if document['location'] else 'N/A'
            lon = document['location'].get('lon') if document['location'] else 'N/A'
            
            print(f"[{local_time.strftime('%H:%M:%S -4')}] Guardado (ID: {result.inserted_id}) | Impacto: {document['impact_G']:.2f} G | Ubicación: {lat}, {lon}")
        else:
            print("[MONGO] ADVERTENCIA: Colección no disponible para guardar datos.")
        log_to_local_json(document)

    except json.JSONDecodeError:
        print(f"[ERROR] Mensaje inválido (no es JSON): {payload_str}")
    except Exception as e:
        print(f"[ERROR] Fallo al procesar/guardar: {type(e).__name__}: {e}")


def main():
    """Función principal del suscriptor de MQTT y MongoDB."""
    setup_mongodb()
    client = mqtt.Client(client_id="Python_Fall_Listener")
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.tls_set(cert_reqs=ssl.CERT_NONE) 
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    except Exception as e:
        print(f"[MQTT] ERROR al configurar seguridad/credenciales: {e}")
        sys.exit(1)

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever() 
    except KeyboardInterrupt:
        print("\nPrograma detenido por el usuario.")
    except Exception as e:
        print(f"Fallo crítico del cliente MQTT: {e}")
    finally:
        if db_client:
            db_client.close()
            print("[MONGO] Conexión a MongoDB cerrada.")

if __name__ == '__main__':
    main()
