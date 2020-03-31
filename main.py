# Available pins are: 0, 1, 2, 3, 4, 5, 12, 13, 14, 15, 16, which correspond to the actual GPIO pin numbers of
# ESP8266 chip

import utils
from settings import settings
import utime
import machine

lcd = utils.i2c_setup()
voltage_step = 0.004887  # 1023 / 5v - voltage_step
low_pressure_value = 4  # low pressure level. water accumulator pressure should low_pressure - 10%
high_pressure_value = 5  # high pressure - top to turn off relay \ water pump
current_pressure = 0  # current one

# settings filename
settings_file_name = "settings.txt"

min_raw_value = 100  # min level for sensor - by default it's 130 - less is like error
max_raw_value = 800  # high pressure level ~8.4 bar

# shifting values
pressure_shift = 130  # 0.5v for sensor is output by default

# pump working seconds|hours|days
working_seconds = 0
working_hours = 0
working_days = 0

# alert messages
system_error_status = False

# working status
is_pump_working = False

# board pins setup
relay = machine.Pin(settings.RELAY, machine.Pin.OUT)
adc = machine.ADC(settings.ADC_PIN)


def read_settings_from_file(filename):
    global low_pressure_value
    global high_pressure_value
    # return value [low_pressure_value, high_pressure_value]
    try:
        with open(filename, mode="r") as f:
            data = f.read()
    except OSError as e:
        with open(filename, mode="rw") as f:
            data = "{}|{}".format(low_pressure_value, high_pressure_value)
            f.write(data)

    # load values from settings file and update them
    pressure_thresholds = data.split("|")
    low_pressure_value = pressure_thresholds[0]
    high_pressure_value = pressure_thresholds[1]


def read_working_seconds(filename):
    global working_seconds
    global working_hours
    global working_days
    try:
        with open(filename, mode="r") as f:
            data = f.read()
    except OSError as e:
        data = 0

    # load values from settings file and update them
    working_data = data.split("|")
    working_seconds = working_data[0]
    working_hours = working_data[1]
    working_days = working_data[2]


def write_working_seconds(filename, data):
    # write working seconds
    with open(filename, mode="rw") as f:
        f.write(data)


def save_data_to_file(filename, data):
    with open(filename, mode="rw") as f:
        f.write(data)


def publish_msg(mqtt_client, msg):
    mqtt_client.publish(settings.MQTT_SERVER_INFO_TOPIC, msg, retain=True)


def turn_OFF_pump():
    relay.value(0)


def turn_ON_pump():
    relay.value(1)


def check_sensor_health(data):
    # extra verification of water pump to safety switch off in any other non working parameters
    if data >= max_raw_value or data <= min_raw_value:
        # switch off relay just to be sure that we're safe
        turn_OFF_pump()
        return False
    return True


def check_high_pressure_value(data):
    if data >= high_pressure_value:
        # if something goes wrong and we have a high pressure - let's stop the whole system
        turn_OFF_pump()
        return False
    return True


def calculate_pressure(data):
    pressure_in_voltage = (data * voltage_step)
    pressure_pascal = (3.0 * (pressure_in_voltage - 0.47)) * 1000000.0
    current_pressure_value = pressure_pascal / 10e5
    if current_pressure_value < 0:
        current_pressure_value = 0
    return current_pressure_value


def main():
    turn_OFF_pump()

    # set global params
    global system_error_status
    global current_pressure

    # load values from settings file
    read_settings_from_file(settings_file_name)

    # set a timer
    timer = utime.ticks_ms()

    try:
        ifconfig = utils.wifi_setup()
        mqtt_client = utils.mqtt_setup()
    except OSError as e:
        utils.module_reset()
    while True:
        try:
            tick = utime.ticks_ms()

            if tick - timer > 200:
                lcd.fill(0)

                timer = utime.ticks_ms()
                # read data
                raw_pressure = adc.read()

                if not check_sensor_health(raw_pressure) and not system_error_status:
                    # something is wrong - need to inform and turn off pump
                    error_msg = "Error! High or Low pressure!"
                    publish_msg(mqtt_client, error_msg)
                    lcd.text(error_msg, 10, 10)
                    publish_msg(mqtt_client, error_msg)
                    # mark system error
                    system_error_status = True

                # get clear current sensor value
                shifted_pressure_value = raw_pressure - pressure_shift

                if not check_high_pressure_value(current_pressure) and not system_error_status:
                    # something is wrong - need to inform and turn off pump
                    error_msg = "Error! High pressure sensor!"
                    publish_msg(mqtt_client, error_msg)
                    lcd.text(error_msg, 10, 10)
                    # mark system error
                    system_error_status = True

                # if all is ok - let's calculate pressure
                if not system_error_status:
                    # check what to do with pump

                    # calculate pressure value
                    current_pressure = calculate_pressure(shifted_pressure_value)
                    # TODO remove testing value
                    current_pressure = round(4.5348734, 1)

                    # draw lcd value
                    lcd_msg = "{} Bar".format(current_pressure)
                    lcd.text(lcd_msg, 10, 10)
                    # and send data to mqtt broker
                    # TODO update
                    publish_msg(mqtt_client, "{} bar".format("{}-{}".format(low_pressure_value, high_pressure_value)))
                else:
                    error_msg = "System Error! Check sensor"
                    lcd.text(error_msg, 10, 10)

                # update display
                lcd.show()

        except OSError as e:
            utils.module_reset()


if __name__ == '__main__':
    main()
