import uasyncio as asio
from machine import Pin, PWM, SPI
import bluetooth
from BLEUART import BLEUART
from TB6612 import TB6612 
import mfrc522
import neopixel
import time
import _thread  # Библиотека для работы со вторым ядром!

# === НАСТРОЙКИ МОТОРОВ TB6612 ===
motor_left = TB6612(pwm_pin=25, in1_pin=26, in2_pin=27)
motor_right = TB6612(pwm_pin=14, in1_pin=32, in2_pin=33)

current_speed = 0  
MAX_SPEED = 1023   
SPEED_STEP = 500    # Мгновенный разгон (до максимума за 40 мс)

# === НАСТРОЙКИ СЕРВОПРИВОДОВ ===
servo1 = PWM(Pin(16), freq=50)
servo2 = PWM(Pin(17), freq=50)

angle1 = 90 
angle2 = 90 
SERVO_STEP = 1

def set_servo_angle(servo, angle):
    angle = max(0, min(180, angle)) 
    duty = int(40 + (115 - 40) * (angle / 180)) 
    servo.duty(duty)
    return angle

angle1 = set_servo_angle(servo1, angle1)
angle2 = set_servo_angle(servo2, angle2)
comand = '' 

# === НАСТРОЙКИ СВЕТОДИОДА ===
np = neopixel.NeoPixel(Pin(4), 1)
np[0] = (0, 0, 0)
np.write()

# === НАСТРОЙКА BLUETOOTH (Возвращаем твой быстрый вариант!) ===
def on_rx():
    global comand
    try:
        data = uart.read().decode('utf-8', 'ignore')
        if data.startswith('!B') and len(data) >= 5:
            button = data[2]
            state = data[3]
            comand = button + state 
    except Exception:
        pass

ble = bluetooth.BLE()
time.sleep(1) # Стабилизация
ble.active(True)
uart = BLEUART(ble, name="Kairos")
uart.irq(handler=on_rx)

# === НАСТРОЙКА RFID ===
vspi = SPI(2)
rdr = mfrc522.MFRC522(spi=vspi, gpioRst=22, gpioCs=21)

# Глобальная переменная для связи между ядрами процессора
detected_color = None

def get_exact_text(chunks):
    full_data = bytearray()
    for c in chunks:
        if c: full_data.extend(c)
    if not full_data: return ""
    try:
        marker_idx = -1
        if b'\x02en' in full_data: marker_idx = full_data.rfind(b'\x02en') + 3
        elif b'\x02ru' in full_data: marker_idx = full_data.rfind(b'\x02ru') + 3
        if marker_idx != -1:
            result = ""
            for b in full_data[marker_idx:]:
                if 32 <= b <= 126: result += chr(b)
                else: break 
            return result.strip()
        return "Пустая метка"
    except: return ""

def text_to_color(text):
    text = text.strip().upper() 
    colors = {
        "WHITE": (255, 255, 255), "BLACK": (0, 0, 0), "RED": (255, 0, 0),
        "YELLOW": (255, 255, 0), "BLUE": (0, 0, 255), "GREEN": (0, 255, 0),
        "ORANGE": (255, 100, 0), "PINK": (255, 20, 147), "PURPLE": (128, 0, 128),
        "BROWN": (139, 69, 19), "GREY": (50, 50, 50)
    }
    return colors.get(text, None)

# ==========================================================
# === ЯДРО 0: ТЯЖЕЛЫЙ СКАНЕР RFID (РАБОТАЕТ В ФОНЕ) ===
# ==========================================================
def rfid_thread():
    global detected_color
    print("[Ядро 0] RFID сканер запущен в независимом потоке!")
    while True:
        if comand != '': 
            time.sleep(0.1) # Если танк едет, сканер не мешает
            continue
        
        (stat, _) = rdr.request(rdr.REQIDL)
        if stat == rdr.OK:
            (stat, raw_uid) = rdr.anticoll()
            if stat == rdr.OK:
                if rdr.select_tag(raw_uid) == rdr.OK:
                    block4 = rdr.read(4); block5 = rdr.read(5)
                    if block4 and block5:
                        text_on_tag = get_exact_text([block4, block5])
                        if text_on_tag and text_on_tag != "Пустая метка":
                            color = text_to_color(text_on_tag)
                            detected_color = color if color else "ERROR"
                        else:
                            detected_color = "ERROR"
                    rdr.stop_crypto1()
                    time.sleep(1.5) 
        time.sleep(0.1)

