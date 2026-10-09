# app_arkanoid.py - Арканоид с реальной физической регулировкой скорости мяча
import time
import math
import struct
import random
import st7789

C_BG     = 0x0000
C_WHITE  = 0xFFFF
C_GRAY   = st7789.ST7789.color565(100, 120, 150)
C_PADDLE = st7789.ST7789.color565(0, 240, 255)
C_BALL   = 0xFFFF
C_BORDER = st7789.ST7789.color565(30, 40, 70)
C_SPD    = st7789.ST7789.color565(255, 230, 0)

ROW_COLORS = [
    st7789.ST7789.color565(255, 30, 60),    # Ряд 0: 50 очков
    st7789.ST7789.color565(255, 120, 0),    # Ряд 1: 40 очков
    st7789.ST7789.color565(255, 230, 0),    # Ряд 2: 30 очков
    st7789.ST7789.color565(0, 230, 100),    # Ряд 3: 20 очков
    st7789.ST7789.color565(0, 180, 255),    # Ряд 4: 10 очков
]

class ArkanoidApp:
    def __init__(self, tft, audio, inputs, config=None):
        self.tft = tft
        self.audio = audio
        self.inputs = inputs
        self.cfg = config if config else {"vol_ui": 30, "mute": False}

        # 5 РЕАЛЬНЫХ ФИЗИЧЕСКИХ СКОРОСТЕЙ (пикселей за шаг, число шагов за кадр, скорость ракетки)
        # x1: 2 px (медленно), x2: 3 px, x3: 5 px, x4: 7 px, x5: 10 px (ракета!)
        self.physics_profiles = [
            {"step": 2, "substeps": 1, "pad_spd": 8},   # x1
            {"step": 3, "substeps": 1, "pad_spd": 11},  # x2
            {"step": 5, "substeps": 1, "pad_spd": 15},  # x3
            {"step": 4, "substeps": 2, "pad_spd": 19},  # x4 (8 px суммарно)
            {"step": 5, "substeps": 2, "pad_spd": 24},  # x5 (10 px суммарно)
        ]
        self.speed_lvl = 1  # По умолчанию x2 (Классика)

        # Платформа
        self.pad_w = 46
        self.pad_h = 7
        self.pad_y = 292
        self.pad_x = 120 - self.pad_w // 2

        # Мяч
        self.ball_size = 5
        self.reset_ball()

        # Кирпичи
        self.rows = 5
        self.cols = 6
        self.brick_w = 36
        self.brick_h = 10
        self.brick_y_start = 45
        self.init_bricks()

        self.score = 0
        self.lives = 3
        self.game_over = False
        self.game_won = False
        self.ball_attached = True

    def init_bricks(self):
        self.bricks = [[1 for _ in range(self.cols)] for _ in range(self.rows)]

    def reset_ball(self):
        self.ball_x = self.pad_x + self.pad_w // 2
        self.ball_y = self.pad_y - self.ball_size - 1
        prof = self.physics_profiles[self.speed_lvl]
        self.ball_dx = prof["step"]
        self.ball_dy = -prof["step"]
        self.ball_attached = True

    def apply_speed_to_ball(self):
        """Мгновенное изменение физической скорости летящего мяча"""
        step = self.physics_profiles[self.speed_lvl]["step"]
        # Сохраняем направление, но меняем силу импульса
        self.ball_dx = step if self.ball_dx > 0 else -step
        self.ball_dy = step if self.ball_dy > 0 else -step

    def beep(self, freq=900, ms=15):
        if self.cfg.get("mute") or self.cfg.get("vol_ui", 30) == 0:
            return
        rate = 22050
        samples = int(rate / freq)
        cycle = bytearray(samples * 2)
        amp = int(1200 * (self.cfg.get("vol_ui", 30) / 100))
        for i in range(samples):
            v = int(amp * math.sin(2 * math.pi * i / samples))
            struct.pack_into("<h", cycle, i * 2, v)
        for _ in range(int((ms / 1000) * freq)):
            self.audio.write(cycle)

    def draw_screen(self):
        self.tft.fill(C_BG)

        # Шапка
        self.tft.fill_rect(0, 0, 240, 28, C_BORDER)
        self.tft.text(f"SC:{self.score:04d}", 6, 10, C_WHITE)
        self.tft.text(f"SPD:x{self.speed_lvl + 1}", 92, 10, C_SPD)
        self.tft.text(f"LVL:{'#' * self.lives}", 172, 10, st7789.ST7789.color565(255, 60, 60))
        self.tft.line(0, 28, 240, 28, C_PADDLE)

        # Кирпичи
        remaining = 0
        for r in range(self.rows):
            for c in range(self.cols):
                if self.bricks[r][c] == 1:
                    remaining += 1
                    bx = 8 + c * (self.brick_w + 2)
                    by = self.brick_y_start + r * (self.brick_h + 3)
                    self.tft.fill_rect(bx, by, self.brick_w, self.brick_h, ROW_COLORS[r])
                    self.tft.line(bx, by, bx + self.brick_w - 1, by, C_WHITE)

        if remaining == 0:
            self.game_won = True

        # Платформа и мяч
        self.tft.fill_rect(int(self.pad_x), self.pad_y, self.pad_w, self.pad_h, C_PADDLE)
        self.tft.rect(int(self.pad_x), self.pad_y, self.pad_w, self.pad_h, C_WHITE)
        self.tft.fill_rect(int(self.ball_x), int(self.ball_y), self.ball_size, self.ball_size, C_BALL)

        if self.ball_attached:
            self.tft.text("PRESS [ENTER] TO SERVE", 30, 215, C_PADDLE)
            self.tft.text("UP/DOWN: Speed +/-", 45, 235, C_SPD)

        self.tft.show()

    def step_physics(self):
        """Один микрошаг физики (без туннелирования сквозь стены)"""
        if self.ball_attached:
            self.ball_x = self.pad_x + self.pad_w // 2 - self.ball_size // 2
            self.ball_y = self.pad_y - self.ball_size - 1
            return

        self.ball_x += self.ball_dx
        self.ball_y += self.ball_dy

        # Стены
        if self.ball_x <= 4:
            self.ball_x = 4
            self.ball_dx = abs(self.ball_dx)
            self.beep(600, 8)
        elif self.ball_x >= 240 - self.ball_size - 4:
            self.ball_x = 240 - self.ball_size - 4
            self.ball_dx = -abs(self.ball_dx)
            self.beep(600, 8)

        # Потолок
        if self.ball_y <= 30:
            self.ball_y = 30
            self.ball_dy = abs(self.ball_dy)
            self.beep(600, 8)

        # Отскок от ракетки
        if (self.pad_y <= self.ball_y + self.ball_size <= self.pad_y + self.pad_h + 4) and \
           (self.pad_x - 3 <= self.ball_x <= self.pad_x + self.pad_w + 3):
            self.ball_dy = -abs(self.ball_dy)
            self.ball_y = self.pad_y - self.ball_size - 1

            # Рикошет
            hit_offset = (self.ball_x + self.ball_size // 2) - (self.pad_x + self.pad_w // 2)
            step = self.physics_profiles[self.speed_lvl]["step"]
            if hit_offset < -10:   self.ball_dx = -int(step * 1.3)
            elif hit_offset > 10:  self.ball_dx = int(step * 1.3)
            else:                  self.ball_dx = step if self.ball_dx > 0 else -step

            self.beep(950, 12)

        # Кирпичи
        for r in range(self.rows):
            for c in range(self.cols):
                if self.bricks[r][c] == 1:
                    bx = 8 + c * (self.brick_w + 2)
                    by = self.brick_y_start + r * (self.brick_h + 3)

                    if (bx <= self.ball_x + self.ball_size and self.ball_x <= bx + self.brick_w) and \
                       (by <= self.ball_y + self.ball_size and self.ball_y <= by + self.brick_h):
                        self.bricks[r][c] = 0
                        self.ball_dy = -self.ball_dy
                        self.score += (5 - r) * 10
                        self.beep(1200 + (5 - r) * 150, 15)
                        return

        # Падение
        if self.ball_y > 315:
            self.lives -= 1
            self.beep(300, 100)
            if self.lives <= 0:
                self.game_over = True
            else:
                self.reset_ball()

    def run(self):
        while not self.game_over and not self.game_won:
            prof = self.physics_profiles[self.speed_lvl]

            # Опрос клавиш
            ev = self.inputs.get_event()
            if ev:
                if ev == 'BACK':
                    self.beep(500, 20)
                    return
                elif ev == 'LEFT':
                    self.pad_x = max(6, self.pad_x - prof["pad_spd"])
                elif ev == 'RIGHT':
                    self.pad_x = min(240 - self.pad_w - 6, self.pad_x + prof["pad_spd"])
                elif ev == 'UP':
                    # УСКОРЕНИЕ МЯЧА
                    if self.speed_lvl < len(self.physics_profiles) - 1:
                        self.speed_lvl += 1
                        self.apply_speed_to_ball()
                        self.beep(1600, 15)
                elif ev == 'DOWN':
                    # ЗАМЕДЛЕНИЕ МЯЧА
                    if self.speed_lvl > 0:
                        self.speed_lvl -= 1
                        self.apply_speed_to_ball()
                        self.beep(650, 15)
                elif ev == 'ENTER' and self.ball_attached:
                    self.ball_attached = False
                    step = prof["step"]
                    self.ball_dx = random.choice([-step, step])
                    self.ball_dy = -step
                    self.beep(1200, 20)

            # Выполняем нужное количество шагов физики за кадр (substeps)
            for _ in range(prof["substeps"]):
                self.step_physics()
                if self.ball_attached or self.game_over or self.game_won:
                    break

            self.draw_screen()
            time.sleep_ms(15)

        # Экран финала
        self.tft.fill_rect(20, 120, 200, 70, C_BORDER)
        self.tft.rect(20, 120, 200, 70, C_WHITE)
        if self.game_won:
            self.tft.text("VICTORY! YOU WIN!", 35, 140, st7789.ST7789.color565(0, 255, 100))
        else:
            self.tft.text("GAME OVER!", 75, 140, st7789.ST7789.color565(255, 60, 60))

        self.tft.text(f"FINAL SCORE: {self.score}", 45, 162, C_WHITE)
        self.tft.show()

        time.sleep(1.5)
        while True:
            ev = self.inputs.get_event()
            if ev in ['BACK', 'ENTER']:
                break
            time.sleep_ms(30)