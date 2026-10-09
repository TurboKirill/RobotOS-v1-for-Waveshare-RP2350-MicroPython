# gui.py - RobotOS: Windows Phone Metro UI + рабочее управление
# Waveshare RP2350-PiZero, ST7789 240x320
import time
import math
import struct
import random
import gc
import sys
import st7789
import app_eyes
import app_files
import app_gallery
import app_player
import app_editor
import app_settings
import app_arkanoid
import app_snake
import app_doom
import app_servo_test
import app_weather
import app_sleep
from machine import PWM, Pin


def rgb(r, g, b):
    return st7789.ST7789.color565(r, g, b)


# ---------------------------------------------------------------- палитра
C_BG    = 0x0000
C_WHITE = 0xFFFF
C_GRAY  = rgb(140, 145, 155)
C_CYAN  = rgb(0, 240, 255)
C_GREEN = rgb(0, 230, 118)
C_DARK  = rgb(20, 24, 35)     # фон выбранного пункта списка
C_LINE  = 0x2104              # тонкая разделительная линия

EYE_PALETTE = [
    ("CYAN",   rgb(0, 240, 255)),
    ("GREEN",  rgb(0, 230, 118)),
    ("YELLOW", rgb(255, 220, 0)),
    ("RED",    rgb(255, 40, 40)),
    ("PURPLE", rgb(170, 60, 255)),
    ("WHITE",  rgb(255, 255, 255)),
    ("BLUE",   rgb(40, 100, 255)),
    ("ORANGE", rgb(255, 140, 0)),
]

# ---------------------------------------------------------------- сетка плиток
# Поля 4 px, зазоры 3 px. 0-1 верх, 2-3-4 середина, 5-6 низ.
LAYOUT = [
    {"x": 4,   "y": 25,  "w": 151, "h": 86},  # 0 Robot
    {"x": 158, "y": 25,  "w": 78,  "h": 86},  # 1 Apps
    {"x": 4,   "y": 114, "w": 74,  "h": 86},  # 2 Games
    {"x": 81,  "y": 114, "w": 78,  "h": 86},  # 3 Player
    {"x": 162, "y": 114, "w": 74,  "h": 86},  # 4 Files
    {"x": 4,   "y": 203, "w": 151, "h": 86},  # 5 Settings
    {"x": 158, "y": 203, "w": 78,  "h": 86},  # 6 Power
]

TILES = [
    {"title": "Robot Core", "color": rgb(0, 138, 230)},
    {"title": "Apps",       "color": rgb(140, 45, 220)},
    {"title": "Games",      "color": rgb(16, 124, 65)},
    {"title": "Player",     "color": 0xFFFF},
    {"title": "Files",      "color": rgb(235, 110, 0)},
    {"title": "Settings",   "color": rgb(52, 60, 72)},
    {"title": "Power",      "color": rgb(38, 48, 125)},
]

# Таблица соседей: для каждого направления -> {откуда: куда}.
# Нет записи = остаёмся на месте (для LEFT/RIGHT) либо переход по кругу (UP/DOWN).
NAV = {
    "RIGHT": {0: 1, 2: 3, 3: 4, 5: 6},
    "LEFT":  {1: 0, 3: 2, 4: 3, 6: 5},
    "DOWN":  {0: 2, 1: 4, 2: 5, 3: 5, 4: 6, 5: 0, 6: 1},
    "UP":    {0: 5, 1: 6, 2: 0, 3: 0, 4: 1, 5: 2, 6: 4},
}

