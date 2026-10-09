# lib/ps2.py - Неблокирующий аппаратный PIO с авто-синхронизацией
import time
import rp2
from machine import Pin

@rp2.asm_pio(in_shiftdir=rp2.PIO.SHIFT_RIGHT)
def ps2_pio_rx():
    # 1. Ждем шину в покое (1) и спад в стартовый бит (0)
    wait(1, gpio, 14)
    wait(0, gpio, 14)
    wait(1, gpio, 14)

    # 2. Считываем 8 бит
    set(x, 7)
    label("bitloop")
    wait(0, gpio, 14)
    in_(pins, 1)
    wait(1, gpio, 14)
    jmp(x_dec, "bitloop")

    # 3. Пропускаем четность и стоп
    wait(0, gpio, 14); wait(1, gpio, 14)
    wait(0, gpio, 14); wait(1, gpio, 14)

    # 4. Неблокирующее выталкивание (никогда не зависает!)
    push(noblock)

class PS2Keyboard:
    EXT_MAP = {
        0x75: 'UP', 0x72: 'DOWN', 0x6B: 'LEFT', 0x74: 'RIGHT',
    }
    STD_MAP = {
        #Служебные
        0x5A: 'ENTER', 0x29: ' ', 0x76: 'ESC', 0x66: 'BACKSPACE', 0x0D: '  ',
        
        # Буквы (A-Z)
        0x1C: 'a', 0x32: 'b', 0x21: 'c', 0x23: 'd', 0x24: 'e', 0x2B: 'f', 0x34: 'g',
        0x33: 'h', 0x43: 'i', 0x3B: 'j', 0x42: 'k', 0x4B: 'l', 0x3A: 'm', 0x31: 'n',
        0x44: 'o', 0x4D: 'p', 0x15: 'q', 0x2D: 'r', 0x1B: 's', 0x2C: 't', 0x3C: 'u',
        0x2A: 'v', 0x1D: 'w', 0x22: 'x', 0x35: 'y', 0x1A: 'z',

        # Цифры (0-9)
        0x45: '0', 0x16: '1', 0x1E: '2', 0x26: '3', 0x25: '4', 
        0x2E: '5', 0x36: '6', 0x3D: '7', 0x3E: '8', 0x46: '9',

        # Знаки препинания и символы кода
        0x49: '.', 0x41: ',', 0x4E: '-', 0x55: '=', 0x4A: '/', 
        0x4C: ';', 0x52: "'", 0x54: '[', 0x5B: ']', 0x0E: '`',
    }

    def __init__(self, clk_pin=14, data_pin=15):
        self.clk = Pin(clk_pin, Pin.IN, Pin.PULL_UP)
        self.data = Pin(data_pin, Pin.IN, Pin.PULL_UP)

        self.sm = None
        for sm_id in [4, 5, 6, 7, 2, 3, 1]:
            try:
                self.sm = rp2.StateMachine(sm_id, ps2_pio_rx, in_base=self.data)
                break
            except ValueError:
                continue

        self.sm.active(1)
        self.buf = bytearray(128)
        self.head = 0
        self.tail = 0
        self.is_ext = False
        self.is_release = False
        self.last_press = time.ticks_ms()

    def get_key(self):
        # 1. Выгребаем всё из аппаратного буфера в софтовый
        while self.sm.rx_fifo() > 0:
            code = (self.sm.get() >> 24) & 0xFF
            nxt = (self.head + 1) % 128
            if nxt != self.tail:
                self.buf[self.head] = code
                self.head = nxt
            self.last_press = time.ticks_ms()

        # 2. Сторожевой таймер: если шина свободна > 60 мс, перезапускаем PIO на старт
        if self.clk.value() == 1 and time.ticks_diff(time.ticks_ms(), self.last_press) > 60:
            self.sm.restart()

        # 3. Декодируем байты
        while self.head != self.tail:
            code = self.buf[self.tail]
            self.tail = (self.tail + 1) % 128

            if code == 0xE0: self.is_ext = True; continue
            if code == 0xF0: self.is_release = True; continue

            if not self.is_release:
                key = self.EXT_MAP.get(code) if self.is_ext else self.STD_MAP.get(code)
                self.is_ext = False
                self.is_release = False
                if key:
                    return key
            else:
                self.is_release = False
                self.is_ext = False

        return None