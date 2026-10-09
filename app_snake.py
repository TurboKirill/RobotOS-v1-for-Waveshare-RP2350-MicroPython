# app_snake.py - Неоновая Змейка (Cyber-Snake) для RobotOS
import time
import math
import struct
import random
import st7789

# Цвета игры
C_BG       = 0x0000                                 # Глубокий черный
C_BORDER   = st7789.ST7789.color565(30, 45, 80)     # Рамка поля
C_HEAD     = st7789.ST7789.color565(255, 255, 255)  # Белая голова с акцентом
C_BODY     = st7789.ST7789.color565(0, 240, 100)    # Неоново-зеленое тело
C_FOOD     = st7789.ST7789.color565(255, 30, 80)    # Красный кристалл
C_WHITE    = 0xFFFF
C_SCORE    = st7789.ST7789.color565(0, 220, 255)
C_BEST     = st7789.ST7789.color565(255, 230, 0)

class SnakeApp:
    def __init__(self, tft, audio, inputs, config=None):
        self.tft = tft
        self.audio = audio
        self.inputs = inputs
        self.cfg = config if config else {"vol_ui": 30, "mute": False}

        # Игровое поле: сетка 22 x 26 клеток по 10 пикселей
        self.cell_size = 10
        self.grid_w = 22
        self.grid_h = 26
        self.offset_x = 10
        self.offset_y = 34

        self.best_score = 0
        self.reset_game()

    def reset_game(self):
        # Начальная змейка из 3 звеньев в центре поля
        self.snake = [(11, 13), (10, 13), (9, 13)]
        self.dir = 'RIGHT'
        self.next_dir = 'RIGHT'
        self.score = 0
        self.game_over = False
        self.speed_ms = 130 # Начальная задержка между шагами
        self.spawn_food()

    def spawn_food(self):
        """Создание еды в свободной клетке"""
        while True:
            fx = random.randint(0, self.grid_w - 1)
            fy = random.randint(0, self.grid_h - 1)
            if (fx, fy) not in self.snake:
                self.food = (fx, fy)
                break

    def beep(self, freq=1200, ms=20):
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

    def chirp_eat(self):
        """Победный аркадный перелив при съедании кристалла"""
        self.beep(1200, 15)
        self.beep(1700, 25)

    def draw_screen(self):
        self.tft.fill(C_BG)

        # Верхняя панель со счетом и рекордом
        self.tft.fill_rect(0, 0, 240, 28, C_BORDER)
        self.tft.text(f"SCORE:{self.score:03d}", 8, 10, C_SCORE)
        self.tft.text(f"BEST:{self.best_score:03d}", 155, 10, C_BEST)
        self.tft.line(0, 28, 240, 28, C_SCORE)

        # Рамка игрового поля
        bx = self.offset_x - 2
        by = self.offset_y - 2
        bw = self.grid_w * self.cell_size + 4
        bh = self.grid_h * self.cell_size + 4
        self.tft.rect(bx, by, bw, bh, C_BORDER)

        # Рисуем еду (кристалл с белой точкой внутри)
        fx = self.offset_x + self.food[0] * self.cell_size
        fy = self.offset_y + self.food[1] * self.cell_size
        self.tft.fill_rect(fx + 1, fy + 1, self.cell_size - 2, self.cell_size - 2, C_FOOD)
        self.tft.fill_rect(fx + 3, fy + 3, 4, 4, C_WHITE)

        # Рисуем змейку
        for i, (sx, sy) in enumerate(self.snake):
            px = self.offset_x + sx * self.cell_size
            py = self.offset_y + sy * self.cell_size
            if i == 0:
                # Голова
                self.tft.fill_rect(px, py, self.cell_size, self.cell_size, C_HEAD)
                # Глазки змейки
                self.tft.fill_rect(px + 2, py + 2, 2, 2, 0x0000)
                self.tft.fill_rect(px + 6, py + 2, 2, 2, 0x0000)
            else:
                # Тело (аккуратные звенья с зазором в 1 пиксель)
                self.tft.fill_rect(px + 1, py + 1, self.cell_size - 2, self.cell_size - 2, C_BODY)

        self.tft.show()

    def update_logic(self):
        # Блокировка движения в обратную сторону
        opposite = {'UP': 'DOWN', 'DOWN': 'UP', 'LEFT': 'RIGHT', 'RIGHT': 'LEFT'}
        if self.next_dir != opposite.get(self.dir):
            self.dir = self.next_dir

        hx, hy = self.snake[0]
        if self.dir == 'UP':    hy -= 1
        elif self.dir == 'DOWN':  hy += 1
        elif self.dir == 'LEFT':  hx -= 1
        elif self.dir == 'RIGHT': hx += 1

        # Проверка удара о стену
        if hx < 0 or hx >= self.grid_w or hy < 0 or hy >= self.grid_h:
            self.game_over = True
            return

        # Проверка удара о собственный хвост
        if (hx, hy) in self.snake:
            self.game_over = True
            return

        new_head = (hx, hy)
        self.snake.insert(0, new_head)

        # Проверка съедания еды
        if new_head == self.food:
            self.score += 10
            if self.score > self.best_score:
                self.best_score = self.score
            self.chirp_eat()
            self.spawn_food()
            # Плавный рост скорости (каждые 5 кристаллов)
            if self.speed_ms > 60:
                self.speed_ms -= 3
        else:
            # Если не съели еду — хвост удаляется
            self.snake.pop()

    def run(self):
        while True:
            self.reset_game()

            # Игровой цикл
            while not self.game_over:
                t_start = time.ticks_ms()

                # Непрерывный опрос клавиш во время шага (чтобы не было задержки отклика)
                while time.ticks_diff(time.ticks_ms(), t_start) < self.speed_ms:
                    ev = self.inputs.get_event()
                    if ev:
                        if ev == 'BACK':
                            self.beep(500, 20)
                            return
                        elif ev in ['UP', 'DOWN', 'LEFT', 'RIGHT']:
                            self.next_dir = ev
                    time.sleep_ms(10)

                self.update_logic()
                self.draw_screen()

            # Звук поражения
            self.beep(400, 80)
            self.beep(250, 160)

            # Экран GAME OVER
            self.tft.fill_rect(20, 120, 200, 80, C_BORDER)
            self.tft.rect(20, 120, 200, 80, C_WHITE)
            self.tft.text("GAME OVER!", 75, 138, st7789.ST7789.color565(255, 60, 60))
            self.tft.text(f"SCORE: {self.score}", 82, 158, C_WHITE)
            self.tft.text("[ENTER] Retry   [ESC] Exit", 26, 178, C_SCORE)
            self.tft.show()

            # Ждём перезапуска или выхода
            while True:
                ev = self.inputs.get_event()
                if ev == 'ENTER':
                    self.beep(1200, 20)
                    break
                elif ev == 'BACK':
                    self.beep(500, 20)
                    return
                time.sleep_ms(30)