# mpu6050.py - Driver para el sensor de aceleración/giroscopio MPU-6050
# Adaptado para MicroPython (I2C)

from machine import Pin, I2C
import utime

class MPU6050:
    
    # Registros del MPU-6050
    PWR_MGMT_1 = 0x6B
    SMPLRT_DIV = 0x19
    CONFIG = 0x1A
    GYRO_CONFIG = 0x1B
    INT_ENABLE = 0x38
    ACCEL_XOUT_H = 0x3B
    TEMP_OUT_H = 0x41
    GYRO_XOUT_H = 0x43
    
    # Dirección I2C del MPU-6050. Puede ser 0x68 o 0x69.
    # El valor por defecto es 0x68 (si AD0 está a GND).
    I2C_ADDR = 0x68 

    def __init__(self, i2c):
        self.i2c = i2c
        self.i2c.writeto(self.I2C_ADDR, bytearray([self.PWR_MGMT_1, 0])) # Despertar MPU-6050
        self.i2c.writeto(self.I2C_ADDR, bytearray([self.SMPLRT_DIV, 0x07])) # Frecuencia de muestreo 1kHz
        self.i2c.writeto(self.I2C_ADDR, bytearray([self.CONFIG, 0])) # Config: LPF 260Hz
        self.i2c.writeto(self.I2C_ADDR, bytearray([self.GYRO_CONFIG, 0x18])) # Gyro: 2000dps (Para sensibilidad máxima, 0x18)
        self.i2c.writeto(self.I2C_ADDR, bytearray([self.INT_ENABLE, 0x01])) # Habilitar interrupciones

    def read_raw_data(self, addr):
        """Lee dos bytes (High y Low) de un registro y los combina en un entero con signo."""
        high = self.i2c.readfrom_mem(self.I2C_ADDR, addr, 1)
        low = self.i2c.readfrom_mem(self.I2C_ADDR, addr + 1, 1)
        value = (high[0] << 8) | low[0]
        
        # Convertir a valor con signo de 16 bits (complemento a dos)
        if (value > 32768):
            value = value - 65536
        return value

    def get_accel_data(self):
        """Devuelve los valores de aceleración en raw counts."""
        ax = self.read_raw_data(self.ACCEL_XOUT_H)
        ay = self.read_raw_data(self.ACCEL_XOUT_H + 2)
        az = self.read_raw_data(self.ACCEL_XOUT_H + 4)
        
        # Conversión a G's (usando FS_SEL=0, que es +/- 2g).
        # Aunque el registro GYRO_CONFIG lo cambiamos a 2000dps, 
        # para el acelerómetro usaremos 16384.0 como divisor para 2g
        # Si cambiamos el rango, este divisor debe cambiar.
        
        accel_scale = 16384.0 # Divisor para +/- 2g
        
        return {
            'x': ax / accel_scale,
            'y': ay / accel_scale,
            'z': az / accel_scale
        }

    def get_gyro_data(self):
        """Devuelve los valores de giroscopio en grados por segundo (dps)."""
        gx = self.read_raw_data(self.GYRO_XOUT_H)
        gy = self.read_raw_data(self.GYRO_XOUT_H + 2)
        gz = self.read_raw_data(self.GYRO_XOUT_H + 4)
        
        # Conversión a dps (usando FS_SEL=3, que es +/- 2000dps, divisor 16.4)
        gyro_scale = 16.4 

        return {
            'x': gx / gyro_scale,
            'y': gy / gyro_scale,
            'z': gz / gyro_scale
        }

# --- Ejemplo de uso de prueba (Opcional) ---
if __name__ == '__main__':
    # Configuración I2C: GP4 (SDA), GP5 (SCL)
    i2c_bus = I2C(0, scl=Pin(5), sda=Pin(4), freq=400000)
    
    # Búsqueda de dispositivos para confirmar conexión
    devices = i2c_bus.scan()
    if MPU6050.I2C_ADDR not in devices:
        print("❌ MPU-6050 no encontrado en la dirección 0x68 o I2C mal conectado.")
    else:
        print("✅ MPU-6050 detectado. Inicializando...")
        sensor = MPU6050(i2c_bus)
        
        while True:
            accel = sensor.get_accel_data()
            print(f"Aceleración (G): X={accel['x']:.2f}, Y={accel['y']:.2f}, Z={accel['z']:.2f} | Acel. Total: {((accel['x']**2 + accel['y']**2 + accel['z']**2)**0.5):.2f} G")
            utime.sleep_ms(500)