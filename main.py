"""
Mechanical relay is replaced with esp8266 + SSD relay + micro-python logic
Using mqtt broker we send the data via data protocol and can see what we have
# Available pins are: 0, 1, 2, 3, 4, 5, 12, 13, 14, 15, 16, which correspond to
the actual GPIO pin numbers of ESP8266 controller
@author: Alex Bogdanovich bogdanovich.alex@gmail.com
"""
import utils
from settings import settings
import utime
from pressure_sensor import PressureSensor


def main():
    """Main method with loop"""
    sensor = PressureSensor()
    # just to be sure...
    sensor.turn_OFF_pump()

    # read working time from file and update display
    sensor.read_working_time()
    # load values from settings file
    sensor.read_settings_from_file()

    timer_pressure = utime.ticks_ms()
    timer_wifi = utime.ticks_ms()
    timer_mqtt_check = utime.ticks_ms()

    while True:
        try:
            if utime.ticks_ms() - timer_wifi > 1000:
                timer_wifi = utime.ticks_ms()
                # check wifi connection each 1 second
                if sensor.mqtt_connected():
                    sensor.publish_info("wifi: connected")

            if utime.ticks_ms() - timer_mqtt_check > 5000:
                timer_mqtt_check = utime.ticks_ms()
                # setup mqtt and check connection
                if sensor.mqtt_connected():
                    sensor.publish_info("mqtt: connected")
                else:
                    sensor.publish_info("mqtt: init conn")

            if utime.ticks_ms() - timer_pressure > 200:
                timer_pressure = utime.ticks_ms()
                sensor.clear_lcd()
                sensor.check_mqtt_updates()
                # read sensor analog data
                sensor.get_analog_data()
                display_message = ""

                if not sensor.system_error_status:
                    if not sensor.check_sensor_health() or not sensor.check_high_pressure_value(
                            sensor.current_pressure
                    ):
                        # something is wrong - need to inform and turn off pump
                        display_message = "Error! High or Low pressure!"
                        # mark system error
                        system_error_status = True

                    else:
                        # calculate pressure value
                        sensor.calculate_pressure()
                        # check what to do with pump
                        # current_pressure = float(utils.randint(3, 5))
                        sensor.check_what_todo_with_pressure()
                        # draw lcd value
                        sensor.publish_data()
                else:
                    display_message = "System Error! Check sensor"

                if display_message:
                    sensor.lcd.text(display_message, 0, round(settings.LCD_HEIGHT / 2))
                    if sensor.mqtt_connected():
                        sensor.publish_info(display_message)
                else:
                    sensor.update_display()

                sensor.lcd.show()

        except OSError as e:
            utils.module_reset()


if __name__ == '__main__':
    main()
