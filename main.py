# Available pins are: 0, 1, 2, 3, 4, 5, 12, 13, 14, 15, 16, which correspond to the actual GPIO pin numbers of
# ESP8266 chip

import utils
# from settings import settings
import utime

lcd = utils.i2c_setup()


def main():
    try:
        # ifconfig = utils.wifi_setup()
        # print(ifconfig)
        # mqtt_client = utils.mqtt_setup()
        ms = utime.ticks_ms()
    except OSError as e:
        utils.module_reset()
    while True:
        try:

            current_ms = utime.ticks_ms()
            if current_ms - ms >= 10000:
                ms = current_ms
                lcd.fill(0)
                lcd.show()
            x = utils.randint(1, settings.LCD_WIDTH)
            y = utils.randint(1, settings.LCD_HEIGHT)
            lcd.pixel(x, y, 1)
            lcd.show()
        except OSError as e:
            utils.module_reset()


if __name__ == '__main__':
    main()
