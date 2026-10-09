# app_doom.py - DOOM-LITE: 3D-шутер на лучевом кастинге для RobotOS (ST7789 240x320)
# Управление ПУЛЬТОМ (шаговое, одно событие на нажатие):
#   UP/DOWN - вперёд/назад, LEFT/RIGHT - поворот 15 град, ENTER - выстрел, BACK(*) - пауза
# Управление КЛАВИАТУРОЙ: W/S, A/D (поворот), Q/E (боковые шаги), пробел - выстрел, ESC - пауза
import time
import math
import struct
import random
import st7789


def rgb(r, g, b):
    return st7789.ST7789.color565(r, g, b)


# ---------------------------------------------------------------- геометрия экрана
VW = 240                 # ширина 3D-вида
VH = 224                 # высота 3D-вида (ниже - панель HUD)
COLS = 60                # число лучей
CW = VW // COLS          # ширина колонки (4 px)
HALF = VH // 2
TICK = 200               # шаг ИИ врагов, мс
TURN = 0.2618            # 15 градусов
FOVK = 0.66              # длина вектора плоскости камеры (~66 градусов)

# ---------------------------------------------------------------- палитра
C_CEIL1 = rgb(14, 14, 24)
C_CEIL2 = rgb(30, 30, 48)
C_FLR1 = rgb(34, 28, 26)
C_FLR2 = rgb(58, 48, 42)
C_HUD = rgb(18, 18, 26)
C_LINE = rgb(90, 20, 20)
C_WHITE = 0xFFFF
C_GRAY = rgb(130, 135, 150)
C_RED = rgb(230, 40, 40)
C_GREEN = rgb(0, 230, 118)
C_YEL = rgb(255, 220, 0)
C_CYAN = rgb(0, 240, 255)

WALL_BASE = {1: (120, 130, 170), 2: (170, 92, 62), 3: (30, 225, 110)}

# ---------------------------------------------------------------- спрайты
# (масштаб высоты, отношение ширина/высота, [(u0,u1,v0,v1,(r,g,b)), ...]) - рисуются по порядку
SPRITES = {
    "imp": (0.85, 0.8, [
        ((0.25), 0.45, 0.85, 1.0, (70, 35, 20)), (0.55, 0.75, 0.85, 1.0, (70, 35, 20)),
        (0.05, 0.22, 0.38, 0.72, (150, 70, 40)), (0.78, 0.95, 0.38, 0.72, (150, 70, 40)),
        (0.2, 0.8, 0.35, 0.88, (160, 78, 44)),
        (0.3, 0.7, 0.05, 0.38, (185, 95, 55)),
        (0.27, 0.36, 0.0, 0.1, (235, 225, 200)), (0.64, 0.73, 0.0, 0.1, (235, 225, 200)),
        (0.37, 0.47, 0.15, 0.23, (255, 230, 0)), (0.53, 0.63, 0.15, 0.23, (255, 230, 0)),
    ]),
    "demon": (0.75, 0.95, [
        (0.2, 0.4, 0.8, 1.0, (110, 30, 70)), (0.6, 0.8, 0.8, 1.0, (110, 30, 70)),
        (0.02, 0.2, 0.4, 0.75, (200, 80, 130)), (0.8, 0.98, 0.4, 0.75, (200, 80, 130)),
        (0.12, 0.88, 0.3, 0.85, (205, 85, 135)),
        (0.2, 0.8, 0.0, 0.4, (225, 105, 150)),
        (0.15, 0.3, 0.3, 0.45, (240, 235, 220)), (0.7, 0.85, 0.3, 0.45, (240, 235, 220)),
        (0.3, 0.42, 0.12, 0.2, (255, 40, 40)), (0.58, 0.7, 0.12, 0.2, (255, 40, 40)),
        (0.3, 0.7, 0.26, 0.34, (60, 0, 10)),
    ]),
    "ammo": (0.28, 1.2, [
        (0.1, 0.9, 0.2, 1.0, (200, 170, 40)), (0.1, 0.9, 0.45, 0.6, (90, 70, 10)),
    ]),
    "health": (0.3, 1.0, [
        (0.05, 0.95, 0.05, 1.0, (235, 235, 235)),
        (0.4, 0.6, 0.15, 0.9, (220, 30, 30)), (0.18, 0.82, 0.42, 0.62, (220, 30, 30)),
    ]),
    "corpse": (0.2, 1.6, [
        (0.05, 0.95, 0.35, 1.0, (110, 18, 18)), (0.3, 0.7, 0.0, 0.55, (150, 28, 28)),
    ]),
}

