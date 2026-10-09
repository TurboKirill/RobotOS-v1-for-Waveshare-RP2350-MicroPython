# app_sleep.py - Анимация сна со скругленными живыми глазками
import time
import math
import struct
import st7789
from machine import Pin, PWM

C_BG   = 0x0000
C_GLOW = st7789.ST7789.color565(0, 240, 255)   # Неоновый бирюзовый (в тон глаз)
C_GRAY = st7789.ST7789.color565(100, 120, 160)

class SleepApp:
    def __init__(self, tft, audio, inputs, config, pwm_bl):
        self.tft = tft
        self.audio = audio
        self.inputs = inputs
        self.cfg = config
        self.pwm_bl = pwm_bl

        # Точные размеры и координаты глаз как в app_eyes.py
        self.w = 72
        self.h = 86
        self.lx = 72
        self.rx = 168
        self.cy = 150

    def beep(self, freq, ms, vol=1500):
        if self.cfg.get("mute") or self.cfg.get("vol_ui", 30) == 0:
            return
        rate = 22050
        samples = int(rate / freq)
        cycle = bytearray(samples * 2)
        amp = int(vol * (self.cfg.get("vol_ui", 30) / 100))
        for i in range(samples):
            v = int(amp * math.sin(2 * math.pi * i / samples))
            struct.pack_into("<h", cycle, i * 2, v)
        for _ in range(int((ms / 1000) * freq)):
            self.audio.write(cycle)

    def fade_backlight(self, from_pct, to_pct, steps=15):
        """Плавное аппаратное угасание/разгорание подсветки через ШИМ"""
        if not self.pwm_bl: return
        step = (to_pct - from_pct) / steps
        for i in range(steps):
            cur = from_pct + step * (i + 1)
            duty = int(65535 * (max(0, min(100, cur)) / 100))
            self.pwm_bl.duty_u16(duty)
            time.sleep_ms(20)

    def draw_round_rect(self, x, y, w, h, r, color):
        """Математическое скругление углов глаз"""
        if r <= 0 or h <= 2 * r or w <= 2 * r:
            self.tft.fill_rect(x, y, w, h, color)
            return
        # Центральное тело
        self.tft.fill_rect(x, y + r, w, h - 2 * r, color)
        # Скругление верхних и нижних дуг
        for dy in range(r):
            y_dist = r - dy
            dx = int(math.sqrt(r * r - y_dist * y_dist))
            self.tft.fill_rect(x + r - dx, y + dy, w - 2 * r + 2 * dx, 1, color)
            self.tft.fill_rect(x + r - dx, y + h - 1 - dy, w - 2 * r + 2 * dx, 1, color)

    def draw_both_eyes(self, w, h, r):
        """Отрисовка пары скругленных глаз"""
        # Левый глаз
        self.draw_round_rect(self.lx - w // 2, self.cy - h // 2, w, h, r, C_GLOW)
        # Правый глаз
        self.draw_round_rect(self.rx - w // 2, self.cy - h // 2, w, h, r, C_GLOW)

    def anim_collapse_to_slits(self):
        """Анимация: круглые глаза плавно смыкаются и засыпают"""
        # Звук засыпания
        self.beep(750, 40)
        self.beep(550, 60)
        self.beep(350, 100)

        # 1. Глаза мягко прищуриваются (высота 86 -> 4 пикселя) со скруглением!
        for h in [86, 60, 36, 18, 8, 4]:
            self.tft.fill(C_BG)
            r = min(16, h // 2)
            self.draw_both_eyes(self.w, h, r)
            self.tft.show()
            time.sleep_ms(25)

        # 2. Мягкая пауза с надписью Zzz...
        self.tft.text("Zzz...", self.rx - 10, self.cy - 24, C_GRAY)
        self.tft.show()
        time.sleep(0.8)

        # 3. Закрытые округлые полоски сжимаются в точки
        for w in [self.w, 48, 28, 12, 4]:
            self.tft.fill(C_BG)
            r = min(2, w // 2)
            self.draw_both_eyes(w, 4, r)
            self.tft.show()
            time.sleep_ms(20)

        # 4. Плавное потухание экрана в полную темноту
        current_br = self.cfg.get("brightness", 90)
        self.fade_backlight(current_br, 0, steps=20)
        self.tft.fill(C_BG)
        self.tft.show()

    def anim_wakeup(self):
        """Анимация: плавное открытие круглых глаз"""
        target_br = self.cfg.get("brightness", 90)
        
        # 1. Плавно разжигаем подсветку
        self.fade_backlight(0, target_br, steps=15)

        # 2. Из точек вырастают округлые щелочки
        for w in [4, 16, 36, 56, self.w]:
            self.tft.fill(C_BG)
            r = min(2, w // 2)
            self.draw_both_eyes(w, 4, r)
            self.tft.show()
            time.sleep_ms(15)

        # 3. Веки плавно распахиваются в большие круглые глаза!
        for h in [4, 16, 36, 60, self.h]:
            self.tft.fill(C_BG)
            r = min(16, h // 2)
            self.draw_both_eyes(self.w, h, r)
            self.tft.show()
            time.sleep_ms(20)

        # Радостная трель пробуждения
        self.beep(400, 30)
        self.beep(750, 40)
        self.beep(1200, 70)
        time.sleep(0.4)

    def run(self):
        # Засыпаем со скругленными веками
        self.anim_collapse_to_slits()

        print("💤 Режим сна: экран погашен, ждем нажатия любой кнопки...")

        # Ждем любую кнопку
        while True:
            ev = self.inputs.get_event()
            if ev:
                break
            time.sleep_ms(40)

        # Просыпаемся с круглыми глазками
        self.anim_wakeup()