import uasyncio as asio
from machine import Pin
import bluetooth
from BLEUART import BLEUART
from TB6612 import TB6612
from rc522 import RC522
from servo import Servo

# === НАСТРОЙКИ МОТОРОВ И СЕРВОПРИВОДОВ ===
motor_left = TB6612(pwm_pin=25, in1_pin=26, in2_pin=27)
motor_right = TB6612(pwm_pin=14, in1_pin=32, in2_pin=33)
speed = 1023

servo1 = Servo(pin=16, start_angle=90) 
servo2 = Servo(pin=17, start_angle=90)
SERVO_STEP = 30 # Угол поворота серво за одно нажатие

comand = '' # Теперь здесь будет храниться строка вида "КнопкаСтатус", например "51"

led = Pin(4, Pin.OUT)
led.value(0)

# === НАСТРОЙКА BLUETOOTH (Bluefruit LE Connect Protocol) ===
def on_rx():
    global comand
    data = uart.read().decode()
    
    # Протокол Bluefruit: !B[Кнопка(1-8)][Статус(0-1)][КонтрольнаяСумма]
    if data.startswith('!B') and len(data) >= 5:
        button = data[2] # Номер кнопки (1-8)
        state = data[3]  # Статус (1 - нажата, 0 - отпущена)
        comand = button + state # Склеиваем, получается: '51', '10', '71' и т.д.

ble = bluetooth.BLE()
uart = BLEUART(ble, name="TankBot")
uart.irq(handler=on_rx)

# === НАСТРОЙКА RFID RC522 ===
rfid = RC522(sck=18, mosi=23, miso=19, cs=21, rst=22)
DB_FILE = 'tags_db.txt'

def check_tag_in_db(uid_str):
    try:
        with open(DB_FILE, 'r') as f:
            allowed_tags = [line.strip().upper() for line in f.readlines()]
            return uid_str.upper() in allowed_tags
    except OSError:
        return False

# === АСИНХРОННЫЕ ЗАДАЧИ ===
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
    print("Считыватель готов...")
    while True:
        uid = rfid.read_uid()
        if uid:
            uid_str = ''.join(['{:02X}'.format(x) for x in uid])
            if check_tag_in_db(uid_str):
                print(f"[RFID] ✓ Метка ПОДХОДИТ: {uid_str}")
                asio.create_task(blink_led("success")) 
            else:
                print(f"[RFID] ✗ Метка НЕ ПОДХОДИТ: {uid_str}")
                asio.create_task(blink_led("error"))
        await asio.sleep_ms(1000)

async def control_task(int_ms):
    global comand
    last_cmd = '' # Защита от спама при удерживании кнопки
    
    while True:
        await asio.sleep_ms(int_ms)
        
        # --- СЕРВОПРИВОДЫ (Кнопки 1, 2, 3, 4 в приложении Bluefruit) ---
        # '11' = Кнопка 1 нажата, '21' = Кнопка 2 нажата и т.д.
        if comand in ['11', '21', '31', '41']:
            if comand != last_cmd: # Срабатывает только 1 раз при нажатии
                last_cmd = comand
                
                if comand == '11':
                    asio.create_task(servo1.move_smooth(SERVO_STEP))
                elif comand == '21':
                    asio.create_task(servo1.move_smooth(-SERVO_STEP))
                elif comand == '31':
                    asio.create_task(servo2.move_smooth(SERVO_STEP))
                elif comand == '41':
                    asio.create_task(servo2.move_smooth(-SERVO_STEP))
                    
        # Когда отпускаем кнопки 1-4 (статус '0'), сбрасываем блокировку
        elif comand in ['10', '20', '30', '40']:
            last_cmd = ''
            comand = ''

        # --- МОТОРЫ (Стрелки D-Pad в приложении Bluefruit) ---
        # '51' = Вверх, '61' = Вниз, '71' = Влево, '81' = Вправо
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
            
        # Когда отпускаем любую стрелку (статус '0')
        elif comand in ['50', '60', '70', '80']:
            motor_left.stop()
            motor_right.stop()
            comand = ''

# === ЗАПУСК ===
async def main():
    print("Танк запущен! Соединитесь в Bluefruit LE Connect и откройте Control Pad.")
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