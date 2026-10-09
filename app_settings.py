# app_settings.py - Меню системных настроек (Громкость, Яркость экрана, Часы)
import time
import math
import struct
import st7789
from machine import Pin, PWM, RTC

C_BG      = st7789.ST7789.color565(10, 14, 26)
C_HEADER  = st7789.ST7789.color565(220, 20, 60)   # Красный для настроек
C_SEL_BG  = st7789.ST7789.color565(35, 45, 75)
C_GLOW    = st7789.ST7789.color565(0, 240, 255)
C_WHITE   = 0xFFFF
C_GRAY    = st7789.ST7789.color565(130, 145, 175)
C_GREEN   = st7789.ST7789.color565(0, 230, 118)
C_RED     = st7789.ST7789.color565(255, 60, 60)

class SettingsApp:
    def __init__(self, tft, audio, inputs, config):
        self.tft = tft
        self.audio = audio
        self.inputs = inputs
        self.cfg = config # Словарь общих настроек системы
        self.rtc = RTC()

        # Настройка ШИМ подсветки на GP21
        try:
            self.pwm_bl = PWM(Pin(21))
            self.pwm_bl.freq(1000)
            self.apply_brightness()
        except:
            self.pwm_bl = None

    def apply_brightness(self):
        """Применение аппаратной яркости экрана через ШИМ"""
        if self.pwm_bl:
            # duty_u16 от 1000 до 65535
            duty = int(65535 * (max(5, self.cfg["brightness"]) / 100))
            self.pwm_bl.duty_u16(duty)

    def beep(self, freq=900, ms=15):
        """Мягкий тихий щелчок с учетом настроек громкости"""
        if self.cfg["mute"] or self.cfg["vol_ui"] == 0:
            return
        rate = 22050
        samples = int(rate / freq)
        cycle = bytearray(samples * 2)
        # Мягкая громкость (максимум 2000 вместо старых 8000)
        amp = int(2000 * (self.cfg["vol_ui"] / 100))
        for i in range(samples):
            v = int(amp * math.sin(2 * math.pi * i / samples))
            struct.pack_into("<h", cycle, i * 2, v)
        for _ in range(int((ms / 1000) * freq)):
            self.audio.write(cycle)

    def draw_slider(self, x, y, val):
        """Отрисовка аккуратного мини-ползунка"""
        self.tft.rect(x, y, 100, 8, C_GRAY)
        w = int(96 * (val / 100))
        if w > 0:
            self.tft.fill_rect(x + 2, y + 2, w, 4, C_GLOW)

    def run(self):
        menu_items = [
            "1. UI VOLUME",
            "2. MUTE SOUND",
            "3. BRIGHTNESS",
            "4. SET CLOCK (H)",
            "5. SET CLOCK (M)",
            "< BACK TO MENU"
        ]
        sel = 0

        while True:
            self.tft.fill(C_BG)
            # Шапка
            self.tft.fill_rect(0, 0, 240, 36, C_HEADER)
            self.tft.text("SYSTEM SETTINGS", 14, 14, C_WHITE)

            y = 52
            for i, item in enumerate(menu_items):
                is_act = (i == sel)
                if is_act:
                    self.tft.fill_rect(8, y - 3, 224, 30, C_SEL_BG)
                    self.tft.rect(8, y - 3, 224, 30, C_GLOW)

                col = C_GLOW if is_act else C_WHITE
                self.tft.text(item, 16, y + 2, col)

                # Значения настроек справа
                if i == 0: # Громкость
                    self.tft.text(f"{self.cfg['vol_ui']}%", 175, y + 2, C_WHITE)
                    self.draw_slider(125, y + 15, self.cfg['vol_ui'])
                elif i == 1: # Mute
                    txt = "[ ON ]" if self.cfg["mute"] else "[ OFF ]"
                    c = C_RED if self.cfg["mute"] else C_GREEN
                    self.tft.text(txt, 165, y + 2, c)
                elif i == 2: # Яркость
                    self.tft.text(f"{self.cfg['brightness']}%", 175, y + 2, C_WHITE)
                    self.draw_slider(125, y + 15, self.cfg['brightness'])
                elif i == 3: # Часы
                    self.tft.text(f"{self.cfg['hour']:02d} h", 175, y + 2, C_GLOW)
                elif i == 4: # Минуты
                    self.tft.text(f"{self.cfg['minute']:02d} m", 175, y + 2, C_GLOW)

                y += 38

            # Нижняя строка подсказки
            self.tft.line(0, 282, 240, 282, C_GRAY)
            self.tft.text("NAV: [UP/DOWN]  ADJUST: [< >]", 8, 294, C_GRAY)
            self.tft.show()

            while True:
                ev = self.inputs.get_event()
                if ev:
                    if ev == 'UP':
                        sel = (sel - 1) % len(menu_items)
                        self.beep(850, 12)
                        break
                    elif ev == 'DOWN':
                        sel = (sel + 1) % len(menu_items)
                        self.beep(750, 12)
                        break
                    elif ev == 'BACK' or (ev == 'ENTER' and sel == 5):
                        self.beep(600, 20)
                        return
                    elif ev == 'ENTER' and sel == 1:
                        # Переключение Mute
                        self.cfg["mute"] = not self.cfg["mute"]
                        self.beep(1000, 20)
                        break
                    elif ev in ['LEFT', 'RIGHT']:
                        step = 1 if ev == 'RIGHT' else -1
                        if sel == 0: # Громкость
                            self.cfg["vol_ui"] = max(0, min(100, self.cfg["vol_ui"] + step * 10))
                            self.beep(1000, 15)
                        elif sel == 1: # Mute
                            self.cfg["mute"] = not self.cfg["mute"]
                            self.beep(1000, 15)
                        elif sel == 2: # Яркость
                            self.cfg["brightness"] = max(10, min(100, self.cfg["brightness"] + step * 10))
                            self.apply_brightness()
                            self.beep(1100, 15)
                        elif sel == 3: # Часы
                            self.cfg["hour"] = (self.cfg["hour"] + step) % 24
                            self.rtc.datetime((2025, 10, 6, 1, self.cfg["hour"], self.cfg["minute"], 0, 0))
                            self.beep(900, 15)
                        elif sel == 4: # Минуты
                            self.cfg["minute"] = (self.cfg["minute"] + step) % 60
                            self.rtc.datetime((2025, 10, 6, 1, self.cfg["hour"], self.cfg["minute"], 0, 0))
                            self.beep(900, 15)
                        break
                time.sleep_ms(20)