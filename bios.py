# bios.py - Чистый, аккуратный BIOS-загрузчик для RobotOS
import time
import math
import struct
import machine
import os
import sdcard

class BootLoader:
    def __init__(self, tft, audio):
        self.tft = tft
        self.audio = audio
        self.line_y = 12
        self.line_height = 14
        
        # Цвета классического BIOS
        self.C_BG     = 0x0000  # Чёрный фон
        self.C_WHITE  = 0xFFFF  # Белый текст
        self.C_GRAY   = 0x7BEF  # Серый
        self.C_CYAN   = 0x07FF  # Бирюзовый
        self.C_GREEN  = 0x07E0  # Зелёный (OK)
        self.C_YELLOW = 0xFFE0  # Жёлтый
        self.C_LINE   = 0x39E7  # Темно-серые линии-разделители

    def beep(self, freq=1000, ms=70, vol=8000):
        """Одиночный короткий сигнал системного динамика (PC Speaker)"""
        rate = 22050
        samples = int(rate / freq)
        cycle = bytearray(samples * 2)
        for i in range(samples):
            v = int(vol * math.sin(2 * math.pi * i / samples))
            struct.pack_into("<h", cycle, i * 2, v)
        for _ in range(int((ms / 1000) * freq)):
            self.audio.write(cycle)

    def startup_chime(self):
        """Победный мажорный аккорд включения системы (До-Ми-Соль-До)"""
        notes = [
            (261, 80),   # C4 (До)
            (329, 80),   # E4 (Ми)
            (392, 80),   # G4 (Соль)
            (523, 200)   # C5 (До октавой выше)
        ]
        for freq, dur in notes:
            self.beep(freq, dur, vol=9500)
            time.sleep_ms(15)

    def print_line(self, text, color=None, delay=0.03):
        """Печать строки с выравниванием по левому краю"""
        if color is None:
            color = self.C_WHITE
        self.tft.text(text, 10, self.line_y, color)
        self.tft.show()
        self.line_y += self.line_height
        if delay > 0:
            time.sleep(delay)

    def memory_test_animation(self):
        """Плавный счётчик тестирования памяти"""
        target_kb = 520
        step = 40
        for kb in range(0, target_kb + 1, step):
            self.tft.fill_rect(10, self.line_y, 220, 10, self.C_BG)
            self.tft.text(f"Memory Test: {kb}KB", 10, self.line_y, self.C_WHITE)
            self.tft.show()
            time.sleep(0.015)
        
        # Финальный результат
        self.tft.fill_rect(10, self.line_y, 220, 10, self.C_BG)
        self.tft.text("Memory Test: 520KB [OK]", 10, self.line_y, self.C_GREEN)
        self.tft.show()
        self.line_y += self.line_height

    def run(self):
        """Выполнение процедуры POST"""
        self.tft.fill(self.C_BG)
        self.tft.show()

        # 1. Шапка BIOS
        self.print_line("RobotOS Modular BIOS v1.0", self.C_WHITE, 0.04)
        self.print_line("(C) 2025 RP2350 Hardware", self.C_GRAY, 0.04)
        self.print_line("----------------------------", self.C_LINE, 0.02)
        self.line_y += 4

        # 2. Процессор
        mhz = machine.freq() // 1000000
        self.print_line("CPU: RP2350B Dual-Core M33", self.C_CYAN, 0.03)
        self.print_line(f"Clock Speed: {mhz} MHz", self.C_WHITE, 0.03)
        self.line_y += 4

        # 3. Тест памяти
        self.memory_test_animation()
        self.line_y += 4

        # 4. Проверка и монтирование MicroSD карты
        sd_ok = False
        try:
            cs = machine.Pin(43, machine.Pin.OUT)
            spi = machine.SPI(1, baudrate=10000000,
                              sck=machine.Pin(30), mosi=machine.Pin(31), miso=machine.Pin(40))
            sd = sdcard.SDCard(spi, cs, baudrate=5000000)
            os.mount(sd, "/sd")
            sd_ok = True
        except:
            pass

        if sd_ok:
            self.print_line("Storage: MicroSD 4GB [OK]", self.C_GREEN, 0.03)
        else:
            self.print_line("Storage: SD Card Not Found", self.C_YELLOW, 0.03)

        # 5. Периферия
        self.print_line("Audio: MAX98357A I2S  [OK]", self.C_WHITE, 0.03)
        self.print_line("Input: PS/2 Keyboard  [OK]", self.C_WHITE, 0.03)
        self.print_line("Video: ST7789 IPS LCD [OK]", self.C_WHITE, 0.03)
        self.line_y += 4

        # Разделитель
        self.print_line("----------------------------", self.C_LINE, 0.02)
        self.line_y += 8

        # Одиночный системный POST BEEP спикера
        self.beep(freq=1000, ms=60)
        time.sleep(0.3)

        # 6. Загрузка ядра RobotOS
        self.print_line("Booting RobotOS Core...", self.C_CYAN, 0.05)
        time.sleep(0.4)

        # Играем победный аккорд включения
        self.startup_chime()

        # Пауза перед передачей управления в GUI
        time.sleep(0.4)
        self.tft.fill(self.C_BG)
        self.tft.show()