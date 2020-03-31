# Available pins are: 0, 1, 2, 3, 4, 5, 12, 13, 14, 15, 16, which correspond to the actual GPIO pin numbers of
# ESP8266 chip

import utils
from settings import settings
import utime
import machine

lcd = utils.i2c_setup()
VOLTAGE_STEP = 0.004887

def checkSensorHealth(data):
    pass


def checkHighPressureValue(data):
    pass


def calculate_pressure(data):
    pressure_in_voltage = (data * VOLTAGE_STEP)
    pressure_pascal = (3.0 * (pressure_in_voltage - 0.47)) * 1000000.0
    current_pressure_value = pressure_pascal / 10e5
    if current_pressure_value < 0:
        current_pressure_value = 0
    return current_pressure_value


def main():
    # setup
    timer = utime.ticks_ms()
    pressure_shift = 130
    raw_pressure = 0
    system_error = False

    # some useful variables :)
    low_pressure_value = 4
    high_pressure_value = 5
    current_pressure = 0


    try:
        adc = machine.ADC(settings.ADC_PIN)
        relay = machine.Pin(settings.RELAY, machine.Pin.OUT)

        ifconfig = utils.wifi_setup()
        mqtt_client = utils.mqtt_setup()

        # relay.value(1)    # turn on
    except OSError as e:
        utils.module_reset()
    while True:
        try:
            tick = utime.ticks_ms()
            if tick - timer > 200:
                timer = utime.ticks_ms()
                raw_pressure = adc.read()
                lcd.fill(0)
                data = raw_pressure - pressure_shift

                checkSensorHealth(data)
                checkHighPressureValue(data)

                if not system_error:
                    pressure = calculate_pressure(data)
                    lcd.text("{} Bar".format(pressure), 10, 10)
                else:
                    lcd.text("System Error!", 10, 10)
                lcd.show()
                mqtt_msg = "{} bar".format(pressure)
                mqtt_client.publish(settings.MQTT_SERVER_INFO_TOPIC, mqtt_msg)

        except OSError as e:
            utils.module_reset()


if __name__ == '__main__':
    main()
