import math

import machine
import network
from umqtt_simple import MQTTClient
import uasyncio as asyncio
import urequests
import gc
import utime

DEBUG = False


def _print(txt):
    if DEBUG:
        print(txt)


def median(lst):
    # return median from the list of values
    quotient, remainder = divmod(len(lst), 2)
    if remainder:
        return sorted(lst)[quotient]
    return sum(sorted(lst)[quotient - 1:quotient + 1]) / 2


class SmartWaterSync:
    """Sync class"""
    wlan = network.WLAN(network.AP_IF)
    wlan.active(False)

    def __init__(self,
                 wifi_ssid="",
                 wifi_pass="",
                 mqtt_server="192.168.10.10",
                 mqtt_port=1183,
                 mqtt_username="",
                 mqtt_password="",
                 mqtt_channels=("smarty/water_pressure", "smarty/water_relay",),
                 board_led=2,
                 board_id="water_pressure",
                 adc_pin=0,                     # adc default pin is 0 on esp8266
                 pump_relay=14,                 # esp8266 board pin to work with RELAY
                 output_channels=None,          # default value is None == mqtt
                 I2C_SCL=5,                     # lcd params
                 I2C_SDA=4,
                 LCD_WIDTH=128,
                 LCD_HEIGHT=32,
                 low_pressure=4,                # low pressure
                 high_pressure=5,               # top high pressure
                 max_sensor_pressure=12,        # the max sensor pressure that it's supported
                 sensor_voltage_offset=0.45,    # default sensor output voltage
                 sensor_raw_offset=43,          # default raw value
                 sensor_min_raw_for_error=30,   # min raw value when we should call ERROR and reset the system
                 ):

        if output_channels is None:
            output_channels = ('mqtt',)

        self.wifi_ssid = wifi_ssid
        self.wifi_pass = wifi_pass
        self.mqtt_server = mqtt_server
        self.mqtt_port = mqtt_port
        self.mqtt_username = mqtt_username
        self.mqtt_password = mqtt_password
        self.mqtt_channels = mqtt_channels
        self.board_id = board_id
        self.mqtt_client = None
        self.wlan = network.WLAN(network.STA_IF)
        self.board_led = machine.Pin(board_led, machine.Pin.OUT)
        self.board_led.value(1)

        # output params
        self.output_channels = output_channels

        # display
        self.I2C_SCL = I2C_SCL
        self.I2C_SDA = I2C_SDA
        self.LCD_WIDTH = LCD_WIDTH
        self.LCD_HEIGHT = LCD_HEIGHT

        # pump relay pin
        self._pump_relay = pump_relay

        # sensor params
        self._adc_pin = adc_pin
        self._low_pressure = low_pressure
        self._high_pressure = high_pressure
        self._min_raw_value = sensor_min_raw_for_error
        self._max_sensor_pressure = max_sensor_pressure
        self._sensor_voltage_offset = sensor_voltage_offset
        self._sensor_raw_offset = sensor_raw_offset

        self.adc = machine.ADC(self._adc_pin)

        # init first values from sensor
        self._current_pressure = self.convert_pressure(self.adc.read())
        self._last_pressure = self.convert_pressure(self.adc.read())

        self._sensor_error = False
        self._pump_working = False
        # setup
        self.pump_relay = machine.Pin(self._pump_relay, machine.Pin.OUT)


        if "display" in output_channels:
            self.lcd = self.i2c_setup()

    @property
    def pump_working(self):
        return self._pump_working

    @pump_working.setter
    def pump_working(self, value: bool):
        self._pump_working = value

    @property
    def sensor_error(self):
        return self._sensor_error

    @sensor_error.setter
    def sensor_error(self, value):
        self._sensor_error = value

    @property
    def min_raw_value(self):
        return self._min_raw_value

    @property
    def max_sensor_pressure(self):
        return self._max_sensor_pressure

    @property
    def sensor_voltage_offset(self):
        return self._sensor_voltage_offset

    @property
    def sensor_raw_offset(self):
        return self._sensor_raw_offset

    @property
    def min_raw_value(self):
        return self._min_raw_value

    @property
    def low_pressure(self):
        return self._low_pressure

    @property
    def high_pressure(self):
        return self._high_pressure

    @property
    def pressure(self):
        return self._current_pressure

    @property
    def last_pressure(self):
        return self._last_pressure

    @last_pressure.setter
    def last_pressure(self, value):
        self._last_pressure = value

    @pressure.setter
    def pressure(self, value):
        self._current_pressure = value

    async def pressure_check(self):
        """Convert raw sensor pressure data into readable Bars and make a decision what to do :)"""
        while True:
            try:
                await asyncio.sleep_ms(500)
                raw_value = self.get_analog_data()
                self.check_sensor_health(raw_value)
                pressure = self.convert_pressure(raw_value)
                self.check_pressure_value(pressure)
                self.pressure = pressure
            except OSError as e:
                _print(e)

    def switch_pump_off(self):
        """switch pump OFF"""
        # relay 0 == OFF | 1 == ON
        self.pump_relay.value(0)

    def switch_pump_on(self):
        """switch pump ON"""
        # relay 0 == OFF | 1 == ON
        self.pump_relay.value(1)

    def check_pressure_value(self, pressure: float):
        """That method terminates water pump if something goes wrong with other verification method"""
        try:
            if pressure >= self.high_pressure and self.pump_working:
                # if something goes wrong and we have a high pressure - let's stop the whole system
                self.switch_pump_off()
                self.pump_working = False
                self.mqtt_publish(self.mqtt_channels[1], "0")
            else:
                if pressure <= self.low_pressure and not self.pump_working:
                    self.pump_working = True
                    self.switch_pump_on()
                    self.mqtt_publish(self.mqtt_channels[1], "1")
        except OSError as e:
            _print("on-off error {}".format(e))
            # just to be sure
            self.switch_pump_off()
            self.pump_working = False

    def check_sensor_health(self, raw_value):
        """Extra verification of water pump to safety switch off in any other non working parameters"""
        if raw_value <= self.min_raw_value:
            # switch off relay just to be sure that we're safe
            self.sensor_error = True
            self.switch_pump_off()
            self.mqtt_publish(self.mqtt_channels)

    def convert_pressure(self, raw_value):
        """Pressure calculation rules"""
        # https://forum.arduino.cc/index.php?topic=568567.0
        full_scale = 1023 - self.sensor_raw_offset
        max_pressure = 12
        sensor_voltage = round((raw_value - self.sensor_raw_offset) / full_scale, 1)
        pressure = round((raw_value - self.sensor_raw_offset) * max_pressure / full_scale, 1)
        _print("debug: sensor_voltage: {}, pressure: {}".format(sensor_voltage, pressure))
        return round(pressure, 1)

    def get_analog_data(self):
        """Return median for the list of values"""
        raw_values = []
        try:
            for i in range(5):
                raw_values.append(self.adc.read())
                utime.sleep_ms(50)
            raw_values.sort()
        except OSError as e:
            raw_values = [0, 0, 0, 0, 0]
            _print("Get analog data error: {}".format(e))
        # take a new values from average values during the last 5 readings
        finally:
            _print("debug: raw values: {}".format(raw_values))
            # return median values
            return median(raw_values)
            # return sum(raw_values) / len(raw_values)

    def i2c_setup(self):
        """setup i2c interface"""
        if 'display' in self.output_channels:
            from esp8266_i2c_lcd import I2cLcd
            from machine import I2C, Pin
            lcd = I2cLcd(I2C(scl=Pin(5), sda=Pin(4)), 0x27, 4, 20)
            lcd.backlight_on()
            lcd.clear()
            lcd.move_to(0, 1)
            lcd.putstr("Init")
            return lcd

    async def board_ticker(self, time_ms):
        while True:
            await asyncio.sleep_ms(time_ms)
            if self.board_led.value() == 0:
                self.board_led.value(1)
            else:
                self.board_led.value(0)

    def _mqtt_setup_callback(self, topic, msg):
        """setup callback for income messages"""
        try:
            _print("MQTT: topic, msg:{}-{}".format(topic, msg))
            topic = topic.decode()
            if len(self.mqtt_channels) > 1:
                # just double check that we have 2 topics during setup procedure
                if str(topic) == str(self.mqtt_channels[1]):
                    data = msg.decode()
                    # change relay status from MQTT channel mqtt_channels[1]
                    # be careful to play with relay!)
                    if int(data) == 1:
                        self.pump_relay.value(1)
                        self.pump_working = True
                    else:
                        self.pump_relay.value(0)
                        self.pump_working = False
        except OSError as e:
            _print("Error during mqtt data reading from channel: {}".format(e))

    async def send_data(self, time_ms):
        """send water pressure to available channels: mqtt, db, display"""
        while True:
            try:
                await asyncio.sleep_ms(time_ms)
                # send update only if the diff > 0.1
                _print("pressure: {} | last: {}, diff: {}".format(self.pressure, self.last_pressure,
                                                                  math.fabs(self.pressure - self.last_pressure)))
                if round(math.fabs(self.pressure-self.last_pressure), 1) > 0.1:
                    self.last_pressure = self.pressure
                    _print(">>>>> push data to DB")
                    if "mqtt" in self.output_channels:
                        self.mqtt_publish(self.mqtt_channels[0], "{}".format(self.pressure))
                    if "db" in self.output_channels:
                        self.send_http_data(_url='http://192.168.10.10/water/pressure/{}'.format(self.pressure))
                    if "display" in self.output_channels:
                        # use your own code here :) for data displaying
                        pass

            except OSError as e:
                # nothing here - continue even we have some errors
                _print("Error during sending data: {}".format(e))


    async def check_mqtt(self):
        """setup MQTT bridge"""
        try:
            i = 0
            while True:
                await asyncio.sleep(10)
                if self.wlan.isconnected():
                    _print("CHECK [mqtt]...{}-{}".format(i, self.mqtt_client))
                    if not self.mqtt_client:
                        _print("Connecting... to mqtt")
                        self.mqtt_client = MQTTClient(
                            client_id=self.board_id,
                            server=self.mqtt_server,
                            port=self.mqtt_port,
                            user=self.mqtt_username,
                            password=self.mqtt_password
                        )
                        self.mqtt_client.set_callback(self._mqtt_setup_callback)
                        self.mqtt_client.connect()
                        if len(self.mqtt_channels) > 1:
                            # double check
                            self.mqtt_client.subscribe(self.mqtt_channels[1])
                        # self.mqtt_client.publish(self.mqtt_channels[0], "{} connected".format("pressure"), False, 0)
                        _print("Connected to mqtt!")
                i += 1
        except OSError as e:
            _print("MQTT connection error: {}".format(e))
            self.wlan.disconnect()
            gc.collect()

    async def wifi_check(self):
        i = 0
        while True:
            await asyncio.sleep(10)
            # _print("CHECK wifi connection...{}".format(i))
            try:
                if not self.wlan.isconnected():
                    _print("setup wifi connection")
                    self.wlan.active(True)
                    self.wlan.connect("nc-main", "sensorium")
                    while not self.wlan.isconnected():
                        # wait until we'll not connect to wifi
                        await asyncio.sleep(5)
                    _print("Connected to wifi. IP: {}".format(self.wlan.ifconfig()))
            except OSError as e:
                _print("Wifi connection error: {}".format(e))
                gc.collect()
            i += 1

    async def check_mqtt_msg(self):
        while True:
            try:
                await asyncio.sleep_ms(1000)
                if self.mqtt_client:
                    self.mqtt_client.check_msg()
                    _print("check mqtt messages")
            except OSError as e:
                _print("Something goes wrong with mqtt: {}".format(e))
                self.mqtt_client = None

    async def run(self):
        asyncio.create_task(self.board_ticker(500))
        # wifi is default channel that should be exists for default communication channels
        asyncio.create_task(self.wifi_check())
        if "mqtt" in self.output_channels:
            asyncio.create_task(self.check_mqtt())
            asyncio.create_task(self.check_mqtt_msg())
        asyncio.create_task(self.pressure_check())
        asyncio.create_task(self.send_data(1000))

    def mqtt_publish(self, channel, msg):
        if self.mqtt_client:
            self.mqtt_client.publish(channel, msg, False, 1)

    def send_http_data(self, _url):
        if self.wlan.isconnected():
            response = urequests.get(url=_url)
            response.close()


