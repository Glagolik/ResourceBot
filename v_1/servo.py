import uasyncio as asio
from machine import Pin, PWM

class Servo:
    def __init__(self, pin, freq=50, min_duty=40, max_duty=115, start_angle=90):
        self.pwm = PWM(Pin(pin), freq=freq)
        self.min_duty = min_duty
        self.max_duty = max_duty
        self.current_angle = start_angle
        self.is_moving = False  # Флаг защиты от спама командами
        self.set_angle(self.current_angle)

    def set_angle(self, angle):
        """Установка точного угла (используется внутри класса)"""
        self.current_angle = max(0, min(180, angle))
        duty = int(self.min_duty + (self.max_duty - self.min_duty) * (self.current_angle / 180))
        self.pwm.duty(duty)

    async def move_smooth(self, step_angle, delay_ms=15):
        """Плавно поворачивает на заданный угол без блокировки танка"""
        if self.is_moving:
            return  # Если серво еще в движении, игнорируем новые нажатия
            
        self.is_moving = True
        target_angle = max(0, min(180, self.current_angle + step_angle))
        
        # Определяем направление (в плюс или в минус)
        step = 1 if target_angle > self.current_angle else -1
        
        # Плавно шагаем по 1 градусу
        if target_angle != self.current_angle:
            for angle in range(self.current_angle, target_angle + step, step):
                self.set_angle(angle)
                await asio.sleep_ms(delay_ms) # Задержка для плавности
                
        self.is_moving = False