# Мелкий 5x7 шрифт для крупной температуры на плитке
GLYPHS = {
    "0": ("11111", "10001", "10011", "10101", "11001", "10001", "11111"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("11110", "00001", "00001", "01110", "10000", "10000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("10010", "10010", "10010", "11111", "00010", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    "+": ("00100", "00100", "11111", "00100", "00100", "00000", "00000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "00110", "00110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
}

BACK_KEYS = ("BACK", "ESC")


class RobotOS_GUI:
    def __init__(self, tft, audio, inputs):
        self.tft = tft
        self.audio = audio
        self.inputs = inputs
        self.selected = 0
        self.eye_idx = 0                      # выбранный цвет глаз (помним между заходами)

        # Live Tiles: одновременно перевёрнута только ОДНА плитка
        self.flipped = [False] * 7
        self.active_flip = -1
        self.flip_interval = 3500
        now = time.ticks_ms()
        self.last_flip_time = now
        self.last_input = now
        self.clock_tick = now

        self._wave = {}                       # кэш звуковых волн для click_sound

        self.cfg = {
            "vol_ui": 30,
            "mute": False,
            "brightness": 90,
            "hour": 22,
            "minute": 52,
        }

        try:
            self.pwm_bl = PWM(Pin(21))
            self.pwm_bl.freq(1000)
        except Exception:
            self.pwm_bl = None
        self.apply_brightness()

    # ================================================================ сервис
    def apply_brightness(self):
        if self.pwm_bl:
            try:
                self.pwm_bl.duty_u16(int(65535 * (self.cfg["brightness"] / 100)))
            except Exception:
                pass

    def _wave_for(self, freq):
        amp = int(1200 * (self.cfg["vol_ui"] / 100))
        key = (freq, amp)
        w = self._wave.get(key)
        if w is None:
            n = max(2, int(22050 / freq))
            w = bytearray(n * 2)
            for i in range(n):
                struct.pack_into("<h", w, i * 2, int(amp * math.sin(2 * math.pi * i / n)))
            if len(self._wave) > 16:
                self._wave.clear()
            self._wave[key] = w
        return w

    def click_sound(self, freq=1200, ms=10):
        if self.cfg["mute"] or self.cfg["vol_ui"] == 0:
            return
        cycle = self._wave_for(freq)
        for _ in range(max(1, int((ms / 1000) * freq))):
            self.audio.write(cycle)

    def launch(self, factory):
        """Запуск приложения. Ошибка в приложении не роняет всю систему."""
        try:
            factory().run()
        except Exception as e:
            try:
                sys.print_exception(e)
            except Exception:
                pass
            self.show_error(e)
        gc.collect()

    def show_error(self, e):
        self.tft.fill(C_BG)
        self.tft.fill_rect(0, 0, 240, 42, rgb(200, 30, 50))
        self.tft.text("ERROR", 16, 16, C_WHITE)
        msg = "%s: %s" % (type(e).__name__, e)
        y = 60
        for i in range(0, min(len(msg), 28 * 8), 28):
            self.tft.text(msg[i:i + 28], 6, y, C_WHITE)
            y += 14
        self.tft.text("Press BACK / OK", 12, 292, C_CYAN)
        self.tft.show()
        while True:
            ev = self.inputs.get_event()
            if ev in ("BACK", "ESC", "ENTER"):
                break
            time.sleep_ms(20)

    # ================================================================ часы
    def update_clock(self, now):
        changed = False
        while time.ticks_diff(now, self.clock_tick) >= 60000:
            self.clock_tick = time.ticks_add(self.clock_tick, 60000)
            m = self.cfg["minute"] + 1
            h = self.cfg["hour"]
            if m >= 60:
                m = 0
                h = (h + 1) % 24
            self.cfg["minute"] = m
            self.cfg["hour"] = h
            changed = True
        return changed

    # ================================================================ главный экран
    def draw_battery(self, x, y):
        self.tft.text("100%", x - 34, y + 1, C_WHITE)
        self.tft.rect(x, y, 22, 11, C_WHITE)
        self.tft.fill_rect(x + 22, y + 3, 2, 5, C_WHITE)
        self.tft.fill_rect(x + 2, y + 2, 18, 7, C_GREEN)

    def draw_header(self):
        self.tft.fill_rect(0, 0, 240, 22, C_BG)
        self.tft.text("RobotOS", 5, 7, C_CYAN)
        self.tft.text("%02d:%02d" % (self.cfg["hour"], self.cfg["minute"]), 101, 7, C_WHITE)
        self.draw_battery(210, 7)

    def fill_circle(self, cx, cy, r, color):
        for dy in range(-r, r + 1):
            dx = int(math.sqrt(r * r - dy * dy))
            self.tft.fill_rect(cx - dx, cy + dy, dx * 2 + 1, 1, color)

    def draw_tile_icon(self, idx, x, y):
        """Иконки 28x28 px. Вырезы рисуются цветом самой плитки."""
        t = self.tft
        bg = TILES[idx]["color"]
        W = C_WHITE
        if idx == 0:      # белые глазки робота (как на обороте, но белые)
            self.draw_round_rect(x - 16, y, 18, 28, 6, W)
            self.draw_round_rect(x + 10, y, 18, 28, 6, W)
        elif idx == 1:    # сетка приложений
            for gx in (0, 16):
                for gy in (0, 16):
                    self.draw_round_rect(x + gx, y + gy, 12, 12, 2, W)
        elif idx == 2:    # геймпад
            self.draw_round_rect(x, y + 5, 28, 19, 7, W)
            t.fill_rect(x + 7, y + 10, 3, 9, bg)              # D-pad
            t.fill_rect(x + 4, y + 13, 9, 3, bg)
            self.fill_circle(x + 20, y + 12, 2, bg)           # кнопки
            self.fill_circle(x + 23, y + 17, 2, bg)
        elif idx == 3:    # эквалайзер (чёрный на белой плитке)
            hs = (10, 20, 28, 16, 22)
            for i in range(5):
                t.fill_rect(x + i * 6, y + 28 - hs[i], 4, hs[i], 0x0000)
        elif idx == 4:    # папка
            self.draw_round_rect(x, y + 3, 13, 8, 2, W)      # язычок
            self.draw_round_rect(x, y + 7, 28, 20, 3, W)
            t.fill_rect(x, y + 12, 28, 1, bg)                 # линия сгиба
        elif idx == 5:    # шестерёнка
            cx, cy = x + 14, y + 14
            self.fill_circle(cx, cy, 9, W)
            t.fill_rect(cx - 2, cy - 14, 5, 5, W)
            t.fill_rect(cx - 2, cy + 10, 5, 5, W)
            t.fill_rect(cx - 14, cy - 2, 5, 5, W)
            t.fill_rect(cx + 10, cy - 2, 5, 5, W)
            t.fill_rect(cx - 11, cy - 11, 4, 4, W)
            t.fill_rect(cx + 8, cy - 11, 4, 4, W)
            t.fill_rect(cx - 11, cy + 8, 4, 4, W)
            t.fill_rect(cx + 8, cy + 8, 4, 4, W)
            self.fill_circle(cx, cy, 4, bg)
        elif idx == 6:    # полумесяц со звёздами
            cx, cy = x + 12, y + 14
            self.fill_circle(cx, cy, 13, W)
            self.fill_circle(cx + 7, cy - 4, 11, bg)
            t.fill_rect(x + 21, y + 17, 5, 1, W)              # звезда
            t.fill_rect(x + 23, y + 15, 1, 5, W)
            t.fill_rect(x + 18, y + 6, 2, 2, W)               # звёздочка

    def draw_round_rect(self, x, y, w, h, r, color):
        if r <= 0 or h <= 2 * r or w <= 2 * r:
            self.tft.fill_rect(x, y, w, h, color)
            return
        self.tft.fill_rect(x, y + r, w, h - 2 * r, color)
        for dy in range(r):
            y_dist = r - dy
            dx = int(math.sqrt(r * r - y_dist * y_dist))
            line_w = w - 2 * r + 2 * dx
            self.tft.fill_rect(x + r - dx, y + dy, line_w, 1, color)
            self.tft.fill_rect(x + r - dx, y + h - 1 - dy, line_w, 1, color)

    def draw_mini_robot_eyes(self, x, y, w, h):
        eye_color = EYE_PALETTE[self.eye_idx][1]   # цвет совпадает с выбранным в меню
        ew, eh, radius, gap = 28, 34, 8, 10
        ex = x + (w - (ew * 2 + gap)) // 2
        ey = y + 8
        self.draw_round_rect(ex, ey, ew, eh, radius, eye_color)
        self.draw_round_rect(ex + ew + gap, ey, ew, eh, radius, eye_color)

    def draw_large_temperature(self, text, x, y, color, scale=2):
        cursor = x
        for ch in text:
            g = GLYPHS.get(ch)
            if g:
                for gy, row in enumerate(g):
                    for gx, bit in enumerate(row):
                        if bit == "1":
                            self.tft.fill_rect(cursor + gx * scale, y + gy * scale,
                                               scale, scale, color)
            cursor += 6 * scale

    def live_data(self, idx):
        """Данные оборотной стороны плитки. Меняйте cfg[...] из приложений - плитка подхватит."""
        if idx == 2:
            return "HI-SCORE", "%d pts" % self.cfg.get("hiscore", 990)
        if idx == 3:
            return "MUSIC", "Track %02d" % self.cfg.get("track", 1)
        if idx == 4:
            return "STORAGE", "MicroSD"
        if idx == 5:
            return "ROBOT-OS 2.0", "RP2350 150MHz"
        if idx == 6:
            return "BATTERY", "%d%%" % self.cfg.get("battery", 100)
        return "", ""

    def draw_tile_body(self, idx, x, y, w, h, is_back):
        t = TILES[idx]
        col = rgb(20, 22, 28) if is_back else t["color"]
        text_col = 0x0000 if (idx == 3 and not is_back) else C_WHITE

        self.tft.fill_rect(x, y, w, h, col)
        if w < LAYOUT[idx]["w"]:  # во время flip узкую плитку не детализируем
            return

        maxc = (w - 8) // 8
        if not is_back:
            self.draw_tile_icon(idx, x + w - 34, y + 9)
            self.tft.text(t["title"][:maxc], x + 7, y + h - 18, text_col)
            return

        if idx == 0:
            self.draw_mini_robot_eyes(x, y, w, h)
            self.tft.text("AI ACTIVE", x + 8, y + h - 28, EYE_PALETTE[self.eye_idx][1])
            self.tft.text("RobotOS Core", x + 8, y + h - 14, C_WHITE)
        elif idx == 1:
            self.tft.text("WEATHER", x + 7, y + 8, C_WHITE)
            self.draw_large_temperature(self.cfg.get("temp_str", "+24.5C")[:6], x + 7, y + 28, C_WHITE)
        else:
            a, b = self.live_data(idx)
            self.tft.text(a[:maxc], x + 7, y + 8, C_WHITE)
            self.tft.text(b[:maxc], x + 7, y + h - 18, C_WHITE)

    def draw_selection(self, x, y, w, h):
        """Двойная белая рамка снаружи плитки - видно на любом цвете."""
        self.tft.rect(x - 2, y - 2, w + 4, h + 4, C_WHITE)
        self.tft.rect(x - 1, y - 1, w + 2, h + 2, C_WHITE)

    def draw_tile(self, idx):
        p = LAYOUT[idx]
        self.draw_tile_body(idx, p["x"], p["y"], p["w"], p["h"], self.flipped[idx])
        if idx == self.selected:
            self.draw_selection(p["x"], p["y"], p["w"], p["h"])

    def flip_tile(self, idx):
        """Переворот плитки сужением по ширине. Рамка выделения снаружи не затрагивается."""
        p = LAYOUT[idx]
        x, y, w, h = p["x"], p["y"], p["w"], p["h"]
        cur = self.flipped[idx]
        for deg in (20, 45, 70, 90, 110, 135, 160, 180):
            draw_w = max(3, int(w * abs(math.cos(math.radians(deg)))))
            draw_x = x + (w - draw_w) // 2
            self.tft.fill_rect(x, y, w, h, C_BG)
            show_back = (not cur) if deg >= 90 else cur
            self.draw_tile_body(idx, draw_x, y, draw_w, h, show_back)
            self.tft.show()
            time.sleep_ms(12)
        self.flipped[idx] = not cur

    def flip_next_tile(self):
        if self.active_flip != -1 and self.flipped[self.active_flip]:
            self.flip_tile(self.active_flip)
            self.render_menu()
            time.sleep_ms(40)
        candidates = [i for i in range(7) if i != self.active_flip]
        self.active_flip = random.choice(candidates)
        self.flip_tile(self.active_flip)
        self.render_menu()

    def render_remote_panel(self):
        self.tft.fill_rect(0, 294, 240, 26, C_BG)

        # D-pad
        cx, cy, arm, thick = 30, 307, 8, 5
        self.tft.fill_rect(cx - thick // 2, cy - arm, thick, arm * 2 + 1, C_WHITE)
        self.tft.fill_rect(cx - arm, cy - thick // 2, arm * 2 + 1, thick, C_WHITE)

        # OK
        ok_x, ok_y = 120, 307
        for yy in range(-7, 8):
            xx = int(math.sqrt(max(0, 49 - yy * yy)))
            self.tft.fill_rect(ok_x - xx, ok_y + yy, xx * 2 + 1, 1, C_WHITE)
        self.tft.text("OK", ok_x - 7, ok_y - 4, C_BG)

        # BACK
        self.tft.text("*", 191, 299, C_CYAN)
        self.tft.text("BACK", 202, 299, C_WHITE)

    def render_menu(self):
        self.tft.fill(C_BG)
        self.draw_header()
        for i in range(7):
            self.draw_tile(i)
        self.render_remote_panel()
        self.tft.show()

    def zoom_animation(self, idx):
        p = LAYOUT[idx]
        x0, y0, w0, h0 = p["x"], p["y"], p["w"], p["h"]
        col = TILES[idx]["color"]
        for step in (0.35, 0.7, 1.0):
            x = int(x0 - x0 * step)
            y = int(y0 - y0 * step)
            w = int(w0 + (240 - w0) * step)
            h = int(h0 + (320 - h0) * step)
            self.tft.fill_rect(x, y, w, h, col)
            self.tft.show()
            time.sleep_ms(15)

    # ================================================================ подменю
    def list_menu(self, title, color, items, sel, start_y, step, on_lr=None):
        """Универсальное Metro-меню. Возвращает индекс (ENTER) или -1 (BACK)."""
        n = len(items)
        back_idx = n - 1
        while True:
            self.tft.fill(C_BG)
            self.tft.fill_rect(0, 0, 240, 42, color)
            self.tft.text(title, 16, 16, C_WHITE)

            for i, item in enumerate(items):
                y = start_y + i * step
                if i == sel:
                    self.tft.fill_rect(10, y - 4, 220, 26, C_DARK)
                    self.tft.rect(10, y - 4, 220, 26, C_WHITE)
                    self.tft.text("> " + item, 18, y + 4, C_WHITE)
                else:
                    self.tft.text("  " + item, 18, y + 4, C_GRAY)

            self.tft.line(0, 280, 240, 280, C_LINE)
            self.tft.text("NAV: [UP/DOWN]  OK: [ENTER]", 12, 292, C_WHITE)
            self.tft.show()

            while True:
                ev = self.inputs.get_event()
                if ev:
                    if ev == 'UP':
                        sel = (sel - 1) % n
                        self.click_sound(850, 15)
                        break
                    elif ev == 'DOWN':
                        sel = (sel + 1) % n
                        self.click_sound(750, 15)
                        break
                    elif ev in BACK_KEYS:
                        self.click_sound(600, 30)
                        return -1
                    elif ev == 'ENTER':
                        self.click_sound(600 if sel == back_idx else 1400, 30)
                        return sel
                    elif ev in ('LEFT', 'RIGHT') and on_lr and on_lr(ev, sel):
                        break
                time.sleep_ms(20)

    def menu_robot(self):
        items = ["1. AI MODULE (SOON)", "2. PROGRAMMING", "3. ROBOT EYES (DEMO)",
                 "4. ANIMATION TESTER", "", "< BACK"]

        def refresh():
            items[4] = "5. EYE COLOR: [%s]" % EYE_PALETTE[self.eye_idx][0]

        def on_lr(ev, s):
            if s != 4:
                return False
            self.eye_idx = (self.eye_idx + (1 if ev == 'RIGHT' else -1)) % len(EYE_PALETTE)
            refresh()
            self.click_sound(1100, 20)
            return True

        refresh()
        sel = 2
        while True:
            sel = self.list_menu("ROBOTICS", TILES[0]["color"], items, sel, 65, 34, on_lr)
            if sel == -1 or sel == 5:
                return
            if sel == 2:
                self.launch(lambda: app_eyes.RobotEyesApp(
                    self.tft, self.audio, self.inputs, self.eye_idx, "DEMO", self.cfg))
            elif sel == 3:
                self.launch(lambda: app_eyes.RobotEyesApp(
                    self.tft, self.audio, self.inputs, self.eye_idx, "MANUAL", self.cfg))
            elif sel == 4:
                self.eye_idx = (self.eye_idx + 1) % len(EYE_PALETTE)
                refresh()

    def menu_apps(self):
        items = ["1. PHOTO GALLERY", "2. MUSIC PLAYER", "3. NOTEPAD++ (EDITOR)",
                 "4. SERVO TEST (ROBOT)", "5. CLIMATE & WEATHER", "< BACK"]
        sel = 4
        while True:
            sel = self.list_menu("APPLICATIONS", TILES[1]["color"], items, sel, 54, 35)
            if sel == -1 or sel == 5:
                return
            if sel == 0:
                self.launch(lambda: app_gallery.GalleryApp(
                    self.tft, self.audio, self.inputs, self.cfg))
            elif sel == 1:
                self.launch(lambda: app_player.MusicPlayerApp(
                    self.tft, self.audio, self.inputs))
            elif sel == 2:
                self.launch(lambda: app_editor.NotepadApp(
                    self.tft, self.audio, self.inputs, self.cfg, filepath="/sd/notes.txt"))
            elif sel == 3:
                self.launch(lambda: app_servo_test.ServoTestApp(
                    self.tft, self.audio, self.inputs, self.cfg))
            elif sel == 4:
                self.launch(lambda: app_weather.WeatherApp(
                    self.tft, self.audio, self.inputs, self.cfg))

    def menu_games(self):
        items = ["1. ARKANOID (BREAKOUT)", "2. CYBER-SNAKE", "3. DOOM-LITE (RAYCAST)", "< BACK"]
        sel = 0
        while True:
            sel = self.list_menu("RETRO GAMES", TILES[2]["color"], items, sel, 70, 40)
            if sel == -1 or sel == 3:
                return
            if sel == 0:
                self.launch(lambda: app_arkanoid.ArkanoidApp(
                    self.tft, self.audio, self.inputs, self.cfg))
            elif sel == 1:
                self.launch(lambda: app_snake.SnakeApp(
                    self.tft, self.audio, self.inputs, self.cfg))
            elif sel == 2:
                if app_doom:
                    self.launch(lambda: app_doom.DoomApp(
                        self.tft, self.audio, self.inputs, self.cfg))
                else:
                    self.show_error(ImportError("app_doom.py not found"))

    def open_section(self, idx):
        self.click_sound(1500, 25)
        self.zoom_animation(idx)

        if idx == 0:
            self.menu_robot()
        elif idx == 1:
            self.menu_apps()
        elif idx == 2:
            self.menu_games()
        elif idx == 3:
            self.launch(lambda: app_player.MusicPlayerApp(self.tft, self.audio, self.inputs))
        elif idx == 4:
            self.launch(lambda: app_files.FileManagerApp(
                self.tft, self.audio, self.inputs, self.cfg))
        elif idx == 5:
            self.launch(lambda: app_settings.SettingsApp(
                self.tft, self.audio, self.inputs, self.cfg))
            self.clock_tick = time.ticks_ms()      # время могли поменять в настройках
        elif idx == 6:
            self.launch(lambda: app_sleep.SleepApp(
                self.tft, self.audio, self.inputs, self.cfg, self.pwm_bl))

        # Возврат на главный экран
        self.apply_brightness()
        now = time.ticks_ms()
        self.update_clock(now)
        self.last_flip_time = now
        self.last_input = now
        self.render_menu()

    # ================================================================ главный цикл
    def run(self):
        self.render_menu()
        now = time.ticks_ms()
        self.last_flip_time = now
        self.last_input = now
        self.clock_tick = now

        while True:
            now = time.ticks_ms()

            # Часы идут сами
            if self.update_clock(now):
                self.draw_header()
                self.tft.show()

            # Live Tile: только когда пользователь 2 сек ничего не нажимал,
            # чтобы анимация не мешала навигации
            if (time.ticks_diff(now, self.last_flip_time) >= self.flip_interval and
                    time.ticks_diff(now, self.last_input) >= 2000):
                self.last_flip_time = now
                self.flip_next_tile()

            ev = self.inputs.get_event()
            if ev:
                self.last_input = now
                old_sel = self.selected

                if ev in NAV:
                    self.selected = NAV[ev].get(self.selected, self.selected)

                elif ev == 'ENTER':
                    # перевёрнутую плитку возвращаем лицом без анимации
                    if self.active_flip != -1:
                        self.flipped[self.active_flip] = False
                        self.active_flip = -1
                    self.open_section(self.selected)
                    continue

                elif ev in BACK_KEYS:
                    self.click_sound(600, 20)

                if old_sel != self.selected:
                    self.click_sound(1000, 12)
                    self.render_menu()

            time.sleep_ms(20)
