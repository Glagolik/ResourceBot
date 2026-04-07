from machine import TouchPad, Pin,PWM
from MX1508 import *
from micropython import const
import uasyncio as asio
from BLEUART import *

debug=0
motor = MX1508(25, 26)
sp=1023
an=0
on=0
comand=''
pwm = PWM(Pin(33,Pin.OUT))
pwm.freq(50)
pwm.duty(0)


        
def map(x, in_min, in_max, out_min, out_max):
    return int((x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)
def servo(pin, angle):
    pin.duty(map(angle, 0, 180, 20, 120))
def on_rx():
    global comand,on
    on=1
    comand=uart.read().decode()
    #print(comand)
    comand=comand[2:]

ble = bluetooth.BLE()
uart = BLEUART(ble)
uart.irq(handler=on_rx)    
                
    
async def do_it(int_ms):
    global an,on
    while 1:
        await asio.sleep_ms(int_ms)
        #print(comand)
        if comand=='516':
            motor.forward(sp)
        if comand=='615':
            motor.reverse(sp)
        if (comand=='507')or(comand=='606'):
            motor.stop()
        if comand=='813' and on:
            an+=30
            on=0
            if an>180:
                an=180
        if comand=='714' and on:
            an-=30
            on=0
            if an<0:
                an=0
        servo(pwm, an)

# define loop
loop = asio.get_event_loop()

#create looped tasks
loop.create_task(do_it(5))
# loop run forever
loop.run_forever()

#uart.close()