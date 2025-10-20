from machine import UART, Pin, I2C
import utime
import network
from micropyGPS import MicropyGPS
import urequests
import math
import ujson
import usocket as socket
import ssl
import random 
import ntptime 


try:
    from umqtt.simple import MQTTClient
except ImportError:
    print("ADVERTENCIA: No se encontró la librería umqtt.simple. La alerta MQTT estará deshabilitada.")
    MQTTClient = None

try:
    from mpu6050 import MPU6050
except ImportError:
    print("ADVERTENCIA: No se encontró la librería mpu6050.py. La detección de caídas estará deshabilitada.")
    MPU6050 = None 


#CONFIGURACIÓN DEL SISTEMA Y CREDENCIALES 

#Credenciales de Wi-Fi
WIFI_SSID = "HUAWEI P30 lite"        
WIFI_PASSWORD = "78312beb"

#Credenciales de Ubidots y Make
HTTP_SERVER = "industrial.api.ubidots.com"
UBIDOTS_DEVICE_LABEL = "gpspico"
UBIDOTS_TOKEN = "BBUS-h2GNIFVlyS7FhzA3nwQ90yDdywnCe6" 
HTTP_PUBLISH_URL = f"http://{HTTP_SERVER}/api/v1.6/devices/{UBIDOTS_DEVICE_LABEL}"

#URL DE TU WEBHOOK DE MAKE (Geocerca)
MAKE_WEBHOOK_URL = "https://hook.us2.make.com/iv4coz08isi7e77uz7e11hlrrs1ds5p3" 

#Credenciales de TELEGRAM
TELEGRAM_BOT_TOKEN = "8422951184:AAHwIM5hZkn2PoOq-iS78fDqhrkplIjUfik" 
TELEGRAM_CHAT_ID = "-1003137793227" 

#Configuración de Geocerca
HOME_LAT = -16.513800  
HOME_LON = -68.126000  
SAFE_RADIUS_M = 150    

#Configuración del MPU-6050
I2C_SDA_PIN = 4
I2C_SCL_PIN = 5
I2C_FREQ = 400000 

#(Detección Híbrida: Caída Libre + Alto Impacto)
MPU_THRESHOLD_G = 0.7    # Inicia la detección si Acel. < 0.7 G.
DURATION_MS = 100        # Captura caídas rápidas (100ms)
IMPACT_THRESHOLD_G = 1.05    # Mínimo impacto para confirmar la caída libre.
INTERRUPT_THRESHOLD_G = 0.85 # Hysteresis para detener la cuenta de Caída Libre.
INSTANT_IMPACT_G = 2.2     # Si Acel. > 2.2 G, activa la alerta inmediatamente.
FALL_COOLDOWN_MS = 15000   # Cooldown de 15 segundos.

# Configuración de GPS
FORCE_NEGATIVE_LAT = True 
FORCE_NEGATIVE_LON = True 
GPS_UART = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))
my_gps = MicropyGPS(location_formatting='dd') 


#CONFIGURACIÓN DEL BROKER PRIVADO MQTT

BROKER_HOST = "33882d7d491e471ab755cad33c886d4a.s1.eu.hivemq.cloud" 
BROKER_PORT = 8883  
MQTT_CLIENT_ID = f"pico_w_tracker_{random.getrandbits(16)}" 
MQTT_USERNAME = "canelita" 
MQTT_PASSWORD = "Canelita123" 
MQTT_TOPIC_FALL = "rastreador/alerta/caida" 

#CONFIGURACIÓN DEL LED DE ESTADO
LED_PIN = Pin("LED", Pin.OUT)
LED_STATE = False


# Variables de estado globales
last_valid_lat = None
last_valid_lon = None
mpu_sensor = None 
fall_start_time = 0 
last_fall_time = 0 
last_debug_time_ms = 0
DEBUG_INTERVAL_MS = 1000
wifi_is_connected = False
mqtt_client = None 


#FUNCIONES DE UTILIDAD Y CONEXIÓN


def toggle_led():
    """Alterna el estado del LED (para el parpadeo)."""
    global LED_STATE
    LED_STATE = not LED_STATE
    LED_PIN.value(LED_STATE)

