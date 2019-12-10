# Available pins are: 0, 1, 2, 3, 4, 5, 12, 13, 14, 15, 16, which correspond to the actual GPIO pin numbers of
# ESP8266 chip

import time
import utils


def main():
    try:
        ifconfig = utils.wifi_setup()
        print(ifconfig)
        lcd = utils.i2c_setup()


        mqtt_client = utils.mqtt_setup()
    except OSError as e:
        utils.module_reset()
    while True:
        time.sleep(1)
        try:
            pass
        except OSError as e:
            utils.module_reset()


if __name__ == '__main__':
    main()
