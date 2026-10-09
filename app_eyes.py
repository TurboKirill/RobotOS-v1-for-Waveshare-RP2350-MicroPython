# app_eyes.py - Полнофункциональный модуль мимики робота (9 анимаций + палитра цветов)
import time
import math
import random
import struct
import st7789

# ПРАВИЛЬНАЯ ПАЛИТРА ЦВЕТОВ (через color565 с аппаратной перестановкой байтов)
COLOR_PALETTE = [
    ("CYAN",    st7789.ST7789.color565(0, 240, 255)),   # 🩵 Неоновый Бирюзовый
    ("GREEN",   st7789.ST7789.color565(0, 255, 60)),    # 💚 Ярко-зелёный
    ("YELLOW",  st7789.ST7789.color565(255, 230, 0)),   # 💛 Жёлтый
    ("RED",     st7789.ST7789.color565(255, 20, 20)),   # 🔴 Боевой красный
    ("PURPLE",  st7789.ST7789.color565(200, 30, 255)),  # 💜 Пурпурный
    ("WHITE",   st7789.ST7789.color565(255, 255, 255)), # ⚪ Чистый белый
    ("BLUE",    st7789.ST7789.color565(0, 100, 255)),   # 💙 Настоящий синий
    ("ORANGE",  st7789.ST7789.color565(255, 120, 0)),   # 🧡 Оранжевый
]

