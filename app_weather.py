# app_weather.py - Климат и погода: BH1750 (свет) + DHT22 (темп/влажность) + мини-глазки RobotOS
import time
import math
import struct
import dht
import st7789
from machine import Pin, I2C

# --- НАСТРОЙКА ПИНОВ ---
DHT_PIN = 13  # Пин данных DHT22 (DATA / OUT)

# Палитра
C_BG       = st7789.ST7789.color565(10, 16, 28)
C_CARD     = st7789.ST7789.color565(18, 28, 48)
C_HEADER   = st7789.ST7789.color565(0, 150, 220)
C_WHITE    = 0xFFFF
C_GRAY     = st7789.ST7789.color565(130, 145, 175)
C_COLD     = st7789.ST7789.color565(0, 220, 255)    # Ледяной синий
C_COMFORT  = st7789.ST7789.color565(0, 240, 255)    # Фирменный Cyan глазок
C_HOT      = st7789.ST7789.color565(255, 60, 60)    # Горячий красный
C_SUN      = st7789.ST7789.color565(255, 220, 0)    # Солнечный желтый

class WeatherApp:
    def __init__(self, tft, audio, inputs, config=None):
        self.tft = tft
        self.audio = audio
        self.inputs = inputs
        self.cfg = config if config else {"vol_ui": 30, "mute": False}

        # 1. Датчик света BH1750 по I2C (GP4 SDA, GP5 SCL)
        self.i2c = None
        self.has_bh1750 = False
        try:
            self.i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=100000)
            self.i2c.writeto(0x23, b'\x01') # Power ON
            self.i2c.writeto(0x23, b'\x10') # High-Res Mode
            self.has_bh1750 = True
        except:
            pass

        # 2. Датчик температуры и влажности DHT22
        self.dht_sensor = None
        self.has_dht = False
        self.last_dht_read = 0  # Метка времени для интервала в 2 сек
        try:
            self.dht_sensor = dht.DHT22(Pin(DHT_PIN))
            self.has_dht = True
        except:
            pass

        # Базовые значения климата
        self.temp = 23.5
        self.humidity = 45.0

    def read_lux(self):
        """Реальный замер Люксов с датчика BH1750"""
        if self.has_bh1750:
            try:
                data = self.i2c.readfrom(0x23, 2)
                return int((data[0] << 8 | data[1]) / 1.2)
            except:
                pass
        return 280

    def read_dht(self):
        """Неблокирующий опрос датчика DHT22 (не чаще 1 раза в 2 секунды)"""
        if not self.has_dht:
            return
        
        now = time.ticks_ms()
        # Проверяем, прошло ли 2000 мс с последнего опроса
        if time.ticks_diff(now, self.last_dht_read) >= 2000:
            self.last_dht_read = now
            try:
                self.dht_sensor.measure()
                self.temp = self.dht_sensor.temperature()
                self.humidity = self.dht_sensor.humidity()
            except Exception:
                # Одиночные сбои опроса у 1-Wire датчиков — норма, 
                # просто оставляем старое значение и не роняем ОС
                pass

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

    def draw_round_rect(self, x, y, w, h, r, color):
        """Фирменное скругление углов глаз"""
        if r <= 0 or h <= 2 * r or w <= 2 * r:
            self.tft.fill_rect(x, y, w, h, color)
            return
        self.tft.fill_rect(x, y + r, w, h - 2 * r, color)
        for dy in range(r):
            y_dist = r - dy
            dx = int(math.sqrt(r * r - y_dist * y_dist))
            self.tft.fill_rect(x + r - dx, y + dy, w - 2 * r + 2 * dx, 1, color)
            self.tft.fill_rect(x + r - dx, y + h - 1 - dy, w - 2 * r + 2 * dx, 1, color)

    def draw_mini_eyes(self, temp, state, frame):
        """Отрисовка настоящих скругленных глаз робота по погоде"""
        cx, cy = 120, 225
        card_w, card_h = 224, 78

        # Подложка карточки
        self.tft.fill_rect(8, cy - card_h//2, card_w, card_h, C_CARD)

        # Координаты пары мини-глаз
        ew, eh = 44, 52
        space = 16
        lx = cx - ew//2 - space//2
        rx = cx + ew//2 + space//2

        # 1. ХОЛОДНО (Синие глаза, дрожат от холода)
        if state == "COLD":
            shiver = (frame % 2) * 2 - 1
            col = C_COLD
            self.tft.rect(8, cy - card_h//2, card_w, card_h, col)
            self.draw_round_rect(lx - ew//2 + shiver, cy - eh//2, ew, eh, 10, col)
            self.draw_round_rect(rx - ew//2 + shiver, cy - eh//2, ew, eh, 10, col)
            self.tft.text("BRRR! FREEZING!", 62, cy + 24, col)

        # 2. ЖАРКО (Красные прищуренные глаза)
        elif state == "HOT":
            col = C_HOT
            self.tft.rect(8, cy - card_h//2, card_w, card_h, col)
            self.draw_round_rect(lx - ew//2, cy - 9, ew, 18, 5, col)
            self.draw_round_rect(rx - ew//2, cy - 9, ew, 18, 5, col)
            self.tft.text("SO HOT! MELTING...", 50, cy + 24, col)

        # 3. КОМФОРТ (Счастливые глазки-улыбки)
        else:
            col = C_COMFORT
            self.tft.rect(8, cy - card_h//2, card_w, card_h, col)
            self.draw_round_rect(lx - ew//2, cy - eh//2, ew, eh, 10, col)
            self.draw_round_rect(rx - ew//2, cy - eh//2, ew, eh, 10, col)
            self.tft.fill_rect(lx - ew//2, cy + 4, ew, 24, C_CARD)
            self.tft.fill_rect(rx - ew//2, cy + 4, ew, 24, C_CARD)
            self.tft.text("NICE & COMFORTABLE!", 45, cy + 24, col)

    def run(self):
        frame = 0

        while True:
            # Опрос датчиков
            lux = self.read_lux()
            self.read_dht()

            # Статус климата
            if self.temp < 18.0:
                state = "COLD"
                status_txt = "STATUS: TOO COLD"
                status_col = C_COLD
            elif self.temp > 25.0:
                state = "HOT"
                status_txt = "STATUS: TOO HOT"
                status_col = C_HOT
            else:
                state = "COMFORT"
                status_txt = "STATUS: COMFORTABLE"
                status_col = C_COMFORT

            # Освещение
            if lux < 30:     l_txt, l_icon = "NIGHT / DARK", "[ MOON ]"
            elif lux < 200:  l_txt, l_icon = "ROOM LIGHT",   "[ LAMP ]"
            elif lux < 800:  l_txt, l_icon = "DAYLIGHT",     "[ SUN ]"
            else:            l_txt, l_icon = "BRIGHT SUN",   "[ SUN+ ]"

            # Отрисовка экрана
            self.tft.fill(C_BG)

            # Шапка
            self.tft.fill_rect(0, 0, 240, 32, C_HEADER)
            self.tft.text("WEATHER & CLIMATE", 12, 10, C_WHITE)
            self.tft.text(f"{self.cfg.get('hour',12):02d}:{self.cfg.get('minute',45):02d}", 192, 10, C_WHITE)

            # Карточка 1: Температура и Влажность с DHT22
            self.tft.fill_rect(8, 38, 224, 56, C_CARD)
            self.tft.rect(8, 38, 224, 56, status_col)
            # Выводим Температуру и добавленную Влажность:
            self.tft.text(f"T:{self.temp:+.1f}C  HUM:{self.humidity:.0f}%", 20, 48, C_WHITE)
            self.tft.text(status_txt, 20, 70, status_col)

            # Карточка 2: Датчик света BH1750 (Люксы)
            self.tft.fill_rect(8, 100, 224, 60, C_CARD)
            self.tft.rect(8, 100, 224, 60, C_SUN)
            self.tft.text(f"LIGHT: {lux} LUX", 20, 110, C_WHITE)
            self.tft.text(f"{l_icon} {l_txt}", 20, 126, C_SUN)
            
            # Шкала люксов
            self.tft.rect(20, 144, 200, 7, C_GRAY)
            fill_w = min(196, int(196 * (lux / 1000.0)))
            if fill_w > 0:
                self.tft.fill_rect(22, 146, fill_w, 3, C_SUN)

            # Карточка 3: Настоящие круглые мини-глазки RobotOS!
            self.draw_mini_eyes(self.temp, state, frame)

            # Подвал
            self.tft.line(0, 276, 240, 276, C_GRAY)
            if self.has_dht:
                self.tft.text("Sensor: DHT22 Active", 10, 286, C_GRAY)
            else:
                self.tft.text("UP/DN: Sim Temp", 10, 286, C_GRAY)
            self.tft.text("ENTER: Beep   ESC: Exit", 10, 302, 0x07FF)
            self.tft.show()

            # Быстрый опрос клавиатуры
            for _ in range(10):
                ev = self.inputs.get_event()
                if ev:
                    if ev in ['BACK', 'ESC']:
                        self.beep(600, 30)
                        return
                    # Стрелки меняют температуру вручную, ТОЛЬКО если датчик не подключен
                    elif ev == 'UP' and not self.has_dht:
                        self.temp = min(38.0, round(self.temp + 1.0, 1))
                        self.beep(1200, 10); break
                    elif ev == 'DOWN' and not self.has_dht:
                        self.temp = max(10.0, round(self.temp - 1.0, 1))
                        self.beep(800, 10); break
                    elif ev == 'ENTER':
                        self.beep(1500, 20)
                time.sleep_ms(30)

            frame += 1