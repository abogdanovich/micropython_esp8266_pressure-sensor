"""
Mechanical relay is replaced with esp8266 + SSD relay + micro-python logic
Using mqtt broker we send the data via data protocol and can see what we have
# Available pins are: 0, 1, 2, 3, 4, 5, 12, 13, 14, 15, 16, which correspond to the actual GPIO pin numbers of
# ESP8266 chip
"""
import utils
from settings import settings
import utime
import machine

lcd = utils.i2c_setup()
voltage_step = 0.004887  # 1023 / 5v - voltage_step
low_pressure_value = 4.0  # low pressure level. water accumulator pressure should low_pressure - 10%
high_pressure_value = 5.0  # high pressure - top to turn off relay \ water pump
current_pressure = 0.0  # current one

# data files
settings_file_name = "settings.txt"
working_time_file_name = "working_data.txt"

min_raw_value = 100  # min level for sensor - by default it's 130 - less is like error
max_raw_value = 800  # high pressure level ~8.4 bar

# shifting values
pressure_shift_raw = 130  # 0.5v for sensor is output by default
voltage_offset = 0.5

# pump working seconds|hours|days
working_seconds = 0
working_minutes = 0
working_hours = 0
working_days = 0

# timer for working seconds
working_timer = 0

# alert messages
system_error_status = False

# working status
is_pump_working = False

# board pins setup
relay = machine.Pin(settings.RELAY, machine.Pin.OUT)
adc = machine.ADC(settings.ADC_PIN)


def read_settings_from_file(filename):
    """Read file settings and set to variables"""
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
    low_pressure_value = float(pressure_thresholds[0])
    high_pressure_value = float(pressure_thresholds[1])


def read_working_time(filename):
    """Read file with stored working minutes|hours|days"""
    global working_minutes
    global working_hours
    global working_days
    try:
        with open(filename, mode="r") as f:
            data = f.read()
    except OSError as e:
        data = "0|0|0"

    # load values from settings file and update them
    working_data = data.split("|")
    working_minutes = int(working_data[0])
    working_hours = int(working_data[1])
    working_days = int(working_data[2])


def calc_pump_working_time(pump_started_timer_ms, mqtt_client):
    """Count working time and store into file"""
    global working_seconds
    global working_minutes
    global working_hours
    global working_days

    save_to_file = False
    current_new_working_seconds = round((utime.ticks_ms() - pump_started_timer_ms) / 1000, 0)
    working_seconds += current_new_working_seconds
    if working_seconds >= 60:
        working_minutes += 1
        working_seconds = 0
        # let's say that we can update our file to do not miss important update
        save_to_file = True

    if working_minutes >= 60:
        working_hours += 1
        working_minutes = 0

    if working_hours >= 24:
        working_days += 1
        working_hours = 0

    if save_to_file:
        working_data = "{}|{}|{}".format(
            working_minutes,
            working_hours,
            working_days
        )
        publish_time(mqtt_client, "{}m{}h{}d".format(
            working_minutes,
            working_hours,
            working_days
        ))
        write_working_time(working_time_file_name, working_data)


def write_working_time(filename, data):
    """Write working seconds"""
    with open(filename, mode="rw") as f:
        f.write(data)


def save_settings(filename, data):
    """Save something into file. For example: save settings like low|high value in float format"""
    with open(filename, mode="rw") as f:
        f.write(data)


def publish_info(mqtt_client, msg):
    """Send message to mqtt broker"""
    mqtt_client.publish(settings.MQTT_SERVER_INFO_TOPIC, msg, retain=True)


def publish_time(mqtt_client, msg):
    """Send message to mqtt broker"""
    mqtt_client.publish(settings.MQTT_SERVER_INFO_WORKING_TIME, msg, retain=True)


def turn_OFF_pump():
    relay.value(0)


def turn_ON_pump():
    relay.value(1)


def check_sensor_health(data: float):
    """Extra verification of water pump to safety switch off in any other non working parameters"""
    if data >= max_raw_value or data <= min_raw_value:
        # switch off relay just to be sure that we're safe
        turn_OFF_pump()
        return False
    return True


def check_high_pressure_value(data: float):
    """That method terminates water pump if something goes wrong with other verification method"""
    if data > high_pressure_value:
        # if something goes wrong and we have a high pressure - let's stop the whole system
        turn_OFF_pump()
        return False
    return True


def calculate_pressure(data: float):
    """Pressure calculation rules"""
    # formula: Pbar=(VALadc*1/(1023*D)-Offset)*Vbar
    pressure_in_voltage = (data * voltage_step)
    pressure_pascal = (3.0 * (pressure_in_voltage - voltage_offset)) * 1000000.0
    current_pressure_value = pressure_pascal / 10e5
    if current_pressure_value < 0.0:
        current_pressure_value = 0.0
    return current_pressure_value


