from machine import Pin, PWM

class TB6612:
    def __init__(self, pwm_pin, in1_pin, in2_pin, freq=1000):
        # Инициализация пинов для одного мотора
        self.pwm = PWM(Pin(pwm_pin, Pin.OUT), freq=freq, duty=0)
        self.in1 = Pin(in1_pin, Pin.OUT)
        self.in2 = Pin(in2_pin, Pin.OUT)
        
    def stop(self):
        # Остановка мотора
        self.in1.value(0)
        self.in2.value(0)
        self.pwm.duty(0)

    def forward(self, speed):
        # Движение вперед (ограничиваем скорость от 0 до 1023)
        speed = min(1023, max(0, speed))
        self.in1.value(1)
        self.in2.value(0)
        self.pwm.duty(speed)

    def reverse(self, speed):
        # Движение назад
        speed = min(1023, max(0, speed))
        self.in1.value(0)
        self.in2.value(1)
        self.pwm.duty(speed)