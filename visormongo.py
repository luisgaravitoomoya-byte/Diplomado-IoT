import pymongo
import pandas as pd
import sys
from datetime import datetime 


MONGO_URI = "URI mongoDB"
DB_NAME = "GPS" 
COLLECTION_NAME = "fall_alerts" 


def fetch_and_display_data():
    """
    Se conecta a MongoDB, recupera todas las alertas de caída 
    y las muestra en formato de tabla usando pandas.
    """
    client = None 
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Conectando a MongoDB Atlas...")
        client = pymongo.MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        
        documents = list(collection.find().sort("received_at_utc", pymongo.DESCENDING))
        
        if not documents:
            print("--------------------------------------------------")
            print("¡Base de datos vacía! No hay alertas de caída registradas.")
            print("--------------------------------------------------")
            return
            
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Conexión exitosa. Se recuperaron {len(documents)} alertas.")

        data_for_df = []
        for doc in documents:
            
            local_time_data = doc.get('received_at_local', 'N/A')
            if isinstance(local_time_data, str):
                try:
                    local_time_data = datetime.fromisoformat(local_time_data)
                except ValueError:
                    local_time_data = 'ERROR_DATE'

            hora_local_str = local_time_data.strftime('%Y-%m-%d %H:%M:%S') if isinstance(local_time_data, datetime) else 'N/A'
            location = doc.get('location', {})
            lat = location.get('lat', 'N/A')
            lon = location.get('lon', 'N/A')
            data_for_df.append({
                "ID_MONGO": str(doc.get('_id')),
                "HORA_LOCAL (UTC-4)": hora_local_str,
                "DISPOSITIVO": doc.get('device_id', 'N/A'),
                "EVENTO": doc.get('event_type', 'N/A'),
                "IMPACTO (G)": f"{doc.get('impact_G', 0.0):.2f}",
                "LATITUD": f"{lat:.6f}" if isinstance(lat, float) else lat,
                "LONGITUD": f"{lon:.6f}" if isinstance(lon, float) else lon,
            })
            
        df = pd.DataFrame(data_for_df)
        
        print("\n" + "=" * 100)
        print(f"            >>> REGISTRO COMPLETO DE ALERTAS DE CAÍDA ({DB_NAME}.{COLLECTION_NAME}) <<<")
        print("=" * 100)
        display_df = df.head(20) if len(df) > 20 else df
        print(display_df.to_string(index=False))

        if len(df) > 20:
            print(f"\n... mostrando solo las primeras 20 de {len(df)} registros. Ejecuta 'df.to_string(index=False)' para ver el total si estás en un entorno interactivo.")

    except pymongo.errors.PyMongoError as e: 
        print(f"\n[ERROR CRÍTICO de MongoDB] No se pudo conectar a MongoDB. Asegúrate de que tu PC tiene acceso a internet y la IP está en la lista blanca de Atlas. Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Ocurrió un error inesperado: {type(e).__name__}: {e}")
    finally:
        if client:
            client.close()
            print("\n[MONGO] Conexión a MongoDB cerrada.")

if __name__ == '__main__':
    fetch_and_display_data()
