"""
Utility to setup some environment
"""
import time
import machine
import network
import urandom
from libs import ssd1306
from libs.umqtt_simple import MQTTClient
from settings import settings

wlan = network.WLAN(network.STA_IF)


pressure_setting_via_mqtt = []
control_data_via_mqtt = None


# setup callback for income messages
def mqtt_setup_callback(topic, msg):
    global pressure_setting_via_mqtt
    global control_data_via_mqtt
    if topic.decode() == settings.MQTT_SERVER_INFO_SETTINGS:
        data = msg.decode().split("|")
        if len(data) == 2 and float(data[0]) > 0.0 and float(data[1]) > 0.0:
            pressure_setting_via_mqtt = data

    elif topic.decode() == settings.MQTT_SERVER_INFO_CONTROL:
        # 1 - on - 0 - off
        data = msg.decode()
        if int(data) is not None:
            control_data_via_mqtt = int(data)


# run WIFI module and connect to wifi router
def wifi_setup():
    if not wlan.isconnected():
        wlan.active(True)
        wlan.connect(settings.WIFI_SSID, settings.WIFI_PASSWORD)
        while not wlan.isconnected():
            pass
    return wlan.ifconfig()


# check that wifi is connected
def wifi_is_connected():
    if not wlan.isconnected():
        wifi_setup()


# setup MQTT bridge
def mqtt_setup():
    client = MQTTClient(settings.MQTT_CLIENT_ID, settings.MQTT_SERVER_URL, settings.MQTT_SERVER_PORT)
    client.set_callback(mqtt_setup_callback)
    client.connect()
    client.publish(settings.MQTT_SERVER_INFO_TOPIC, '{} is loaded'.format(settings.MQTT_CLIENT_ID), False, 0)
    client.subscribe(settings.MQTT_SERVER_INFO_CONTROL)  # topic to control relay
    client.subscribe(settings.MQTT_SERVER_INFO_SETTINGS)  # topic for income settings low|high values
    return client


# setup i2c interface
def i2c_setup():
    i2c = machine.I2C(-1, scl=machine.Pin(settings.I2C_SCL), sda=machine.Pin(settings.I2C_SDA))
    lcd = ssd1306.SSD1306_I2C(settings.LCD_WIDTH, settings.LCD_HEIGHT, i2c)
    lcd.fill(0)  # clear screen
    lcd.text('lcd init!', (int(settings.LCD_WIDTH / 2)) - 30, int(settings.LCD_HEIGHT / 2))
    lcd.show()
    return lcd


def adc_setup():
    adc = machine.ADC(settings.ADC_PIN)
    return adc


def adc_read_data(adc):
    return adc.read()


def module_reset():
    time.sleep(1)
    machine.reset()


def randint(min, max):
    span = max - min + 1
    div = 0x3fffffff // span
    offset = urandom.getrandbits(30) // div
    val = min + offset
    return val
