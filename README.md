Este repositorio contiene el firmware para el microPython, los scripts de backend de python y la base de datos
para desarrollar un dispositivo wearable para detectar caidas y geolocalizar a personas mayores.
Tambien se presenta el modelo 3D usado para la carcasa del proyecto y el archivo para la placa PCB.

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