def check_what_todo_with_pressure(pressure_value, mqtt_client):
    """Check what to do with pressure - turnoff, turnon water pump, etc..."""
    global is_pump_working
    global working_timer
    if pressure_value < low_pressure_value and not is_pump_working:
        turn_ON_pump()
        is_pump_working = True
        # start working timer
        working_timer = utime.ticks_ms()

    if pressure_value >= high_pressure_value and is_pump_working:
        turn_OFF_pump()
        is_pump_working = False
        calc_pump_working_time(working_timer, mqtt_client)


def draw_vline(x, y, width):
    for i in range(1, width):
        lcd.pixel(x, y + i, 1)


def draw_hline(x, y, width):
    for i in range(1, width):
        lcd.pixel(x + i, y, 1)


def update_display():
    """Update lcd screen and draw values"""
    msg1 = "{} bar".format(high_pressure_value)
    lcd.text(msg1, 0, 2)

    msg1 = "{} bar".format(current_pressure)
    lcd.text(msg1, 0, 12)

    msg1 = "{} bar".format(low_pressure_value)
    lcd.text(msg1, 0, 22)

    draw_vline(60, 0, width=settings.LCD_HEIGHT)
    # draw_hline(0, settings.LCD_HEIGHT-1, width=settings.LCD_WIDTH)

    msg1 = "{} min".format(working_minutes)
    lcd.text(msg1, 65, 2)

    msg1 = "{} hour".format(working_hours)
    lcd.text(msg1, 65, 12)

    msg1 = "{} days".format(working_days)
    lcd.text(msg1, 65, 22)

    if is_pump_working:
        lcd.invert(1)
    else:
        lcd.invert(0)


def get_analog_data():
    """Return median for the list of values"""
    raw_data = []
    for i in range(1, 5):
        raw_data.append(adc.read())
        utime.sleep_ms(50)
    raw_data.sort()
    return raw_data[round(len(raw_data) / 2)]

# FIXME fix 0.6 bar deviation (check starting value, check resistors and calculation method)


def check_control_via_mqtt():
    if utils.control_data_via_mqtt == 1:
        turn_ON_pump()
        utils.control_data_via_mqtt = None
    elif utils.control_data_via_mqtt == 0:
        turn_OFF_pump()
        utils.control_data_via_mqtt = None


def check_mqtt_settings_update():
    """Update settings via MQTT channel"""
    global low_pressure_value
    global high_pressure_value
    data_low_high = utils.pressure_setting_via_mqtt

    if data_low_high != [low_pressure_value, high_pressure_value] and len(data_low_high) == 2:
        low_pressure_value = float(data_low_high[0])
        high_pressure_value = float(data_low_high[1])
        save_settings(settings_file_name, "{}|{}".format(low_pressure_value, high_pressure_value))


def main():
    """Main method with loop"""
    turn_OFF_pump()

    # read and update local counter after reboot
    read_working_time(working_time_file_name)

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
                mqtt_client.check_msg()

                # check settings via mqtt
                check_mqtt_settings_update()
                check_control_via_mqtt()

                timer = utime.ticks_ms()
                # read data
                raw_pressure = get_analog_data()

                if not check_sensor_health(raw_pressure) and not system_error_status:
                    # something is wrong - need to inform and turn off pump
                    error_msg = "Error! High or Low pressure!"
                    publish_info(mqtt_client, error_msg)
                    lcd.text(error_msg, 10, 10)
                    publish_info(mqtt_client, error_msg)
                    # mark system error
                    system_error_status = True

                if not check_high_pressure_value(current_pressure) and not system_error_status:
                    # something is wrong - need to inform and turn off pump
                    error_msg = "Error! High pressure sensor!"
                    publish_info(mqtt_client, error_msg)
                    lcd.text(error_msg, 10, 10)
                    # mark system error
                    system_error_status = True

                # if all is ok - let's calculate pressure
                if not system_error_status:
                    # check what to do with pump

                    # calculate pressure value
                    current_pressure = calculate_pressure(raw_pressure)

                    check_what_todo_with_pressure(current_pressure, mqtt_client)

                    # draw lcd value
                    update_display()
                    # and send data to mqtt broker
                    publish_info(mqtt_client, "{} Bar".format(current_pressure))
                else:
                    error_msg = "System Error! Check sensor"
                    lcd.text(error_msg, 10, 10)

                # update display
                lcd.show()

        except OSError as e:
            utils.module_reset()


if __name__ == '__main__':
    main()
