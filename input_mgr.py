# input_mgr.py - Единый диспетчер: проверенный ps2.py + откалиброванный ИК-пульт
import time
from machine import Pin
from utime import ticks_us, ticks_diff
import ps2

# 1. ТОЧНАЯ ТАБЛИЦА ВАШЕГО ПУЛЬТА
IR_MAP = {
    0x31: 'UP',      # ВВЕРХ
    0xA5: 'DOWN',    # ВНИЗ
    0x11: 'LEFT',    # ВЛЕВО
    0xB5: 'RIGHT',   # ВПРАВО
    0x39: 'ENTER',   # ОК
    0x2D: 'BACK',    # * (Назад)
    0x1B: 'BACK',    # #
}

class InputManager:
    def __init__(self, kbd_clk=14, kbd_data=15, ir_pin=3):
        # 1. КЛАВИАТУРА — работает через наш проверенный ps2.py!
        self.kbd = ps2.PS2Keyboard(clk_pin=kbd_clk, data_pin=kbd_data)

        # 2. ИК-ПУЛЬТ — работает по вашим точным кодам
        self.ir_pin = Pin(ir_pin, Pin.IN, Pin.PULL_UP)
        self.ir_event = None
        self.ir_times = []
        self.ir_last_edge = ticks_us()
        self.ir_pin.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=self._ir_irq)

        print("🎮 Диспетчер готов: ps2.py + Пульт работают вместе!")

    def _ir_irq(self, pin):
        now = ticks_us()
        dt = ticks_diff(now, self.ir_last_edge)
        self.ir_last_edge = now

        if dt > 10000:
            if len(self.ir_times) >= 66:
                val = 0
                for i in range(1, 65, 2):
                    val >>= 1
                    if self.ir_times[i] > 1100:
                        val |= 0x80000000
                cmd = (val >> 16) & 0xFF
                
                # Команда с пульта
                action = IR_MAP.get(cmd)
                if action:
                    self.ir_event = action
            self.ir_times = []
        else:
            self.ir_times.append(dt)

    def get_event(self):
        # 1. Проверяем пульт
        if self.ir_event:
            ev = self.ir_event
            self.ir_event = None
            return ev

        # 2. Проверяем клавиатуру через ps2.py
        k = self.kbd.get_key()
        if k:
            # ТОЛЬКО ESC вызывает выход/назад!
            if k == 'ESC': 
                return 'BACK'
            # BACKSPACE отдаем как BACKSPACE для стирания букв!
            return k

        return None