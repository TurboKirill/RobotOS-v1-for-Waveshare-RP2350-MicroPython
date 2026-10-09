# app_editor.py - Редактор Notepad++ с плавным меню без мерцаний и Save As
import os
import time
import math
import struct
import st7789

C_BG      = st7789.ST7789.color565(14, 18, 28)
C_HEADER  = st7789.ST7789.color565(0, 120, 215)
C_LINE_NUM= st7789.ST7789.color565(90, 110, 140)
C_TEXT    = 0xFFFF
C_WHITE   = 0xFFFF                                  # Добавлена недостающая переменная!
C_CURSOR  = st7789.ST7789.color565(0, 240, 255)
C_MENU_BG = st7789.ST7789.color565(22, 30, 48)
C_GRAY    = st7789.ST7789.color565(120, 135, 165)
C_GLOW    = st7789.ST7789.color565(0, 240, 255)

class NotepadApp:
    def __init__(self, tft, audio, inputs, config=None, filepath="/sd/notes.txt"):
        self.tft = tft
        self.audio = audio
        self.inputs = inputs
        self.cfg = config if config else {"vol_ui": 30, "mute": False}
        self.filepath = filepath

        self.lines = [""]
        self.cur_row = 0
        self.cur_col = 0
        self.scroll_row = 0
        self.scroll_col = 0
        self.is_modified = False

        self.load_file()

    def beep(self, freq=1100, ms=10):
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

    def load_file(self):
        try:
            with open(self.filepath, "r") as f:
                raw = [l.rstrip("\r\n") for l in f.readlines()]
                self.lines = raw if raw else [""]
        except:
            if self.filepath.endswith(".py"):
                self.lines = ["# Python Script", "print('Hello RobotOS!')", ""]
            else:
                self.lines = ["# RobotOS Notepad++", "Type notes here...", ""]
        self.is_modified = False

    def save_file(self):
        try:
            with open(self.filepath, "w") as f:
                for line in self.lines:
                    f.write(line + "\n")
            self.is_modified = False
            self.beep(1600, 30)
            return True
        except Exception as e:
            print("Save error:", e)
            return False

    def prompt_save_as(self):
        """Аккуратный модальный диалог SAVE AS без наложений"""
        drives = ["/sd/", "/"]
        drive_idx = 0 if self.filepath.startswith("/sd") else 1

        name = self.filepath.split("/")[-1]
        if not name:
            name = "script.py"

        active_field = 1

        while True:
            self.tft.fill_rect(10, 50, 220, 180, C_MENU_BG)
            self.tft.rect(10, 50, 220, 180, C_GLOW)

            self.tft.fill_rect(12, 52, 216, 24, C_HEADER)
            self.tft.text("SAVE AS...", 25, 60, C_TEXT)

            # Поле 1: Накопитель
            c1 = C_GLOW if active_field == 0 else C_TEXT
            self.tft.text("1. TARGET DRIVE:", 20, 86, C_GRAY)
            drive_label = "< SD CARD: /sd/ >" if drive_idx == 0 else "< FLASH: / >"
            self.tft.fill_rect(20, 100, 200, 20, C_BG)
            if active_field == 0:
                self.tft.rect(20, 100, 200, 20, C_GLOW)
            self.tft.text(drive_label, 26, 106, c1)

            # Поле 2: Имя файла
            c2 = C_GLOW if active_field == 1 else C_TEXT
            self.tft.text("2. FILE NAME:", 20, 130, C_GRAY)
            self.tft.fill_rect(20, 144, 200, 22, C_BG)
            if active_field == 1:
                self.tft.rect(20, 144, 200, 22, C_GLOW)
            
            disp_name = (name[-18:] + "_") if active_field == 1 else name[-18:]
            self.tft.text(disp_name, 26, 151, c2)

            self.tft.line(10, 180, 230, 180, C_GRAY)
            self.tft.text("UP/DN:Field  ENTER:Save", 18, 190, C_GRAY)
            self.tft.text("ESC:Cancel", 18, 206, C_GLOW)
            self.tft.show()

            while True:
                ev = self.inputs.get_event()
                if ev:
                    if ev in ['UP', 'DOWN']:
                        active_field = 1 - active_field
                        self.beep(850, 10); break
                    elif ev in ['LEFT', 'RIGHT'] and active_field == 0:
                        drive_idx = 1 - drive_idx
                        self.beep(950, 10); break
                    elif ev in ['ESC', 'BACK']:
                        return 'CANCEL'
                    elif ev == 'ENTER':
                        clean_name = name.strip()
                        if clean_name:
                            self.filepath = drives[drive_idx] + clean_name
                            self.save_file()
                            return 'SAVED'
                    elif active_field == 1:
                        if ev == 'BACKSPACE':
                            if len(name) > 0:
                                name = name[:-1]
                                self.beep(650, 8); break
                        elif len(ev) == 1 and ev not in [' ', '/']:
                            name += ev
                            self.beep(1200, 6); break
                time.sleep_ms(20)

    def adjust_scroll(self):
        max_rows = 18
        max_cols = 23

        if self.cur_row < self.scroll_row:
            self.scroll_row = self.cur_row
        elif self.cur_row >= self.scroll_row + max_rows:
            self.scroll_row = self.cur_row - max_rows + 1

        if self.cur_col < self.scroll_col:
            self.scroll_col = self.cur_col
        elif self.cur_col >= self.scroll_col + max_cols:
            self.scroll_col = self.cur_col - max_cols + 1

    def draw_editor(self, update_screen=True):
        self.tft.fill(C_BG)

        # Шапка
        self.tft.fill_rect(0, 0, 240, 26, C_HEADER)
        fname = self.filepath.split("/")[-1][:13]
        mod_mark = "*" if self.is_modified else ""
        self.tft.text(f"{fname}{mod_mark}", 8, 8, C_TEXT)
        self.tft.text(f"Ln {self.cur_row+1}, Col {self.cur_col+1}", 130, 8, 0x07FF)

        max_rows = 18
        max_cols = 23
        y = 34

        for r_idx in range(self.scroll_row, min(len(self.lines), self.scroll_row + max_rows)):
            line = self.lines[r_idx]
            self.tft.text(f"{r_idx+1:02d}|", 4, y, C_LINE_NUM)

            visible_text = line[self.scroll_col : self.scroll_col + max_cols]
            self.tft.text(visible_text, 32, y, C_TEXT)

            if r_idx == self.cur_row:
                cx = 32 + (self.cur_col - self.scroll_col) * 8
                if 32 <= cx <= 220:
                    self.tft.fill_rect(cx, y + 8, 7, 2, C_CURSOR)

            y += 14

        self.tft.line(0, 296, 240, 296, C_LINE_NUM)
        self.tft.text("TYPE:Text  BKSP:Del", 6, 304, C_LINE_NUM)
        self.tft.text("ESC:Menu", 165, 304, C_CURSOR)

        if update_screen:
            self.tft.show()

    def show_exit_dialog(self):
        opts = [
            "1. SAVE",
            "2. SAVE AS...",
            "3. EXIT (DISCARD)",
            "4. CANCEL"
        ]
        sel = 0

        # Фон рисуется один раз в буфер
        self.draw_editor(update_screen=False)

        menu_x, menu_y = 15, 75
        menu_w, menu_h = 210, 145

        while True:
            self.tft.fill_rect(menu_x, menu_y, menu_w, menu_h, C_MENU_BG)
            self.tft.rect(menu_x, menu_y, menu_w, menu_h, C_CURSOR)
            self.tft.text("NOTEPAD++ MENU", menu_x + 48, menu_y + 12, C_TEXT)

            y = menu_y + 36
            for i, o in enumerate(opts):
                is_act = (i == sel)
                if is_act:
                    self.tft.fill_rect(menu_x + 6, y - 3, menu_w - 12, 22, C_HEADER)
                    self.tft.text(f"> {o}", menu_x + 10, y + 4, C_TEXT)
                else:
                    self.tft.text(f"  {o}", menu_x + 10, y + 4, C_GRAY)
                y += 24

            self.tft.show()

            while True:
                ev = self.inputs.get_event()
                if ev:
                    if ev == 'UP':
                        sel = (sel - 1) % len(opts)
                        self.beep(850, 10); break
                    elif ev == 'DOWN':
                        sel = (sel + 1) % len(opts)
                        self.beep(750, 10); break
                    elif ev == 'ENTER':
                        if sel == 0:
                            self.save_file()
                            return 'EXIT'
                        elif sel == 1:
                            res = self.prompt_save_as()
                            if res == 'SAVED':
                                return 'EXIT'
                            self.draw_editor(update_screen=False)
                            break
                        elif sel == 2:
                            return 'EXIT'
                        elif sel == 3:
                            return 'CANCEL'
                    elif ev in ['ESC', 'BACK']:
                        return 'CANCEL'
                time.sleep_ms(20)

    def run(self):
        while True:
            self.adjust_scroll()
            self.draw_editor()

            ev = self.inputs.get_event()
            if ev:
                cur_line = self.lines[self.cur_row]

                if ev in ['ESC', 'BACK']:
                    res = self.show_exit_dialog()
                    if res == 'EXIT':
                        break

                elif ev == 'UP':
                    if self.cur_row > 0:
                        self.cur_row -= 1
                        self.cur_col = min(self.cur_col, len(self.lines[self.cur_row]))
                        self.beep(900, 8)

                elif ev == 'DOWN':
                    if self.cur_row < len(self.lines) - 1:
                        self.cur_row += 1
                        self.cur_col = min(self.cur_col, len(self.lines[self.cur_row]))
                        self.beep(800, 8)

                elif ev == 'LEFT':
                    if self.cur_col > 0:
                        self.cur_col -= 1
                    elif self.cur_row > 0:
                        self.cur_row -= 1
                        self.cur_col = len(self.lines[self.cur_row])
                    self.beep(950, 8)

                elif ev == 'RIGHT':
                    if self.cur_col < len(cur_line):
                        self.cur_col += 1
                    elif self.cur_row < len(self.lines) - 1:
                        self.cur_row += 1
                        self.cur_col = 0
                    self.beep(950, 8)

                elif ev == 'ENTER':
                    left_part = cur_line[:self.cur_col]
                    right_part = cur_line[self.cur_col:]
                    self.lines[self.cur_row] = left_part
                    self.lines.insert(self.cur_row + 1, right_part)
                    self.cur_row += 1
                    self.cur_col = 0
                    self.scroll_col = 0
                    self.is_modified = True
                    self.beep(1200, 15)

                elif ev == 'BACKSPACE':
                    if self.cur_col > 0:
                        self.lines[self.cur_row] = cur_line[:self.cur_col-1] + cur_line[self.cur_col:]
                        self.cur_col -= 1
                        self.is_modified = True
                        self.beep(650, 8)
                    elif self.cur_row > 0:
                        prev_len = len(self.lines[self.cur_row - 1])
                        self.lines[self.cur_row - 1] += cur_line
                        self.lines.pop(self.cur_row)
                        self.cur_row -= 1
                        self.cur_col = prev_len
                        self.is_modified = True
                        self.beep(650, 8)

                elif len(ev) == 1 or ev == '  ':
                    self.lines[self.cur_row] = cur_line[:self.cur_col] + ev + cur_line[self.cur_col:]
                    self.cur_col += len(ev)
                    self.is_modified = True
                    self.beep(1300, 6)

            time.sleep_ms(20)