# Выталкиваем эту функцию на второе ядро
_thread.start_new_thread(rfid_thread, ())


# ==========================================================
# === ЯДРО 1: МГНОВЕННОЕ УПРАВЛЕНИЕ И СВЕТОДИОД ===
# ==========================================================
async def show_cargo_color(color_rgb):
    np[0] = color_rgb; np.write()
    await asio.sleep_ms(2000)
    np[0] = (0, 0, 0); np.write()

async def blink_error():
    for _ in range(3):
        np[0] = (255, 0, 0); np.write()
        await asio.sleep_ms(150)
        np[0] = (0, 0, 0); np.write()
        await asio.sleep_ms(150)

async def led_controller():
    """Ловит сигналы от второго ядра и включает нужный свет"""
    global detected_color
    while True:
        if detected_color:
            if detected_color == "ERROR":
                asio.create_task(blink_error())
            else:
                asio.create_task(show_cargo_color(detected_color))
            detected_color = None
        await asio.sleep_ms(100)

async def control_task(int_ms):
    global comand, angle1, angle2, current_speed
    last_move_cmd = '' 
    
    while True:
        await asio.sleep_ms(int_ms)
        
        # --- СЕРВОПРИВОДЫ ---
        if comand in ['11', '21', '31', '41']:
            if comand == '11': angle1 = set_servo_angle(servo1, angle1 + SERVO_STEP)
            elif comand == '21': angle1 = set_servo_angle(servo1, angle1 - SERVO_STEP)
            elif comand == '31': angle2 = set_servo_angle(servo2, angle2 + SERVO_STEP)
            elif comand == '41': angle2 = set_servo_angle(servo2, angle2 - SERVO_STEP)
        elif comand in ['10', '20', '30', '40']:
            comand = '' 

        # --- МОТОРЫ ---
        elif comand in ['51', '61', '71', '81']:
            if comand != last_move_cmd:
                # Пауза ТОЛЬКО при смене направления (например, с "Вперед" на "Назад")
                if last_move_cmd != '': 
                    motor_left.stop()
                    motor_right.stop()
                    await asio.sleep_ms(100) 
                current_speed = 0
                last_move_cmd = comand
                
            if current_speed < MAX_SPEED:
                current_speed += SPEED_STEP
                if current_speed > MAX_SPEED: current_speed = MAX_SPEED
            
            if comand == '51':
                motor_left.forward(current_speed)
                motor_right.forward(current_speed)
            elif comand == '61':
                motor_left.reverse(current_speed)
                motor_right.reverse(current_speed)
            elif comand == '71':
                motor_left.reverse(current_speed)
                motor_right.forward(current_speed)
            elif comand == '81':
                motor_left.forward(current_speed)
                motor_right.reverse(current_speed)
                
        elif comand in ['50', '60', '70', '80']:
            motor_left.stop()
            motor_right.stop()
            current_speed = 0 
            last_move_cmd = '' 
            comand = ''

# === ЗАПУСК ===
async def main():
    print("[Ядро 1] Моторы и Bluetooth готовы!")
    asio.create_task(led_controller())
    asio.create_task(control_task(20)) 
    while True: await asio.sleep(1)

try:
    asio.run(main())
except KeyboardInterrupt:
    motor_left.stop()
    motor_right.stop()
    np[0] = (0, 0, 0); np.write()
    print("Остановлено.")

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
