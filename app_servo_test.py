# app_servo_test.py - Тестовый пульт управления шасси робота (колеса GP1/2 + ковш GP0)
import time
import math
import struct
import st7789
from machine import Pin, PWM

C_BG      = st7789.ST7789.color565(10, 14, 26)
C_HEADER  = st7789.ST7789.color565(0, 180, 70)     # Зеленый для шасси
C_PANEL   = st7789.ST7789.color565(20, 30, 50)
C_GLOW    = st7789.ST7789.color565(0, 240, 255)
C_WHITE   = 0xFFFF
C_GRAY    = st7789.ST7789.color565(130, 145, 175)
C_ORANGE  = st7789.ST7789.color565(255, 160, 0)
C_RED     = st7789.ST7789.color565(255, 60, 60)

class ServoTestApp:
    def __init__(self, tft, audio, inputs, config=None):
        self.tft = tft
        self.audio = audio
        self.inputs = inputs
        self.cfg = config if config else {"vol_ui": 30, "mute": False}

        # Настройка сервоприводов
        # GP0: Ковш (0-180°), GP1: Правое колесо (360°), GP2: Левое колесо (360°)
        self.pwm_bucket = self.init_pwm(0)
        self.pwm_r_wheel = self.init_pwm(1)
        self.pwm_l_wheel = self.init_pwm(2)

        self.bucket_angle = 90
        self.chassis_status = "STOPPED"
        self.stop_all()

    def init_pwm(self, pin_num):
        try:
            p = PWM(Pin(pin_num))
            p.freq(50)
            return p
        except Exception as e:
            print(f"Ошибка GP{pin_num}:", e)
            return None

    def set_servo_angle(self, pwm, angle):
        if not pwm: return
        angle = max(0, min(180, angle))
        pulse_us = 500 + (angle / 180.0) * 2000
        duty = int(65535 * (pulse_us / 20000))
        pwm.duty_u16(duty)

    def stop_wheels(self):
        # 90 градусов для серв постоянного вращения - это СТОП
        self.set_servo_angle(self.pwm_r_wheel, 90)
        self.set_servo_angle(self.pwm_l_wheel, 90)
        self.chassis_status = "STOPPED"

    def drive_forward(self):
        # Правое и левое крутятся навстречу друг другу
        self.set_servo_angle(self.pwm_r_wheel, 0)
        self.set_servo_angle(self.pwm_l_wheel, 180)
        self.chassis_status = "FORWARD ▲"

    def drive_backward(self):
        self.set_servo_angle(self.pwm_r_wheel, 180)
        self.set_servo_angle(self.pwm_l_wheel, 0)
        self.chassis_status = "BACKWARD ▼"

    def turn_left(self):
        self.set_servo_angle(self.pwm_r_wheel, 0)
        self.set_servo_angle(self.pwm_l_wheel, 0)
        self.chassis_status = "ROTATE LEFT ◄"

    def turn_right(self):
        self.set_servo_angle(self.pwm_r_wheel, 180)
        self.set_servo_angle(self.pwm_l_wheel, 180)
        self.chassis_status = "ROTATE RIGHT ►"

    def stop_all(self):
        self.stop_wheels()
        self.set_servo_angle(self.pwm_bucket, self.bucket_angle)

    def beep(self, freq=1200, ms=15):
        if self.cfg.get("mute") or self.cfg.get("vol_ui", 30) == 0:
            return
        rate = 22050
        samples = int(rate / freq)
        cycle = bytearray(samples * 2)
        amp = int(800 * (self.cfg.get("vol_ui", 30) / 100))
        for i in range(samples):
            v = int(amp * math.sin(2 * math.pi * i / samples))
            struct.pack_into("<h", cycle, i * 2, v)
        for _ in range(int((ms / 1000) * freq)):
            self.audio.write(cycle)

    def auto_demo_routine(self):
        """Автотест: подъем ковша и маневр колес"""
        self.tft.fill_rect(20, 205, 200, 30, C_HEADER)
        self.tft.text("DEMO ROUTINE...", 45, 215, C_WHITE)
        self.tft.show()

        # 1. Поднимаем ковш
        for a in range(20, 110, 10):
            self.bucket_angle = a
            self.set_servo_angle(self.pwm_bucket, a)
            time.sleep_ms(40)

        # 2. Едем вперед 1 сек
        self.drive_forward()
        time.sleep(1.0)

        # 3. Разворот
        self.turn_right()
        time.sleep(0.8)

        # 4. Опускаем ковш и стоп
        self.stop_wheels()
        self.bucket_angle = 45
        self.set_servo_angle(self.pwm_bucket, 45)
        self.beep(1500, 30)

    def draw_screen(self):
        self.tft.fill(C_BG)

        # Шапка
        self.tft.fill_rect(0, 0, 240, 34, C_HEADER)
        self.tft.text("ROBOT SERVO TEST", 14, 12, C_WHITE)

        # Панель 1: Колеса (Шасси)
        self.tft.fill_rect(10, 48, 220, 80, C_PANEL)
        self.tft.rect(10, 48, 220, 80, C_GLOW)
        self.tft.text("CHASSIS (GP1 & GP2):", 20, 56, C_WHITE)
        self.tft.text(f"STATE: {self.chassis_status}", 20, 75, C_GLOW)
        self.tft.text("ARROWS: Drive / Turn", 20, 96, C_GRAY)
        self.tft.text("SPACE : Emergency STOP", 20, 110, C_ORANGE)

        # Панель 2: Ковш
        self.tft.fill_rect(10, 140, 220, 75, C_PANEL)
        self.tft.rect(10, 140, 220, 75, C_ORANGE)
        self.tft.text("BUCKET (GP0):", 20, 148, C_WHITE)
        self.tft.text(f"ANGLE: {self.bucket_angle:03d} deg", 20, 168, C_ORANGE)
        
        # Шкала угла ковша
        self.tft.rect(20, 186, 200, 8, C_GRAY)
        fill_w = int(196 * (self.bucket_angle / 180.0))
        if fill_w > 0:
            self.tft.fill_rect(22, 188, fill_w, 4, C_ORANGE)

        # Подсказки снизу
        self.tft.line(0, 275, 240, 275, C_GRAY)
        self.tft.text("1/2/3/4: Bucket angle", 12, 285, C_WHITE)
        self.tft.text("ENTER: Demo   ESC: Exit", 12, 302, C_GLOW)

        self.tft.show()

    def run(self):
        while True:
            self.draw_screen()

            ev = self.inputs.get_event()
            if ev:
                if ev in ['BACK', 'ESC']:
                    self.stop_all()
                    self.beep(600, 25)
                    return

                # === УПРАВЛЕНИЕ КОЛЕСАМИ (ШАССИ) ===
                elif ev == 'UP':
                    self.drive_forward()
                    self.beep(1200, 10)
                elif ev == 'DOWN':
                    self.drive_backward()
                    self.beep(900, 10)
                elif ev == 'LEFT':
                    self.turn_left()
                    self.beep(1000, 10)
                elif ev == 'RIGHT':
                    self.turn_right()
                    self.beep(1000, 10)
                elif ev in [' ', 's']: # ПРОБЕЛ ИЛИ S - СТОП
                    self.stop_wheels()
                    self.beep(700, 15)

                # === УПРАВЛЕНИЕ КОВШОМ (КЛАВИШИ 1, 2, 3, 4) ===
                elif ev == '1': # Опустить
                    self.bucket_angle = 10
                    self.set_servo_angle(self.pwm_bucket, 10)
                    self.beep(800, 15)
                elif ev == '2': # Средний
                    self.bucket_angle = 45
                    self.set_servo_angle(self.pwm_bucket, 45)
                    self.beep(1000, 15)
                elif ev == '3': # Поднять
                    self.bucket_angle = 90
                    self.set_servo_angle(self.pwm_bucket, 90)
                    self.beep(1200, 15)
                elif ev == '4': # Максимум
                    self.bucket_angle = 135
                    self.set_servo_angle(self.pwm_bucket, 135)
                    self.beep(1400, 15)

                # ДЕМО РЕЖИМ
                elif ev == 'ENTER':
                    self.auto_demo_routine()

            time.sleep_ms(25)