def set_led_solid_on():
    """Mantiene el LED encendido de forma fija."""
    global LED_STATE
    LED_STATE = True
    LED_PIN.value(LED_STATE)

def set_led_off():
    """Mantiene el LED apagado."""
    global LED_STATE
    LED_STATE = False
    LED_PIN.value(LED_STATE)


def set_time_ntp():
    """Sincroniza el reloj interno de la Pico W con un servidor NTP. Crucial para TLS/SSL."""
    global wifi_is_connected
    if not wifi_is_connected:
        print("[NTP] Omite la sincronización: No hay Wi-Fi.")
        return False
    
    print("[NTP] Sincronizando hora...")
    try:
        ntptime.settime()
        (year, month, day, hour, minute, second, _, _) = utime.localtime()
        print(f"[NTP] Hora sincronizada: {day}/{month}/{year} {hour}:{minute:02d}:{second:02d} UTC")
        return True
    except Exception as e:
        print(f"[NTP] Fallo al sincronizar la hora: {e}. La conexión MQTT podría fallar.")
        return False

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calcula la distancia Haversine entre dos puntos GPS en metros."""
    R = 6371000 
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) * math.sin(delta_phi / 2) + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2) * math.sin(delta_lambda / 2)
        
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance_m = R * c
    return distance_m

def do_connect(ssid, password):
    """Maneja la conexión a la red Wi-Fi."""
    global wifi_is_connected
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if wlan.isconnected():
        wifi_is_connected = True
        return True
    
    print('\n[WIFI] Conectando a la red...')
    wlan.connect(ssid, password)
    timeout = 10
    while not wlan.isconnected() and timeout > 0:
        toggle_led()
        print('.', end='')
        utime.sleep(1)
        timeout -= 1
        
    if wlan.isconnected():
        print('\n[WIFI] Conectado. IP:', wlan.ifconfig()[0])
        wifi_is_connected = True
        return True
    else:
        print('\n[WIFI] Falló la conexión.')
        wifi_is_connected = False
        return False

def initialize_mpu():
    """Inicializa el bus I2C y el sensor MPU-6050."""
    global mpu_sensor
    if MPU6050 is None: 
        print("[MPU] Inicialización omitida (librería mpu6050.py no encontrada).")
        return False
    
    print(f'[MPU] Inicializando I2C en SDA=GP{I2C_SDA_PIN}, SCL=GP{I2C_SCL_PIN}')
    try:
        i2c_bus = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=I2C_FREQ)
        devices = i2c_bus.scan()
        if MPU6050.I2C_ADDR not in devices:
            print("ERROR: MPU-6050 no encontrado en la dirección I2C. Sistema anticaídas DESHABILITADO.")
            return False
            
        mpu_sensor = MPU6050(i2c_bus)
        _ = mpu_sensor.get_accel_data() 
        print("MPU-6050 detectado e inicializado. Sistema anticaídas ACTIVO.")
        return True
    except Exception as e:
        print(f"ERROR al inicializar MPU por excepción: {e}. Sistema anticaídas DESHABILITADO.")
        return False


#FUNCIONES DE CONEXIÓN Y ALERTA MQTT
#

def mqtt_connect_secure():
    if MQTTClient is None:
        return None

    try:
        ssl_params = {"server_hostname": BROKER_HOST}
        
        client = MQTTClient(
            client_id=MQTT_CLIENT_ID, 
            server=BROKER_HOST, 
            user=MQTT_USERNAME, 
            password=MQTT_PASSWORD,
            port=BROKER_PORT,
            ssl=True, 
            ssl_params=ssl_params, 
            keepalive=60
        )
        
        print(f"[MQTT] Intentando conectar a {BROKER_HOST}:{BROKER_PORT}...")
        connect_timeout = 10
        while connect_timeout > 0:
            try:
                client.connect()
                print(f"[MQTT] Conectado al broker seguro. ID: {MQTT_CLIENT_ID}")
                return client
            except OSError as e:
                toggle_led() 
                print('.', end='')
                utime.sleep(1)
                connect_timeout -= 1
        
        print(f"[MQTT] Falló la conexión segura al broker después de {10} segundos.")
        return None

    except Exception as e:
        print(f"[MQTT] ERROR de conexión segura al broker: {type(e).__name__}: {e}")
        return None

def send_mqtt_fall_alert(accel_magnitude, lat, lon): 
    global mqtt_client 

    if mqtt_client is None:
        print("[MQTT] Cliente no inicializado. Alerta MQTT omitida.")
        return

    try:
        payload_data = {
            "timestamp": utime.time(),
            "event": "CRITICAL_FALL",
            "impact_G": accel_magnitude,
            "device_id": MQTT_CLIENT_ID,
            "location": {"lat": lat, "lon": lon}
        }
        
        payload_json = ujson.dumps(payload_data)
        
        print("-" * 50)
        print(f"[MQTT] Intentando publicar en tópico: {MQTT_TOPIC_FALL}")
        print(f"[MQTT] Payload JSON: {payload_json}")
        print("-" * 50)
        
        mqtt_client.publish(MQTT_TOPIC_FALL, payload_json.encode('utf-8'))
        print(f"[MQTT] Publicada alerta de caída.")

    except Exception as e:
        print(f"[MQTT] Error CRÍTICO al publicar la alerta: {type(e).__name__}: {e}. Intentando reconectar...")
        
        try:
            mqtt_client.disconnect()
        except:
            pass
        mqtt_client = mqtt_connect_secure() 



#FUNCIONES DE ALERTA Y LÓGICA DE CAÍDA

def send_telegram_alert(lat, lon, is_fall_alert=False):
    """
    Envía alertas a Telegram (Geocerca o Caída).
    """
    if not do_connect(WIFI_SSID, WIFI_PASSWORD):
        print("[TELEGRAM] ERROR: No se pudo reconectar al Wi-Fi. Alerta de Telegram fallida.")
        return
        
    maps_link = f"https://www.google.com/maps?q={lat:.6f},{lon:.6f}"
    
    if is_fall_alert:
        subject = "¡ALERTA CRÍTICA: CAÍDA DETECTADA!"
        body = "Se ha detectado una caída fuerte. ¡Verifique el estado del paciente inmediatamente!"
    else:
        subject = "¡ALERTA DE GEOCERCA!"
        body = "El rastreador ha salido de la zona segura."
        
    message = (
        f"{subject}\n"
        f"{body}\n"
        f"Última Ubicación: {lat:.6f}, {lon:.6f}\n"
        f"[Ver Ubicación Exacta]({maps_link})"
    )
    
    encoded_message = message.replace('\n', '%0A').replace(' ', '%20').replace('(', '%28').replace(')', '%29')

    url_text = (
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        f"?chat_id={TELEGRAM_CHAT_ID}"
        f"&text={encoded_message}"
        f"&parse_mode=Markdown" 
    )
    
    try:
        r_text = urequests.get(url_text)
        print(f"[TELEGRAM] Mensaje de {'CAÍDA' if is_fall_alert else 'GEOCERCA'} enviado.")
        r_text.close()
    except Exception as e:
        print(f"[TELEGRAM] Error al enviar mensaje: {e}")
        
    try:
        url_location = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendLocation"
        payload_loc = {"chat_id": TELEGRAM_CHAT_ID, "latitude": lat, "longitude": lon}
        r_loc = urequests.post(url_location, json=payload_loc)
        print("[TELEGRAM] Pin de ubicación enviado.")
        r_loc.close()
    except Exception as e:
        print(f"[TELEGRAM] Error al enviar Pin: {e}")


def send_alert_to_make(lat, lon, distance):
    """Dispara un Webhook HTTP POST directo a Make para notificar la alerta de Geocerca."""
    try:
        alert_payload = {
            "device_label": UBIDOTS_DEVICE_LABEL, "latitude": lat, "longitude": lon, 
            "distance_m": distance, "message": "ALERTA: RASTREADOR FUERA DE ZONA SEGURA"
        }
        response = urequests.post(MAKE_WEBHOOK_URL, json=alert_payload)
        if response.status_code == 200:
            print("[MAKE] Alerta de Geocerca enviada.")
        else:
            print(f"[MAKE] Fallo al enviar a Make. Estado: {response.status_code}")
        response.close()
    except Exception as e:
        print(f"[MAKE] Error en el Webhook a Make: {e}")


def check_for_fall(mpu_sensor):
    """
    Detecta una posible caída libre seguida de un impacto usando la aceleración total (magnitud).
    """
    global fall_start_time, last_fall_time
    
    if mpu_sensor is None: return 0.0, False

    try:
        accel = mpu_sensor.get_accel_data()
        accel_magnitude = (accel['x']**2 + accel['y']**2 + accel['z']**2)**0.5
        current_time = utime.ticks_ms()
        is_fall = False 

        if utime.ticks_diff(current_time, last_fall_time) < FALL_COOLDOWN_MS:
            return accel_magnitude, False
        
        if accel_magnitude > INSTANT_IMPACT_G:
            is_fall = True
            print("=====================================================")
            print(f"¡CAÍDA DETECTADA! (IMPACTO INSTANTÁNEO: {accel_magnitude:.2f} G)")
            print("=====================================================")
            
        elif fall_start_time != 0 and utime.ticks_diff(current_time, fall_start_time) >= DURATION_MS:
            if accel_magnitude > IMPACT_THRESHOLD_G:
                is_fall = True
                print("=====================================================")
                print(f"¡CAÍDA DETECTADA! (SEC. LIBRE + BAJO IMPACTO: {accel_magnitude:.2f} G)")
                print("=====================================================")
            else:
                print(f"[CAÍDA] Zero-G completado, pero impacto bajo ({accel_magnitude:.2f} G). Falsa alarma.")
                fall_start_time = 0
                
        elif accel_magnitude < MPU_THRESHOLD_G:
            if fall_start_time == 0:
                fall_start_time = current_time
                print(f"[CAÍDA] Zero-G iniciado ({accel_magnitude:.2f} G). Esperando {DURATION_MS}ms...")
                
        elif fall_start_time != 0 and accel_magnitude >= INTERRUPT_THRESHOLD_G:
            print(f"[CAÍDA] Zero-G INTERRUMPIDO: Acel. = {accel_magnitude:.2f} G (Debe ser < {MPU_THRESHOLD_G} G para caer).")
            fall_start_time = 0
            
        if is_fall:
            fall_start_time = 0 
            last_fall_time = current_time
            
            if last_valid_lat is not None:
                send_mqtt_fall_alert(accel_magnitude, last_valid_lat, last_valid_lon) 
            
            return accel_magnitude, True
            
    except Exception as e:
        print(f"[MPU] Error al leer MPU-6050 en el bucle: {e}")
        fall_start_time = 0 
    
    return accel_magnitude, False 


def process_and_publish(lat, lon):
    is_published = False
    

    if not do_connect(WIFI_SSID, WIFI_PASSWORD):
        print("[HTTP] Publicación y Geocerca fallida: No hay conexión Wi-Fi.")
        return False
        
    distance = calculate_distance(lat, lon, HOME_LAT, HOME_LON)
    alerta_status = 1 if distance > SAFE_RADIUS_M else 0
    
    print(f"[GEO] Distancia al hogar: {distance:.1f}m. Alerta: {'OUT' if alerta_status == 1 else 'IN'}")

    try:
        payload_data = {
            "gps": {
                "value": 1, 
                "context": {"lat": lat, "lng": lon}
            },
            "alerta_zona": alerta_status
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-Auth-Token": UBIDOTS_TOKEN
        }
        
        response = urequests.post(
            HTTP_PUBLISH_URL, 
            json=payload_data, 
            headers=headers
        )
        
        if response.status_code < 400:
            print(f"[HTTP] Ubidots OK. Lat/Lon: {lat:.6f}, {lon:.6f}")
            is_published = True
        else:
            print(f"[HTTP] Error Ubidots: {response.status_code}")
            
        response.close()
            
    except Exception as e:
        print(f"[HTTP] Error de red Ubidots: {e}")
    
    if is_published and alerta_status == 1:
        send_telegram_alert(lat, lon, is_fall_alert=False)
        send_alert_to_make(lat, lon, distance)
        
    return is_published


#FUNCIÓN PRINCIPAL DE RASTREO

def main():
    
    global last_valid_lat, last_valid_lon, mpu_sensor, last_debug_time_ms, mqtt_client
    
    set_led_off()
    
    wifi_ok = do_connect(WIFI_SSID, WIFI_PASSWORD)
    
    if not wifi_ok: 
        set_led_off()
        return
    
    set_time_ntp() 
    
    mqtt_client = mqtt_connect_secure()
    mqtt_is_connected = mqtt_client is not None
    if wifi_ok and mqtt_is_connected:
        set_led_solid_on() 
        print("[LED] Ambas conexiones (Wi-Fi y MQTT) OK. LED encendido fijo.")
    else:
        set_led_off() 
        print("[LED] No se pudo establecer una o ambas conexiones principales. LED apagado.")
        
    if not initialize_mpu():
        print("[MPU] Sistema anticaídas no operativo. Procediendo solo con GPS/Geocerca.")

    print("\n" + "="*70)
    print("INICIO: Rastreo GPS con Geocerca, Caídas y MQTT")
    print("======================================================================")
    
    start_time = utime.time()
    fix_achieved = False 
    last_publish_time = 0
    PUBLISH_INTERVAL_SEC = 60 
    
    while True:
        current_time_ms = utime.ticks_ms()
        
        if mqtt_client:
            try:
                mqtt_client.check_msg() 
            except Exception as e:
                print(f"[MQTT] Fallo en el loop: {e}. Intentando reconectar...")
                try:
                    mqtt_client.disconnect()
                except:
                    pass
                mqtt_client = mqtt_connect_secure()
        
        len_data = GPS_UART.any()
        if len_data > 0:
            data = GPS_UART.read(len_data)
            for char in data: my_gps.update(chr(char))
                
            latitude = my_gps.latitude[0]
            longitude = my_gps.longitude[0]
            satellites = my_gps.satellites_in_use
            
            is_valid_position = (
                my_gps.fix_type > 0 and 
                (latitude != 0.0 or longitude != 0.0) and 
                satellites > 1
            )

            if is_valid_position:
                
                if FORCE_NEGATIVE_LAT and latitude > 0: latitude *= -1
                if FORCE_NEGATIVE_LON and longitude > 0: longitude *= -1
                
                last_valid_lat = latitude
                last_valid_lon = longitude
                
                if not fix_achieved:
                    ttff = utime.time() - start_time
                    fix_achieved = True
                    print("\n" + "#"*70)
                    print(f"      ¡FIX OBTENIDO! TTFF: {ttff} segundos.")
                    print("#"*70)
                    
            elif not fix_achieved:
                print(f"Buscando FIX... Satélites visibles: {my_gps.satellites_visible}. Segundos: {utime.time() - start_time}", end='\r')
                
        if mpu_sensor is not None:
            accel_mag, is_fall = check_for_fall(mpu_sensor)
            
            if utime.ticks_diff(current_time_ms, last_debug_time_ms) >= DEBUG_INTERVAL_MS:
                if fix_achieved: 
                    is_cooldown = utime.ticks_diff(current_time_ms, last_fall_time) < FALL_COOLDOWN_MS
                    status = "En Caída Libre" if fall_start_time != 0 else "Estable"
                    status = "COOLDOWN" if is_cooldown else status
                    
                    print(f"[MPU-DEBUG] Acel. Mag: {accel_mag:.2f} G. Estado: {status}")
                last_debug_time_ms = current_time_ms

            if is_fall:
                if last_valid_lat is not None:
                    send_telegram_alert(last_valid_lat, last_valid_lon, is_fall_alert=True)

        current_time_s = utime.time()
        if last_valid_lat is not None and (current_time_s - last_publish_time >= PUBLISH_INTERVAL_SEC):
            
            process_and_publish(last_valid_lat, last_valid_lon) 
            last_publish_time = current_time_s
            
        utime.sleep_ms(10) 

try:
    main()
except KeyboardInterrupt:
    print("\nPrograma detenido por el usuario.")
finally:
    if 'GPS_UART' in locals() and GPS_UART is not None:
        GPS_UART.deinit()
    if mqtt_client:
        try:
            mqtt_client.disconnect()
            print("[MQTT] Cliente MQTT desconectado.")
        except:
            pass
    set_led_off() 
    print("Comunicación terminada.")
