# This file is executed on every boot (including wake-boot from deepsleep)
import esp
import uos, machine
import gc
esp.osdebug(None)
# uos.dupterm(None, 1) # disable REPL on UART(0)
# import webrepl
# webrepl.start()
gc.collect()
