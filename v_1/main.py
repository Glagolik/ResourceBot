import uasyncio as asio
from machine import Pin, PWM
import bluetooth
from BLEUART import BLEUART
from TB6612 import TB6612 
from rc522 import RC522

#  НАСТРОЙКИ МОТОРОВ TB6612 
motor_left = TB6612(pwm_pin=25, in1_pin=26, in2_pin=27)
motor_right = TB6612(pwm_pin=14, in1_pin=32, in2_pin=33)
speed = 1023

#  НАСТРОЙКИ СЕРВОПРИВОДОВ 
servo1 = PWM(Pin(16), freq=50)
servo2 = PWM(Pin(17), freq=50)

angle1 = 90 # Текущий угол 1 сервопривода
angle2 = 90 # Текущий угол 2 сервопривода
SERVO_STEP = 10 # Шаг поворота в градусах

def set_servo_angle(servo, angle):
    """Мгновенно поворачивает сервопривод на заданный угол"""
    angle = max(0, min(180, angle)) # Защита от выхода за пределы (0-180)
    duty = int(40 + (115 - 40) * (angle / 180)) 
    servo.duty(duty)
    return angle


angle1 = set_servo_angle(servo1, angle1)
angle2 = set_servo_angle(servo2, angle2)

comand = '' 

#  НАСТРОЙКИ СВЕТОДИОДА 
led = Pin(4, Pin.OUT)
led.value(0)

#  НАСТРОЙКА BLUETOOTH (Bluefruit LE Connect) 
def on_rx():
    global comand
    data = uart.read().decode()
    if data.startswith('!B') and len(data) >= 5:
        button = data[2]
        state = data[3]
        comand = button + state 

ble = bluetooth.BLE()
uart = BLEUART(ble, name="Kairos")
uart.irq(handler=on_rx)

# НАСТРОЙКА RFID RC522 
rfid = RC522(sck=18, mosi=23, miso=19, cs=21, rst=22)
DB_FILE = 'tags_db.txt'

def check_tag_in_db(uid_str):
    try:
        with open(DB_FILE, 'r') as f:
            allowed_tags = [line.strip().upper() for line in f.readlines()]
            return uid_str.upper() in allowed_tags
    except OSError:
        return False

#  АСИНХРОННЫЕ ЗАДАЧИ 
async def blink_led(mode):
    if mode == "success":
        for _ in range(3):
            led.value(1)
            await asio.sleep_ms(100)
            led.value(0)
            await asio.sleep_ms(100)
    elif mode == "error":
        led.value(1)
        await asio.sleep_ms(1000)
        led.value(0)

async def rfid_task():
    print("Считыватель карт готов.")
    while True:
        uid = rfid.read_uid()
        if uid:
            uid_str = ''.join(['{:02X}'.format(x) for x in uid])
            if check_tag_in_db(uid_str):
                print(f"[RFID] Метка ПОДХОДИТ: {uid_str}")
                asio.create_task(blink_led("success")) 
            else:
                print(f"[RFID] Метка НЕ ПОДХОДИТ: {uid_str}")
                asio.create_task(blink_led("error"))
        await asio.sleep_ms(1000)

async def control_task(int_ms):
    global comand, angle1, angle2
    last_cmd = '' # Защита от спама команд 
    
    while True:
        await asio.sleep_ms(int_ms)
        
        # СЕРВОПРИВОДЫ (Кнопки 1, 2, 3, 4) 
        if comand in ['11', '21', '31', '41']:
            if comand != last_cmd: 
                last_cmd = comand

                if comand == '11':
                    angle1 = set_servo_angle(servo1, angle1 + SERVO_STEP)
                elif comand == '21':
                    angle1 = set_servo_angle(servo1, angle1 - SERVO_STEP)
                elif comand == '31':
                    angle2 = set_servo_angle(servo2, angle2 + SERVO_STEP)
                elif comand == '41':
                    angle2 = set_servo_angle(servo2, angle2 - SERVO_STEP)
                    
        # Сброс защиты
        elif comand in ['10', '20', '30', '40']:
            last_cmd = ''
            comand = ''

        #  МОТОРЫ (стрелки: 5, 6, 7, 8)
        elif comand == '51':
            motor_left.forward(speed)
            motor_right.forward(speed)
        elif comand == '61':
            motor_left.reverse(speed)
            motor_right.reverse(speed)
        elif comand == '71':
            motor_left.reverse(speed)
            motor_right.forward(speed)
        elif comand == '81':
            motor_left.forward(speed)
            motor_right.reverse(speed)
            
        # Остановка моторов при отпускании стрелки
        elif comand in ['50', '60', '70', '80']:
            motor_left.stop()
            motor_right.stop()
            comand = ''

#  ЗАПУСК ПРОГРАММЫ 
async def main():
    print("Started")
    asio.create_task(rfid_task())
    asio.create_task(control_task(20)) 
    
    while True:
        await asio.sleep(1)

try:
    asio.run(main())
except KeyboardInterrupt:
    motor_left.stop()
    motor_right.stop()
    led.value(0)
