import time
from machine import Pin, SPI, I2S
import st7789
import bios
import gui
import input_mgr

print("Запуск системы RobotOS...")

# 1. Экран (60 МГц)
spi = SPI(0, baudrate=60_000_000, polarity=1, phase=1, sck=Pin(18), mosi=Pin(19))
tft = st7789.ST7789(spi, width=240, height=320, dc=Pin(8), cs=Pin(20), rst=Pin(9), bl=Pin(21), rot=0)

# 2. Звук
audio = I2S(
    0,
    sck=Pin(10), ws=Pin(11), sd=Pin(12),
    mode=I2S.TX, bits=16, format=I2S.MONO,
    rate=22050, ibuf=1024
)

# === СНАЧАЛА ЗАПУСКАЕМ BIOS POST ===
boot = bios.BootLoader(tft, audio)
boot.run()

# === ЗАТЕМ ЧИСТО АКТИВИРУЕМ ВВОД (Клавиатура + ИК-Пульт) ===
# Это предотвращает сбой прерываний от SPI1
inputs = input_mgr.InputManager(kbd_clk=14, kbd_data=15, ir_pin=3)

# === ЗАПУСК ИНТЕРФЕЙСА ===
os_gui = gui.RobotOS_GUI(tft, audio, inputs)
os_gui.run()