# ---------------------------------------------------------------- уровни
# # стена, % стена 2, X выход, P старт, M имп, D демон, a патроны, h аптечка
LEVELS = [
    [
        "################",
        "#P.....#.......#",
        "#......#...M...#",
        "#..##..#.......#",
        "#..##....###...#",
        "#......#.#a#...#",
        "####.###.#.#####",
        "#......#.#.....#",
        "#..M...#.#..h..#",
        "#......#.####.##",
        "#......#.......#",
        "###.##########.#",
        "#a..#.....M....#",
        "#...#..........#",
        "#.........##..X#",
        "################",
    ],
    [
        "################",
        "#P.#...........#",
        "#..#.%%%%%%%%%.#",
        "#..#.%.....M.%.#",
        "#....%.%%%%%.%.#",
        "####.%.%a..%.%.#",
        "#M...%.%.D.%...#",
        "#.####.%.%%%%.##",
        "#......%.......#",
        "#.######.#####.#",
        "#.#h...#.#.M..##",
        "#.#.##.#.#.#.###",
        "#.#.#M...#.#...#",
        "#.#.#.####.##..#",
        "#...#a.....D..X#",
        "################",
    ],
]


class DoomApp:
    def __init__(self, tft, audio, inputs, config=None):
        self.tft = tft
        self.audio = audio
        self.inputs = inputs
        self.cfg = config if config is not None else {"vol_ui": 30, "mute": False}

        self.zb = [0.0] * COLS
        self._wave = {}
        self._noise = None

        # таблицы цветов стен: [тип][сторона][оттенок 0..7]
        self.wcol = {}
        for wt, base in WALL_BASE.items():
            sides = []
            for side in (0, 1):
                k = 1.0 if side == 0 else 0.68
                row = []
                for s in range(8):
                    f = max(0.10, 1.0 - s / 7.0 * 0.9) * k
                    row.append(rgb(int(base[0] * f), int(base[1] * f), int(base[2] * f)))
                sides.append(row)
            self.wcol[wt] = sides

        self.level = 0
        self.score = 0
        self.hp = 100
        self.ammo = 30
        self.load_level(0)

    # ================================================================ звук
    def _wave_for(self, freq):
        amp = int(1200 * (self.cfg.get("vol_ui", 30) / 100))
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

    def beep(self, freq=900, ms=15):
        if self.cfg.get("mute") or self.cfg.get("vol_ui", 30) == 0:
            return
        cycle = self._wave_for(freq)
        for _ in range(max(1, int((ms / 1000) * freq))):
            self.audio.write(cycle)

    def noise(self, ms=40):
        """Звук выстрела - короткий шумовой всплеск."""
        if self.cfg.get("mute") or self.cfg.get("vol_ui", 30) == 0:
            return
        amp = int(2500 * (self.cfg.get("vol_ui", 30) / 100))
        if self._noise is None or self._noise[1] != amp:
            b = bytearray(512)
            for i in range(256):
                struct.pack_into("<h", b, i * 2, random.randint(-amp, amp))
            self._noise = (b, amp)
        for _ in range(max(1, int(ms * 22.05 / 256))):
            self.audio.write(self._noise[0])

    # ================================================================ уровень
    def load_level(self, n):
        rows = LEVELS[n]
        self.grid = []
        self.enemies = []
        self.items = []
        self.runs = []                       # для миникарты: [(x0, длина, тип)] по строкам
        for y, row in enumerate(rows):
            grow = []
            runs = []
            for x, ch in enumerate(row):
                v = 0
                if ch == "#":
                    v = 1
                elif ch == "%":
                    v = 2
                elif ch == "X":
                    v = 3
                elif ch == "P":
                    self.px, self.py = x + 0.5, y + 0.5
                elif ch == "M":
                    self.enemies.append({"x": x + 0.5, "y": y + 0.5, "hp": 3, "k": "imp",
                                         "alert": False, "cd": 0, "pain": 0})
                elif ch == "D":
                    self.enemies.append({"x": x + 0.5, "y": y + 0.5, "hp": 5, "k": "demon",
                                         "alert": False, "cd": 0, "pain": 0})
                elif ch == "a":
                    self.items.append({"x": x + 0.5, "y": y + 0.5, "k": "ammo", "on": True})
                elif ch == "h":
                    self.items.append({"x": x + 0.5, "y": y + 0.5, "k": "health", "on": True})
                grow.append(v)
                if v:
                    if runs and runs[-1][0] + runs[-1][1] == x and runs[-1][2] == v:
                        runs[-1][1] += 1
                    else:
                        runs.append([x, 1, v])
            self.grid.append(grow)
            self.runs.append(runs)

        self.total = len(self.enemies)
        self.kills = 0
        self.pa = 0.0
        # смотрим туда, где дальше всего до стены
        best = -1
        for k in range(4):
            a = k * math.pi / 2
            d = self.cast(self.px, self.py, math.cos(a), math.sin(a))[0]
            if d > best:
                best = d
                self.pa = a

        self.next_fire = 0
        self.flash_until = 0
        self.hurt_until = 0
        self.exit_hit = False
        self.state = "play"
        self.dirty = True
        self.hud_key = None

    # ================================================================ геометрия
    def cast(self, ox, oy, rdx, rdy):
        """DDA. Возвращает (расстояние, сторона, тип стены, доля вдоль грани)."""
        g = self.grid
        mx = int(ox)
        my = int(oy)
        ddx = abs(1.0 / rdx) if rdx else 1e9
        ddy = abs(1.0 / rdy) if rdy else 1e9
        if rdx < 0:
            sx = -1
            sdx = (ox - mx) * ddx
        else:
            sx = 1
            sdx = (mx + 1.0 - ox) * ddx
        if rdy < 0:
            sy = -1
            sdy = (oy - my) * ddy
        else:
            sy = 1
            sdy = (my + 1.0 - oy) * ddy
        side = 0
        while True:
            if sdx < sdy:
                sdx += ddx
                mx += sx
                side = 0
            else:
                sdy += ddy
                my += sy
                side = 1
            w = g[my][mx]
            if w:
                break
        if side == 0:
            d = sdx - ddx
            f = oy + d * rdy
        else:
            d = sdy - ddy
            f = ox + d * rdx
        if d < 0.05:
            d = 0.05
        return d, side, w, f - int(f)

    def los(self, x0, y0, x1, y1):
        """Прямая видимость (проход по отрезку шагом 0.25)."""
        dx = x1 - x0
        dy = y1 - y0
        d = math.sqrt(dx * dx + dy * dy)
        n = int(d / 0.25)
        if n < 1:
            return True
        sx = dx / n
        sy = dy / n
        g = self.grid
        for i in range(1, n):
            if g[int(y0 + sy * i)][int(x0 + sx * i)]:
                return False
        return True

    def free(self, x, y, r):
        g = self.grid
        for cx in (x - r, x + r):
            for cy in (y - r, y + r):
                v = g[int(cy)][int(cx)]
                if v:
                    if v == 3:
                        self.exit_hit = True
                    return False
        return True

    def enemy_at(self, x, y, skip=None):
        for e in self.enemies:
            if e is skip or e["hp"] <= 0:
                continue
            dx = e["x"] - x
            dy = e["y"] - y
            if dx * dx + dy * dy < 0.36:
                return True
        return False

    # ================================================================ действия игрока
    def move(self, mx, my):
        nx = self.px + mx
        if self.free(nx, self.py, 0.22) and not self.enemy_at(nx, self.py):
            self.px = nx
        ny = self.py + my
        if self.free(self.px, ny, 0.22) and not self.enemy_at(self.px, ny):
            self.py = ny
        # подбор предметов
        for it in self.items:
            if not it["on"]:
                continue
            dx = it["x"] - self.px
            dy = it["y"] - self.py
            if dx * dx + dy * dy < 0.3:
                if it["k"] == "ammo":
                    self.ammo = min(99, self.ammo + 12)
                    it["on"] = False
                    self.beep(1500, 20)
                elif it["k"] == "health" and self.hp < 100:
                    self.hp = min(100, self.hp + 25)
                    it["on"] = False
                    self.beep(1100, 20)
                    self.beep(1500, 20)

    def hurt(self, dmg, now):
        self.hp -= dmg
        self.hurt_until = now + 220
        self.dirty = True
        if self.hp <= 0:
            self.hp = 0
            self.state = "dead"

    def fire(self, now):
        if time.ticks_diff(now, self.next_fire) < 0:
            return
        if self.ammo <= 0:
            self.beep(300, 15)
            self.next_fire = time.ticks_add(now, 250)
            return
        self.ammo -= 1
        self.next_fire = time.ticks_add(now, 350)
        self.flash_until = time.ticks_add(now, 100)
        self.dirty = True

        dx = math.cos(self.pa)
        dy = math.sin(self.pa)
        best = None
        bd = 1e9
        for e in self.enemies:
            if e["hp"] <= 0:
                continue
            sx = e["x"] - self.px
            sy = e["y"] - self.py
            fwd = dx * sx + dy * sy
            lat = -dy * sx + dx * sy
            if fwd > 0.15 and abs(lat) < 0.32 and fwd < bd:
                if self.los(self.px, self.py, e["x"], e["y"]):
                    best = e
                    bd = fwd
        self.noise(35)
        if best is not None:
            best["alert"] = True
            best["pain"] = 2
            best["hp"] -= random.randint(1, 2)
            if best["hp"] <= 0:
                self.kills += 1
                self.score += 100 if best["k"] == "imp" else 200
                self.items.append({"x": best["x"], "y": best["y"], "k": "corpse", "on": True})
                self.beep(250, 40)

    # ================================================================ ИИ
    def ai_tick(self, now):
        for e in self.enemies:
            if e["hp"] <= 0:
                continue
            ex = e["x"]
            ey = e["y"]
            vx = self.px - ex
            vy = self.py - ey
            d = math.sqrt(vx * vx + vy * vy)
            seen = d < 11 and self.los(ex, ey, self.px, self.py)
            if not e["alert"]:
                if seen and d < 9:
                    e["alert"] = True
                    self.dirty = True
                continue
            self.dirty = True
            if d < 1.0:
                if time.ticks_diff(now, e["cd"]) >= 0:
                    e["cd"] = time.ticks_add(now, 900)
                    self.hurt(random.randint(8, 14) if e["k"] == "demon" else random.randint(4, 8), now)
                    self.beep(180, 25)
                continue
            if e["k"] == "imp" and seen and d > 2.0 and time.ticks_diff(now, e["cd"]) >= 0 \
                    and random.random() < 0.4:
                e["cd"] = time.ticks_add(now, 1300)
                if random.random() < 0.7:
                    self.hurt(random.randint(4, 9), now)
                self.beep(420, 25)
                continue
            sp = 0.34 if e["k"] == "demon" else 0.22
            ux = vx / d * sp
            uy = vy / d * sp
            moved = False
            nx = ex + ux
            if not self.grid[int(ey)][int(nx + (0.25 if ux > 0 else -0.25))] \
                    and not self.enemy_at(nx, ey, e):
                e["x"] = nx
                moved = True
            ny = e["y"] + uy
            if not self.grid[int(ny + (0.25 if uy > 0 else -0.25))][int(e["x"])] \
                    and not self.enemy_at(e["x"], ny, e):
                e["y"] = ny
                moved = True
            if not moved:       # упёрся - боковой шаг
                sx = -uy
                sy = ux
                if random.random() < 0.5:
                    sx = -sx
                    sy = -sy
                tx = e["x"] + sx
                ty = e["y"] + sy
                if not self.grid[int(ty)][int(tx)] and not self.enemy_at(tx, ty, e):
                    e["x"] = tx
                    e["y"] = ty

    # ================================================================ отрисовка
    def draw_sprites(self, dx, dy, plx, ply):
        t = self.tft
        lst = []
        for e in self.enemies:
            if e["hp"] > 0:
                lst.append((e["x"], e["y"], e["k"], e["pain"] > 0, e))
        for it in self.items:
            if it["on"]:
                lst.append((it["x"], it["y"], it["k"], False, it))
        if not lst:
            return
        det = plx * dy - dx * ply
        inv = 1.0 / det
        vis = []
        for s in lst:
            sx = s[0] - self.px
            sy = s[1] - self.py
            ty = inv * (-ply * sx + plx * sy)
            if ty > 0.2:
                tx = inv * (dy * sx - dx * sy)
                vis.append((ty, tx, s))
        vis.sort(key=lambda a: -a[0])

        zb = self.zb
        for ty, tx, s in vis:
            kind = s[2]
            scale, wr, rects = SPRITES[kind]
            scr = int(VW / 2 * (1 + tx / ty))
            size = VH / ty
            sh = int(size * scale)
            sw = int(sh * wr)
            if sh < 2 or sw < 2:
                continue
            left = scr - sw // 2
            if left >= VW or left + sw <= 0:
                continue
            top = HALF + int(size / 2) - sh
            f = max(0.2, min(1.0, 1.7 / (1.0 + ty * 0.35)))
            if s[3]:
                f = 1.6
            cr = []
            for r in rects:
                c = r[4]
                cr.append((r[0], r[1], r[2], r[3],
                           rgb(min(255, int(c[0] * f)), min(255, int(c[1] * f)), min(255, int(c[2] * f)))))
            c0 = max(0, left // CW)
            c1 = min(COLS - 1, (left + sw) // CW)
            for c in range(c0, c1 + 1):
                if zb[c] < ty:
                    continue
                u = (c * CW + CW // 2 - left) / sw
                if u < 0 or u >= 1:
                    continue
                for r in cr:
                    if r[0] <= u < r[1]:
                        y = top + int(r[2] * sh)
                        hh = max(1, int((r[3] - r[2]) * sh))
                        if y < 0:
                            hh += y
                            y = 0
                        if y + hh > VH:
                            hh = VH - y
                        if hh > 0:
                            t.fill_rect(c * CW, y, CW, hh, r[4])
            if s[3]:
                s[4]["pain"] -= 1

    def draw_weapon(self, now):
        t = self.tft
        firing = self.flash_until and time.ticks_diff(now, self.flash_until) < 0
        oy = 6 if firing else 0
        cx = VW // 2
        if firing:
            t.fill_rect(cx - 14, VH - 98, 28, 26, rgb(255, 150, 0))
            t.fill_rect(cx - 7, VH - 92, 14, 16, C_YEL)
            t.fill_rect(cx - 3, VH - 88, 6, 8, C_WHITE)
        t.fill_rect(cx - 6, VH - 72 + oy, 12, 38, rgb(95, 100, 112))
        t.fill_rect(cx - 3, VH - 72 + oy, 6, 38, rgb(150, 155, 168))
        t.fill_rect(cx - 12, VH - 36 + oy, 24, 36, rgb(60, 62, 72))
        t.fill_rect(cx - 9, VH - 33 + oy, 18, 30, rgb(82, 86, 98))
        # прицел
        t.fill_rect(cx - 1, HALF - 6, 2, 4, C_WHITE)
        t.fill_rect(cx - 1, HALF + 3, 2, 4, C_WHITE)
        t.fill_rect(cx - 7, HALF - 1, 4, 2, C_WHITE)
        t.fill_rect(cx + 4, HALF - 1, 4, 2, C_WHITE)

    def draw_face(self, x, y):
        t = self.tft
        skin = rgb(225, 175, 135)
        t.fill_rect(x, y, 32, 38, skin)
        t.fill_rect(x, y, 32, 8, rgb(85, 55, 30))
        t.fill_rect(x + 7, y + 15, 5, 5, 0x0000)
        t.fill_rect(x + 20, y + 15, 5, 5, 0x0000)
        if self.hp > 60:
            t.fill_rect(x + 9, y + 28, 14, 2, rgb(120, 40, 40))
            t.fill_rect(x + 8, y + 26, 2, 2, rgb(120, 40, 40))
            t.fill_rect(x + 22, y + 26, 2, 2, rgb(120, 40, 40))
        elif self.hp > 30:
            t.fill_rect(x + 9, y + 28, 14, 2, rgb(120, 40, 40))
            t.fill_rect(x + 4, y + 9, 10, 5, C_RED)
        else:
            t.fill_rect(x + 4, y + 9, 12, 6, C_RED)
            t.fill_rect(x + 20, y + 24, 8, 12, C_RED)
            t.fill_rect(x + 10, y + 27, 12, 6, rgb(90, 10, 10))

    def draw_hud(self, now):
        t = self.tft
        key = (self.hp, self.ammo, self.kills, self.level)
        if self.hud_key is None:
            t.fill_rect(0, VH, VW, 320 - VH, C_HUD)
            t.fill_rect(0, VH, VW, 2, C_LINE)
        if key != self.hud_key:
            self.hud_key = key
            t.fill_rect(0, VH + 2, 184, 94, C_HUD)
            hc = C_GREEN if self.hp > 50 else (C_YEL if self.hp > 25 else C_RED)
            t.text("HP %3d" % self.hp, 6, VH + 10, hc)
            t.rect(6, VH + 22, 102, 8, C_GRAY)
            t.fill_rect(7, VH + 23, self.hp, 6, hc)
            t.text("AMMO %2d" % self.ammo, 6, VH + 38, C_YEL if self.ammo > 5 else C_RED)
            t.text("KILL %d/%d" % (self.kills, self.total), 6, VH + 54, C_WHITE)
            t.text("LEVEL %d/%d" % (self.level + 1, len(LEVELS)), 6, VH + 70, C_CYAN)
            t.text("OK:FIRE  *:PAUSE", 6, VH + 84, C_GRAY)
            self.draw_face(124, VH + 14)

        # миникарта (перерисовывается каждый кадр)
        mx0 = 188
        my0 = VH + 8
        t.fill_rect(mx0 - 2, my0 - 2, 52, 52, rgb(6, 6, 10))
        for y, runs in enumerate(self.runs):
            for r in runs:
                t.fill_rect(mx0 + r[0] * 3, my0 + y * 3, r[1] * 3, 3,
                            rgb(70, 78, 105) if r[2] == 1 else (rgb(120, 70, 50) if r[2] == 2 else C_GREEN))
        for e in self.enemies:
            if e["hp"] > 0 and e["alert"]:
                t.fill_rect(mx0 + int(e["x"] * 3) - 1, my0 + int(e["y"] * 3) - 1, 3, 3, C_RED)
        pxx = mx0 + int(self.px * 3)
        pyy = my0 + int(self.py * 3)
        t.fill_rect(pxx - 1, pyy - 1, 3, 3, C_YEL)
        t.fill_rect(pxx + int(math.cos(self.pa) * 4), pyy + int(math.sin(self.pa) * 4), 1, 1, C_WHITE)

    def render(self, now):
        t = self.tft
        t.fill_rect(0, 0, VW, HALF // 2, C_CEIL1)
        t.fill_rect(0, HALF // 2, VW, HALF - HALF // 2, C_CEIL2)
        t.fill_rect(0, HALF, VW, (VH - HALF) // 2, C_FLR1)
        t.fill_rect(0, HALF + (VH - HALF) // 2, VW, VH - HALF - (VH - HALF) // 2, C_FLR2)

        dx = math.cos(self.pa)
        dy = math.sin(self.pa)
        plx = -dy * FOVK
        ply = dx * FOVK
        zb = self.zb
        px = self.px
        py = self.py
        cast = self.cast
        wcol = self.wcol
        for c in range(COLS):
            cam = 2.0 * (c + 0.5) / COLS - 1.0
            d, side, w, fr = cast(px, py, dx + plx * cam, dy + ply * cam)
            zb[c] = d
            h = int(VH / d)
            si = int(d * 0.55)
            if fr < 0.05 or fr > 0.95:
                si += 2
            if si > 7:
                si = 7
            if h >= VH:
                y0 = 0
                h = VH
            else:
                y0 = HALF - h // 2
            t.fill_rect(c * CW, y0, CW, h, wcol[w][side][si])

        self.draw_sprites(dx, dy, plx, ply)
        self.draw_weapon(now)

        if self.hurt_until and time.ticks_diff(now, self.hurt_until) < 0:
            t.fill_rect(0, 0, VW, 8, C_RED)
            t.fill_rect(0, VH - 8, VW, 8, C_RED)
            t.fill_rect(0, 0, 8, VH, C_RED)
            t.fill_rect(VW - 8, 0, 8, VH, C_RED)

        self.draw_hud(now)
        t.show()

    # ================================================================ экраны
    def overlay(self, lines, color):
        t = self.tft
        h = 20 + len(lines) * 18
        y = (VH - h) // 2
        t.fill_rect(20, y, 200, h, rgb(10, 10, 16))
        t.rect(20, y, 200, h, color)
        for i, (s, c) in enumerate(lines):
            t.text(s, 120 - len(s) * 4, y + 12 + i * 18, c)
        t.show()

    def wait_key(self, keys):
        while True:
            ev = self.inputs.get_event()
            if ev in keys:
                return ev
            time.sleep_ms(30)

    def pause(self):
        self.overlay([("PAUSED", C_YEL), ("OK: RESUME", C_WHITE), ("*: QUIT GAME", C_GRAY)], C_YEL)
        ev = self.wait_key(("ENTER", "BACK", "ESC", " "))
        self.hud_key = None
        self.dirty = True
        return ev in ("BACK", "ESC")

    def save_hiscore(self):
        if self.score > self.cfg.get("hiscore", 0):
            self.cfg["hiscore"] = self.score

    # ================================================================ главный цикл
    def handle(self, ev, now):
        dx = math.cos(self.pa)
        dy = math.sin(self.pa)
        if ev in ("UP", "w", "W"):
            self.move(dx * 0.45, dy * 0.45)
        elif ev in ("DOWN", "s", "S"):
            self.move(-dx * 0.35, -dy * 0.35)
        elif ev in ("LEFT", "a", "A"):
            self.pa = (self.pa - TURN) % (2 * math.pi)
        elif ev in ("RIGHT", "d", "D"):
            self.pa = (self.pa + TURN) % (2 * math.pi)
        elif ev in ("q", "Q"):
            self.move(dy * 0.35, -dx * 0.35)
        elif ev in ("e", "E"):
            self.move(-dy * 0.35, dx * 0.35)
        elif ev in ("ENTER", " "):
            self.fire(now)
        elif ev in ("BACK", "ESC"):
            return self.pause()
        else:
            return False
        self.dirty = True
        return False

    def run(self):
        self.level = 0
        self.score = 0
        self.hp = 100
        self.ammo = 30
        self.load_level(0)
        self.tft.fill(0x0000)
        last_tick = time.ticks_ms()

        while True:
            now = time.ticks_ms()

            n = 0
            while n < 6:
                ev = self.inputs.get_event()
                if not ev:
                    break
                n += 1
                if self.handle(ev, now):
                    self.save_hiscore()
                    return
                if self.exit_hit:
                    break

            if time.ticks_diff(now, last_tick) >= TICK:
                last_tick = now
                self.ai_tick(now)

            if self.flash_until and time.ticks_diff(now, self.flash_until) >= 0:
                self.flash_until = 0
                self.dirty = True
            if self.hurt_until and time.ticks_diff(now, self.hurt_until) >= 0:
                self.hurt_until = 0
                self.dirty = True

            if self.exit_hit and self.state == "play":
                self.state = "exit"

            if self.dirty or self.state != "play":
                self.dirty = False
                self.render(now)

            if self.state == "dead":
                self.save_hiscore()
                self.overlay([("YOU DIED", C_RED), ("SCORE %d" % self.score, C_WHITE),
                              ("OK / *: EXIT", C_GRAY)], C_RED)
                time.sleep_ms(600)
                self.wait_key(("ENTER", "BACK", "ESC", " "))
                return

            if self.state == "exit":
                self.score += 300 + self.kills * 50
                self.save_hiscore()
                last = self.level + 1 >= len(LEVELS)
                self.overlay([("LEVEL CLEAR!" if not last else "YOU WIN!", C_GREEN),
                              ("KILLS %d/%d" % (self.kills, self.total), C_WHITE),
                              ("SCORE %d" % self.score, C_YEL),
                              ("OK: NEXT" if not last else "OK: EXIT", C_GRAY)], C_GREEN)
                self.beep(900, 40)
                self.beep(1400, 60)
                time.sleep_ms(500)
                self.wait_key(("ENTER", "BACK", "ESC", " "))
                if last:
                    return
                self.level += 1
                self.hp = min(100, self.hp + 25)
                self.ammo = min(99, self.ammo + 15)
                self.load_level(self.level)
                self.tft.fill(0x0000)
                last_tick = time.ticks_ms()
                continue

            time.sleep_ms(8)
