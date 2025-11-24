Este repositorio contiene el firmware para el microPython, los scripts de backend de python y la base de datos
para desarrollar un dispositivo wearable para detectar caidas y geolocalizar a personas mayores.
Tambien se presenta el modelo 3D usado para la carcasa del proyecto de un archivo solidworks, el archivo para la placa PCB y un PDF que muestra las pruebas que se realizaron para el proyecto.

El proyecto opera bajo una arquitectura de Edge Computing y Nube segura.
Los componentes requeridos son:
Raspberry Pi Pico W: Adquisición de sensores, procesamiento de algoritmos y gestion de Wi-Fi.
Sensor MPU-6050: Sensor dedicado a la deteccion de caidas. Usado en el algoritmo hibrido.
Modulo GPS NEO-M8L: Modulo usado para la geolocalizacion, ubicacion en tiempo real y la geocerca.

Respecto a servicios externos en la web es necesario tener una cuenta en HiveMQ, MongoDB, Ubidots,Make y Telegram.

Para el firmware de la Raspberry Pi Pico W se requiere que sea MicroPython. 

Las librerias necesarias que tienen que instalar son:
umqtt.simple.py: Cliente MQTT para la comunicacion con HiveMQ.
urequests.py: Para peticiones HTTP a Ubidots, Make y Telegram.
ntptime.py: Necesario para la sincronizacion horaria, con esto se realiza la conexion SSL/TLS.
mpu6050.py: Driver de la libreria para poder leer el sensor dedicado a las caidas.
micropyGPS.py: Driver de la libreria para el modulo GPS.

En la imagen llamada circuito se puede ver las conexiones de la raspberry pi pico w con los sensores.

Cambios importantes en el main.py
Se tienen que actualizar las credenciales de cada persona. 
Como ser el nombre de la red y su contrasena: WIFI_SSID y WIFI_PASSWORD
Las credenciales de HiveMQ: BROKER_HOST, MQTT_USERNAME, MQTT_PASSWORD
Las credenciales de Ubidots: UBIDOTS_TOKEN
La URL del webhook de Make: MAKE_WEBHOOK_URL
Las credenciales de Telegram: TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID
La configuracion de las coordenadas de la geocerca: HOME_LAT y HOME_LON

Para los scripts de Python de la Pc que son necesarios para la base de datos es necesario instalar las librerias para el suscriptor:
pip install paho-mqtt pymongo pandas

En MongoDb hay que configurar el acceso a la red, esto se realiza asegurando que el acceso este abierto mediante la siguiente IP: 0.0.0.0/0

Actualizar el MONGO_URI de ambos scripts de python.

De igual manera se presenta los planos de los modelos 3D
