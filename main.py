import uasyncio as asyncio
from sync import SmartWaterSync

loop = asyncio.get_event_loop()


def run_water_pressure():
    try:
        sensor = SmartWaterSync(
            wifi_ssid="",
            wifi_pass="",
            mqtt_username="",
            mqtt_password="",
            mqtt_channels=("smarty/water_pressure", "smarty/water_relay",),     # 2 topics all time! for sensor and for relay
            output_channels=('mqtt', 'db'),     # possible: mqtt, display, db
            low_pressure=4,                     # bottom ON pressure
            high_pressure=5,                    # up OFF pressure
            max_sensor_pressure=12,             # the max sensor pressure according to specification
            sensor_raw_offset=43,               # define the default value from sensor
            sensor_min_raw_for_error=30         # define this to call ERROR state and disable RELAY \ STOP working
        )
        asyncio.run(sensor.run())
        loop.run_forever()
    except KeyboardInterrupt:
        print('Interrupted')
    finally:
        # Clear retained state
        asyncio.new_event_loop()
        print('done cycle')


run_water_pressure()
