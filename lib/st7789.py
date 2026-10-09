# st7789.py - Драйвер ST7789 240x320 для MicroPython
import time
from machine import Pin, SPI
import framebuf

# Команды ST7789
_SWRESET = 0x01
_SLPOUT  = 0x11
_COLMOD  = 0x3A
_MADCTL  = 0x36
_CASET   = 0x2A
_RASET   = 0x2B
_RAMWR   = 0x2C
_INVON   = 0x21
_INVOFF  = 0x20
_DISPON  = 0x29

class ST7789(framebuf.FrameBuffer):
    def __init__(self, spi, width=240, height=320, dc=None, cs=None, rst=None, bl=None, rot=0):
        self.spi = spi
        self.width = width
        self.height = height
        self.dc = dc
        self.cs = cs
        self.rst = rst
        self.bl = bl
        
        self.dc.init(Pin.OUT, value=0)
        if self.cs:
            self.cs.init(Pin.OUT, value=1)
        if self.rst:
            self.rst.init(Pin.OUT, value=1)
        if self.bl:
            self.bl.init(Pin.OUT, value=1)

        # Выделяем буфер кадра в формате RGB565 (2 байта на пиксель)
        self.buffer = bytearray(self.width * self.height * 2)
        super().__init__(self.buffer, self.width, self.height, framebuf.RGB565)

        self.reset()
        self.init_display(rot)

    def write_cmd(self, cmd):
        self.dc.value(0)
        if self.cs: self.cs.value(0)
        self.spi.write(bytearray([cmd]))
        if self.cs: self.cs.value(1)

    def write_data(self, data):
        self.dc.value(1)
        if self.cs: self.cs.value(0)
        self.spi.write(data)
        if self.cs: self.cs.value(1)

    def reset(self):
        if self.rst:
            self.rst.value(0)
            time.sleep_ms(50)
            self.rst.value(1)
            time.sleep_ms(50)

    def init_display(self, rot):
        self.write_cmd(_SWRESET)
        time.sleep_ms(150)
        self.write_cmd(_SLPOUT)
        time.sleep_ms(120)

        # 16-bit цвет (RGB565)
        self.write_cmd(_COLMOD)
        self.write_data(bytearray([0x55]))

        # Ориентация экрана (MADCTL)
        # 0: портрет, 1: альбом, 2: инверсный портрет, 3: инверсный альбом
        rotations = [0x00, 0x60, 0xC0, 0xA0]
        self.write_cmd(_MADCTL)
        self.write_data(bytearray([rotations[rot % 4]]))

        # Включение инверсии (для IPS матриц обычно нужно INVON)
        self.write_cmd(_INVON)
        
        self.write_cmd(_DISPON)
        time.sleep_ms(20)

    def set_window(self, x0, y0, x1, y1):
        self.write_cmd(_CASET)
        self.write_data(bytearray([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF]))
        self.write_cmd(_RASET)
        self.write_data(bytearray([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF]))
        self.write_cmd(_RAMWR)

    def show(self):
        self.set_window(0, 0, self.width - 1, self.height - 1)
        self.dc.value(1)
        if self.cs: self.cs.value(0)
        # Отправляем буфер целиком по SPI
        self.spi.write(self.buffer)
        if self.cs: self.cs.value(1)

    # Вспомогательный конвертер цветов из RGB888 в формат RGB565 для FrameBuffer
    @staticmethod
    def color565(r, g, b):
        c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        # Swap bytes for FrameBuffer
        return ((c & 0xFF) << 8) | ((c >> 8) & 0xFF)