class RobotEyesApp:
    def __init__(self, tft, audio, inputs, color_idx=0, mode="DEMO", config=None):
        self.tft = tft
        self.audio = audio
        self.inputs = inputs
        self.color_idx = color_idx
        self.mode = mode
        self.cfg = config if config else {"vol_ui": 30, "mute": False}

        # Размеры глаз для экрана 240x320
        self.ref_w = 72
        self.ref_h = 86
        self.ref_r = 16
        self.space = 22
        self.cx, self.cy = 120, 150

        self.anim_idx = 0
        self.anim_names = [
            "0: WAKEUP", "1: NORMAL", "2: LOOK LEFT", "3: LOOK RIGHT",
            "4: BLINK", "5: FAST BLINK", "6: HAPPY SMILE", "7: SAD",
            "8: SACCADE", "9: SLEEP"
        ]

        self.reset_coords()

    @property
    def current_color(self):
        return COLOR_PALETTE[self.color_idx][1]

    def reset_coords(self):
        self.lx = self.cx - self.ref_w // 2 - self.space // 2
        self.ly = self.cy
        self.rx = self.cx + self.ref_w // 2 + self.space // 2
        self.ry = self.cy
        self.lw, self.lh = self.ref_w, self.ref_h
        self.rw, self.rh = self.ref_w, self.ref_h
        self.r = self.ref_r

    def beep(self, freq, ms, vol=1500):
        """Мягкие электронные трели робота"""
        if self.cfg.get("mute") or self.cfg.get("vol_ui", 30) == 0:
            return
        rate = 22050
        samples = int(rate / freq)
        cycle = bytearray(samples * 2)
        # Тихий уютный голос робота
        amp = int(1500 * (self.cfg.get("vol_ui", 30) / 100))
        for i in range(samples):
            v = int(amp * math.sin(2 * math.pi * i / samples))
            struct.pack_into("<h", cycle, i * 2, v)
        for _ in range(int((ms / 1000) * freq)):
            self.audio.write(cycle)

    def draw_round_rect(self, x, y, w, h, r, color):
        if r <= 0 or h <= 2 * r or w <= 2 * r:
            self.tft.fill_rect(x, y, w, h, color)
            return
        self.tft.fill_rect(x, y + r, w, h - 2 * r, color)
        for dy in range(r):
            y_dist = r - dy
            dx = int(math.sqrt(r * r - y_dist * y_dist))
            self.tft.fill_rect(x + r - dx, y + dy, w - 2 * r + 2 * dx, 1, color)
            self.tft.fill_rect(x + r - dx, y + h - 1 - dy, w - 2 * r + 2 * dx, 1, color)

    def render(self, caption=None):
        self.tft.fill(0x0000)
        # Глаза
        self.draw_round_rect(
            int(self.lx - self.lw // 2), int(self.ly - self.lh // 2),
            int(self.lw), int(self.lh), self.r, self.current_color
        )
        self.draw_round_rect(
            int(self.rx - self.rw // 2), int(self.ry - self.rh // 2),
            int(self.rw), int(self.rh), self.r, self.current_color
        )
        # Нижняя подсказка
        if caption:
            self.tft.text(caption, 10, 290, 0x7BEF)
            self.tft.text(f"COLOR: {COLOR_PALETTE[self.color_idx][0]}", 10, 305, 0x07FF)
        self.tft.show()

    # ================= 9 АНИМАЦИЙ ИЗ ARDUINO =================

    def anim_0_wakeup(self):
        self.beep(600, 30); self.beep(900, 50); self.beep(1200, 80)
        for h in range(4, self.ref_h + 1, 8):
            self.lh = self.rh = h
            self.r = min(self.ref_r, h // 2)
            self.render("0: WAKEUP")
            time.sleep_ms(20)
        self.reset_coords()
        self.render("0: WAKEUP")

    def anim_1_normal(self):
        self.reset_coords()
        self.render("1: NORMAL")

    def anim_2_look_left(self):
        self.beep(1100, 40); self.beep(1500, 50)
        self.lw += 12; self.lh += 12
        self.lx -= 26; self.rx -= 26
        self.render("2: LOOK LEFT")
        time.sleep(0.8)
        self.reset_coords()

    def anim_3_look_right(self):
        self.beep(1100, 40); self.beep(1500, 50)
        self.rw += 12; self.rh += 12
        self.lx += 26; self.rx += 26
        self.render("3: LOOK RIGHT")
        time.sleep(0.8)
        self.reset_coords()

    def anim_4_blink(self):
        self.beep(1400, 10, vol=3000)
        orig_h = self.lh
        for h in [orig_h // 2, 4, orig_h // 2, orig_h]:
            self.lh = self.rh = h
            self.r = min(self.ref_r, h // 2)
            self.render("4: BLINK")
            time.sleep_ms(20)
        self.reset_coords()

    def anim_5_fast_blink(self):
        self.anim_4_blink()
        time.sleep_ms(80)
        self.anim_4_blink()

    def anim_6_happy(self):
        for f in [900, 1300, 1750]: self.beep(f, 30)
        self.render("6: HAPPY SMILE")
        for i in range(12):
            self.tft.fill_rect(int(self.lx - self.lw // 2), int(self.ly + 10 + i * 2), self.lw, 15, 0x0000)
            self.tft.fill_rect(int(self.rx - self.rw // 2), int(self.ry + 10 + i * 2), self.rw, 15, 0x0000)
            self.tft.show()
            time.sleep_ms(25)
        time.sleep(1.0)
        self.reset_coords()
        self.render("6: HAPPY SMILE")

    def anim_7_sad(self):
        self.beep(700, 80); self.beep(450, 120)
        self.render("7: SAD")
        # Срезаем верхнюю часть
        for i in range(10):
            self.tft.fill_rect(int(self.lx - self.lw // 2), int(self.ly - self.lh // 2), self.lw, 12 + i * 2, 0x0000)
            self.tft.fill_rect(int(self.rx - self.rw // 2), int(self.ry - self.lh // 2), self.rw, 12 + i * 2, 0x0000)
            self.tft.show()
            time.sleep_ms(25)
        time.sleep(1.0)
        self.reset_coords()
        self.render("7: SAD")

    def anim_8_saccade(self):
        for _ in range(3):
            dx = random.choice([-15, 15])
            dy = random.choice([-8, 8])
            self.lx += dx; self.rx += dx
            self.ly += dy; self.ry += dy
            self.render("8: SACCADE")
            time.sleep_ms(120)
            self.lx -= dx; self.rx -= dx
            self.ly -= dy; self.ry -= dy
        self.render("8: SACCADE")

    def anim_9_sleep(self):
        self.beep(800, 50); self.beep(400, 100)
        for h in range(self.ref_h, 3, -8):
            self.lh = self.rh = h
            self.r = min(self.ref_r, h // 2)
            self.render("9: SLEEP")
            time.sleep_ms(20)
        time.sleep(1.0)
        self.reset_coords()

    def play_by_index(self, idx):
        funcs = [
            self.anim_0_wakeup, self.anim_1_normal, self.anim_2_look_left,
            self.anim_3_look_right, self.anim_4_blink, self.anim_5_fast_blink,
            self.anim_6_happy, self.anim_7_sad, self.anim_8_saccade, self.anim_9_sleep
        ]
        if 0 <= idx < len(funcs):
            funcs[idx]()

    def run(self):
        self.anim_0_wakeup()
        last_auto = time.ticks_ms()

        while True:
            ev = self.inputs.get_event()
            if ev:
                if ev == 'BACK':
                    self.beep(400, 50)
                    break

                # Листаем анимации 0..9 (Влево / Вправо)
                elif ev == 'RIGHT':
                    self.anim_idx = (self.anim_idx + 1) % 10
                    self.play_by_index(self.anim_idx)
                elif ev == 'LEFT':
                    self.anim_idx = (self.anim_idx - 1) % 10
                    self.play_by_index(self.anim_idx)

                # Меняем цвет глаз (Вверх / Вниз)
                elif ev == 'UP':
                    self.color_idx = (self.color_idx + 1) % len(COLOR_PALETTE)
                    self.beep(1200, 20)
                    self.render(self.anim_names[self.anim_idx])
                elif ev == 'DOWN':
                    self.color_idx = (self.color_idx - 1) % len(COLOR_PALETTE)
                    self.beep(1000, 20)
                    self.render(self.anim_names[self.anim_idx])

                elif ev == 'ENTER':
                    # Повторить текущую анимацию
                    self.play_by_index(self.anim_idx)

                last_auto = time.ticks_ms()

            # В демо-режиме робот сам случайно меняет анимации
            if self.mode == "DEMO":
                now = time.ticks_ms()
                if time.ticks_diff(now, last_auto) > 2500:
                    self.anim_idx = random.choice([1, 2, 3, 4, 5, 6, 8])
                    self.play_by_index(self.anim_idx)
                    last_auto = time.ticks_ms()

            time.sleep_ms(20)