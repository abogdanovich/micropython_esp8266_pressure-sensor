"""
Settings for project to track all in one place
- WIFI
- MQTT
"""

# WIFI credentials
WIFI_LOGIN = ''
WIFI_SSID = 'nc-main'
WIFI_PASSWORD = 'sensorium'

# MQTT connection data
MQTT_CLIENT_ID = 'pressure_sensor'
MQTT_SERVER_URL = '523d06922fa4.sn.mynetname.net'
MQTT_SERVER_PORT = 1182
MQTT_SERVER_USERNAME = 'smarty'
MQTT_SERVER_USERPASSWORD = 'sensorium'
MQTT_SERVER_INFO_TOPIC = 'smarty/garage/sensor/pressure/info'

# LCD i2c interface pins
I2C_SCL = 5
I2C_SDA = 4
LCD_WIDTH = 128
LCD_HEIGHT = 32

# ADC pin
ADC_PIN = 0

# pins
RELAY = 14

