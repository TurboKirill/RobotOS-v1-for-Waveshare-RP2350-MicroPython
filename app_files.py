# app_files.py - Профессиональный Commander: ввод любого пути, Copy, Move, Mkdir, Delete
import os
import time
import math
import struct
import st7789
import app_editor
import app_gallery

# Палитра
C_BG      = st7789.ST7789.color565(10, 14, 26)
C_HEADER  = st7789.ST7789.color565(245, 120, 0)
C_SEL_BG  = st7789.ST7789.color565(30, 45, 80)
C_GLOW    = st7789.ST7789.color565(0, 240, 255)
C_WHITE   = 0xFFFF
C_GRAY    = st7789.ST7789.color565(130, 145, 175)
C_DIR     = st7789.ST7789.color565(255, 215, 0)
C_WAV     = st7789.ST7789.color565(0, 230, 118)
C_IMG     = st7789.ST7789.color565(255, 60, 180)
C_PY      = st7789.ST7789.color565(0, 200, 255)
C_TXT     = st7789.ST7789.color565(255, 160, 0)
C_MENU_BG = st7789.ST7789.color565(22, 30, 48)
C_MARKED  = st7789.ST7789.color565(255, 230, 0)

class FileManagerApp:
    def __init__(self, tft, audio, inputs, config=None):
        self.tft = tft
        self.audio = audio
        self.inputs = inputs
        self.cfg = config if config else {"vol_ui": 30, "mute": False}

    def beep(self, freq=1000, ms=15):
        if self.cfg.get("mute") or self.cfg.get("vol_ui", 30) == 0:
            return
        rate = 22050
        samples = int(rate / freq)
        cycle = bytearray(samples * 2)
        amp = int(1000 * (self.cfg.get("vol_ui", 30) / 100))
        for i in range(samples):
            v = int(amp * math.sin(2 * math.pi * i / samples))
            struct.pack_into("<h", cycle, i * 2, v)
        for _ in range(int((ms / 1000) * freq)):
            self.audio.write(cycle)

    def play_wav(self, path):
        try:
            with open(path, "rb") as f:
                f.seek(44)
                buf = bytearray(1024)
                self.tft.fill_rect(8, 250, 224, 20, C_BG)
                self.tft.text("PLAYING... [ESC: Stop]", 12, 254, C_WAV)
                self.tft.show()
                while True:
                    ev = self.inputs.get_event()
                    if ev in ['BACK', 'ENTER', 'ESC']:
                        break
                    n = f.readinto(buf)
                    if not n: break
                    self.audio.write(buf[:n])
        except Exception as e:
            print("Audio error:", e)

    def format_size(self, size):
        if size < 1024: return f"{size}B"
        elif size < 1024 * 1024: return f"{size//1024}K"
        else: return f"{size//(1024*1024)}M"

    def draw_disk_space_bar(self, current_path):
        try:
            root = "/sd" if current_path.startswith("/sd") else "/"
            st = os.statvfs(root)
            total = st[0] * st[2]
            free = st[0] * st[3]
            used = total - free
            pct = int((used / total) * 100) if total > 0 else 0
            
            t_str = self.format_size(total)
            u_str = self.format_size(used)
            self.tft.text(f"Disk: {u_str}/{t_str} ({pct}%)", 10, 252, C_GRAY)
            self.tft.rect(10, 264, 220, 7, C_GRAY)
            fill_w = min(216, max(2, int(216 * (pct / 100))))
            self.tft.fill_rect(12, 266, fill_w, 3, C_GLOW)
        except:
            pass

    def prompt_input_cursor(self, title, initial_val=""):
        """Полноценное окно ввода текста с курсором внутри строки"""
        text = initial_val
        cur_pos = len(text)
        scroll_x = 0
        max_disp = 21

        while True:
            if cur_pos < scroll_x:
                scroll_x = cur_pos
            elif cur_pos >= scroll_x + max_disp:
                scroll_x = cur_pos - max_disp + 1

            disp_str = text[scroll_x : scroll_x + max_disp]

            self.tft.fill_rect(10, 75, 220, 125, C_MENU_BG)
            self.tft.rect(10, 75, 220, 125, C_GLOW)
            self.tft.fill_rect(12, 77, 216, 22, C_HEADER)
            self.tft.text(title[:20], 18, 83, C_WHITE)

            self.tft.fill_rect(18, 110, 204, 24, C_BG)
            self.tft.rect(18, 110, 204, 24, C_GLOW)
            self.tft.text(disp_str, 24, 117, C_WHITE)

            cursor_px = 24 + (cur_pos - scroll_x) * 8
            if 24 <= cursor_px <= 212:
                self.tft.fill_rect(cursor_px, 128, 7, 2, C_GLOW)

            self.tft.line(10, 150, 230, 150, C_GRAY)
            self.tft.text("< >:Move cursor", 16, 158, C_GRAY)
            self.tft.text("ENTER:OK  ESC:Cancel", 16, 174, C_GLOW)
            self.tft.show()

            while True:
                ev = self.inputs.get_event()
                if ev:
                    if ev in ['ESC', 'BACK']:
                        return None
                    elif ev == 'ENTER':
                        clean = text.strip()
                        return clean if clean else None
                    elif ev == 'LEFT':
                        if cur_pos > 0:
                            cur_pos -= 1
                            self.beep(900, 6); break
                    elif ev == 'RIGHT':
                        if cur_pos < len(text):
                            cur_pos += 1
                            self.beep(900, 6); break
                    elif ev == 'BACKSPACE':
                        if cur_pos > 0:
                            text = text[:cur_pos-1] + text[cur_pos:]
                            cur_pos -= 1
                            self.beep(650, 8); break
                    elif len(ev) == 1 and ev not in ['\\']:
                        text = text[:cur_pos] + ev + text[cur_pos:]
                        cur_pos += len(ev)
                        self.beep(1200, 6); break
                time.sleep_ms(20)

    def prompt_confirm(self, title, msg):
        opts = ["[1] YES (CONFIRM)", "[2] NO (CANCEL)"]
        sel = 0
        while True:
            self.tft.fill_rect(15, 85, 210, 115, C_MENU_BG)
            self.tft.rect(15, 85, 210, 115, st7789.ST7789.color565(255, 60, 60))
            self.tft.text(title[:18], 25, 96, st7789.ST7789.color565(255, 60, 60))
            self.tft.text(msg[:22], 25, 114, C_WHITE)

            y = 138
            for i, o in enumerate(opts):
                c = C_GLOW if i == sel else C_GRAY
                self.tft.text(o, 30, y, c)
                y += 22

            self.tft.show()

            while True:
                ev = self.inputs.get_event()
                if ev:
                    if ev in ['UP', 'DOWN']:
                        sel = 1 - sel
                        self.beep(850, 10); break
                    elif ev in ['ESC', 'BACK']:
                        return False
                    elif ev == 'ENTER':
                        return (sel == 0)
                time.sleep_ms(20)

    def stream_copy(self, src_path, dst_path):
        """Потоковая передача файла кусочками по 2 КБ"""
        self.tft.fill_rect(15, 110, 210, 60, C_MENU_BG)
        self.tft.rect(15, 110, 210, 60, C_GLOW)
        fname = src_path.split("/")[-1][:13]
        self.tft.text(f"COPYING: {fname}", 22, 132, C_WHITE)
        self.tft.show()
        try:
            with open(src_path, "rb") as fsrc:
                with open(dst_path, "wb") as fdst:
                    buf = bytearray(2048)
                    while True:
                        n = fsrc.readinto(buf)
                        if not n: break
                        fdst.write(buf[:n])
            return True
        except Exception as e:
            print("Copy error:", e)
            return False

    def copy_or_move_files(self, current_path, file_list, is_move=False):
        """Копирование или перенос файлов по ЛЮБОМУ указанному пользователем пути"""
        act_title = "MOVE FILES TO:" if is_move else "COPY FILES TO:"
        # По умолчанию предлагаем текущую папку
        default_dst = (current_path + "/").replace("//", "/")
        
        target_path = self.prompt_input_cursor(act_title, default_dst)
        if not target_path: return False

        target_dir = target_path.rstrip("/")
        if not target_dir: target_dir = "/"

        # Автоматически создаем целевую папку, если пользователь ввел новое имя!
        try:
            os.mkdir(target_dir)
        except:
            pass

        # Обрабатываем каждый файл
        for f in file_list:
            src = (current_path + "/" + f).replace("//", "/")
            dst = (target_dir + "/" + f).replace("//", "/")

            if src == dst:
                dst = (target_dir + "/copy_" + f).replace("//", "/")

            # Если это ПЕРЕНОС (Move) внутри одного диска - делаем мгновенный rename!
            is_same_drive = (src.startswith("/sd") == dst.startswith("/sd"))
            if is_move and is_same_drive:
                try:
                    os.rename(src, dst)
                    continue
                except Exception as e:
                    print("Quick move error, fallback to stream:", e)

            # Иначе потоковое копирование
            if self.stream_copy(src, dst):
                if is_move:
                    try: os.remove(src)
                    except: pass

        self.beep(1600, 35)
        return True

    def show_actions_menu(self, current_path, item_name, is_dir, selected_set):
        opts = [
            "1. RENAME",
            "2. NEW FOLDER",
            "3. COPY TO PATH...",
            "4. MOVE TO PATH...",
            "5. DELETE",
            "< CANCEL"
        ]
        sel = 0
        menu_w, menu_h = 210, 165
        menu_x, menu_y = 15, 60

        while True:
            self.tft.fill_rect(menu_x, menu_y, menu_w, menu_h, C_MENU_BG)
            self.tft.rect(menu_x, menu_y, menu_w, menu_h, C_GLOW)
            self.tft.text("FILE ACTIONS", menu_x + 45, menu_y + 12, C_WHITE)

            y = menu_y + 32
            for i, o in enumerate(opts):
                is_act = (i == sel)
                if is_act:
                    self.tft.fill_rect(menu_x + 6, y - 3, menu_w - 12, 18, C_SEL_BG)
                    self.tft.text(f"> {o}", menu_x + 10, y + 2, C_GLOW)
                else:
                    self.tft.text(f"  {o}", menu_x + 10, y + 2, C_GRAY)
                y += 20

            self.tft.show()

            while True:
                ev = self.inputs.get_event()
                if ev:
                    if ev in ['UP', 'DOWN']:
                        sel = (sel + (1 if ev == 'DOWN' else -1)) % len(opts)
                        self.beep(850, 10); break
                    elif ev in ['ESC', 'BACK'] or (ev == 'ENTER' and sel == 5):
                        return None
                    elif ev == 'ENTER':
                        targets = list(selected_set) if selected_set else [item_name]
                        targets = [t for t in targets if not t.startswith("..") and not t.startswith("<")]

                        # 1. RENAME
                        if sel == 0:
                            if not item_name.startswith("..") and not item_name.startswith("<"):
                                new_name = self.prompt_input_cursor("RENAME TO:", item_name)
                                if new_name and new_name != item_name:
                                    try:
                                        os.rename((current_path + "/" + item_name).replace("//", "/"),
                                                  (current_path + "/" + new_name).replace("//", "/"))
                                        self.beep(1400, 25)
                                    except Exception as e: print("Rename error:", e)
                            return 'REFRESH'

                        # 2. NEW FOLDER
                        elif sel == 1:
                            new_dir = self.prompt_input_cursor("NEW FOLDER NAME:", "new_dir")
                            if new_dir:
                                try:
                                    os.mkdir((current_path + "/" + new_dir).replace("//", "/"))
                                    self.beep(1400, 25)
                                except Exception as e: print("Mkdir error:", e)
                            return 'REFRESH'

                        # 3. COPY TO PATH
                        elif sel == 2:
                            if targets:
                                self.copy_or_move_files(current_path, targets, is_move=False)
                                selected_set.clear()
                            return 'REFRESH'

                        # 4. MOVE TO PATH
                        elif sel == 3:
                            if targets:
                                self.copy_or_move_files(current_path, targets, is_move=True)
                                selected_set.clear()
                            return 'REFRESH'

                        # 5. DELETE
                        elif sel == 4:
                            if targets:
                                msg = f"DELETE {len(targets)} ITEMS?" if len(targets) > 1 else item_name
                                if self.prompt_confirm("CONFIRM DELETE?", msg):
                                    for t in targets:
                                        full_t = (current_path + "/" + t).replace("//", "/")
                                        try:
                                            if (os.stat(full_t)[0] & 0x4000) != 0:
                                                os.rmdir(full_t)
                                            else:
                                                os.remove(full_t)
                                        except Exception as e: print("Del error:", e)
                                    self.beep(600, 40)
                                    selected_set.clear()
                            return 'REFRESH'
                time.sleep_ms(20)

    def get_dir_items(self, path):
        IGNORE = ['System Volume Information', '$RECYCLE.BIN', 'FOUND.000']
        filtered = []
        try:
            for entry in os.ilistdir(path):
                name = entry[0]
                if name not in IGNORE and not name.startswith('.'):
                    filtered.append(name)
        except:
            try:
                for name in os.listdir(path):
                    if name not in IGNORE and not name.startswith('.'):
                        filtered.append(name)
            except:
                return []
        return sorted(filtered)

    def browse_dir(self, current_path):
        sel = 0
        scroll_top = 0
        visible_rows = 6
        selected_set = set()

        while True:
            raw_items = self.get_dir_items(current_path)
            items = []
            if current_path not in ["/", "/sd"]:
                items.append((".. (UP)", True, 0, ""))

            for name in raw_items:
                full = (current_path + "/" + name).replace("//", "/")
                is_dir = False
                size = 0
                try:
                    st = os.stat(full)
                    is_dir = (st[0] & 0x4000) != 0
                    size = st[6]
                except:
                    pass
                ext = name.split(".")[-1].lower() if "." in name else ""
                items.append((name, is_dir, size, ext))

            if not items:
                items = [("< EMPTY >", False, 0, "")]

            sel = max(0, min(sel, len(items) - 1))
            if sel < scroll_top: scroll_top = sel
            if sel >= scroll_top + visible_rows: scroll_top = sel - visible_rows + 1

            self.tft.fill(C_BG)
            self.tft.fill_rect(0, 0, 240, 32, C_HEADER)
            short_path = current_path if len(current_path) < 22 else "..." + current_path[-18:]
            self.tft.text(f"DIR: {short_path}", 8, 10, C_WHITE)

            y = 40
            for i in range(scroll_top, min(len(items), scroll_top + visible_rows)):
                name, is_dir, size, ext = items[i]
                is_active = (i == sel)
                is_marked = (name in selected_set)

                if is_active:
                    self.tft.fill_rect(6, y - 2, 228, 28, C_SEL_BG)
                    self.tft.rect(6, y - 2, 228, 28, C_GLOW)

                if name.startswith(".."): icon, col = "<DIR>", C_DIR
                elif is_dir:             icon, col = "[DIR]", C_DIR
                elif ext == "wav":       icon, col = "[WAV]", C_WAV
                elif ext in ["bmp", "raw"]: icon, col = "[IMG]", C_IMG
                elif ext == "py":        icon, col = "[PY ]", C_PY
                elif ext in ["txt", "log", "md"]: icon, col = "[TXT]", C_TXT
                else:                    icon, col = "[FILE]", C_WHITE

                mark_prefix = "*" if is_marked else " "
                self.tft.text(mark_prefix + icon, 8, y + 6, C_MARKED if is_marked else col)
                
                name_col = C_MARKED if is_marked else (C_WHITE if is_active else C_GRAY)
                self.tft.text(name[:13], 64, y + 6, name_col)

                if not is_dir and not name.startswith("..") and not name.startswith("<"):
                    self.tft.text(self.format_size(size), 195, y + 6, C_GRAY)

                y += 32

            self.draw_disk_space_bar(current_path)

            self.tft.line(0, 276, 240, 276, C_GRAY)
            if selected_set:
                self.tft.text(f"MARKED: {len(selected_set)} items", 10, 286, C_MARKED)
            else:
                self.tft.text("ENTER:Open  SPC:Mark  M:Menu", 10, 286, C_WHITE)
            # Полная подсказка горячих кнопок
            self.tft.text("R:Ren N:Dir C:Cop X:Mov D:Del", 4, 302, C_GLOW)
            self.tft.show()

            while True:
                ev = self.inputs.get_event()
                if ev:
                    curr_name, curr_isdir, _, curr_ext = items[sel]

                    if ev == 'UP':
                        sel = (sel - 1) % len(items)
                        self.beep(850, 15); break
                    elif ev == 'DOWN':
                        sel = (sel + 1) % len(items)
                        self.beep(750, 15); break
                    elif ev in ['BACK', 'ESC']:
                        self.beep(600, 25)
                        if selected_set:
                            selected_set.clear(); break
                        if current_path in ["/", "/sd"]:
                            return
                        else:
                            current_path = "/".join(current_path.rstrip("/").split("/")[:-1])
                            if not current_path: current_path = "/"
                            sel = 0; break

                    # ПРОБЕЛ - МУЛЬТИ-ВЫДЕЛЕНИЕ
                    elif ev == ' ':
                        if not curr_name.startswith("..") and not curr_name.startswith("<"):
                            if curr_name in selected_set: selected_set.remove(curr_name)
                            else: selected_set.add(curr_name)
                            self.beep(1300, 10)
                            sel = (sel + 1) % len(items)
                        break

                    # МЕНЮ ДЕЙСТВИЙ 'M'
                    elif ev == 'm':
                        res = self.show_actions_menu(current_path, curr_name, curr_isdir, selected_set)
                        if res == 'REFRESH': break

                    # СОЗДАТЬ ПАПКУ 'N'
                    elif ev == 'n':
                        new_dir = self.prompt_input_cursor("NEW FOLDER NAME:", "new_dir")
                        if new_dir:
                            try:
                                os.mkdir((current_path + "/" + new_dir).replace("//", "/"))
                                self.beep(1400, 25)
                            except Exception as e: print("Mkdir error:", e)
                        break

                    # ПЕРЕИМЕНОВАТЬ 'R'
                    elif ev == 'r':
                        if not curr_name.startswith("..") and not curr_name.startswith("<"):
                            new_name = self.prompt_input_cursor("RENAME TO:", curr_name)
                            if new_name and new_name != curr_name:
                                try:
                                    os.rename((current_path + "/" + curr_name).replace("//", "/"),
                                              (current_path + "/" + new_name).replace("//", "/"))
                                    self.beep(1400, 25)
                                except Exception as e: print("Rename error:", e)
                        break

                    # УДАЛИТЬ 'D'
                    elif ev == 'd':
                        targets = list(selected_set) if selected_set else [curr_name]
                        targets = [t for t in targets if not t.startswith("..") and not t.startswith("<")]
                        if targets:
                            msg = f"DELETE {len(targets)} ITEMS?" if len(targets) > 1 else curr_name
                            if self.prompt_confirm("CONFIRM DELETE?", msg):
                                for t in targets:
                                    try:
                                        full_t = (current_path + "/" + t).replace("//", "/")
                                        if (os.stat(full_t)[0] & 0x4000) != 0:
                                            os.rmdir(full_t)
                                        else:
                                            os.remove(full_t)
                                    except Exception as e: print("Del error:", e)
                                self.beep(600, 40)
                                selected_set.clear()
                        break

                    # КОПИРОВАТЬ В ЛЮБОЙ ПУТЬ 'C'
                    elif ev == 'c':
                        targets = list(selected_set) if selected_set else [curr_name]
                        targets = [t for t in targets if not t.startswith("..") and not t.startswith("<")]
                        if targets:
                            self.copy_or_move_files(current_path, targets, is_move=False)
                            selected_set.clear()
                        break

                    # ПЕРЕНЕСТИ / ВЫРЕЗАТЬ В ЛЮБОЙ ПУТЬ 'X'
                    elif ev == 'x':
                        targets = list(selected_set) if selected_set else [curr_name]
                        targets = [t for t in targets if not t.startswith("..") and not t.startswith("<")]
                        if targets:
                            self.copy_or_move_files(current_path, targets, is_move=True)
                            selected_set.clear()
                        break

                    # ENTER - ОТКРЫТИЕ
                    elif ev == 'ENTER':
                        if curr_name.startswith(".."):
                            current_path = "/".join(current_path.rstrip("/").split("/")[:-1])
                            if not current_path: current_path = "/"
                            sel = 0; break
                        elif curr_isdir:
                            self.beep(1200, 30)
                            current_path = (current_path + "/" + curr_name).replace("//", "/")
                            sel = 0; selected_set.clear(); break
                        else:
                            full_file = (current_path + "/" + curr_name).replace("//", "/")
                            if curr_ext in ["bmp", "raw"]:
                                gallery = app_gallery.GalleryApp(self.tft, self.audio, self.inputs, self.cfg)
                                gallery.run_from_file(full_file)
                                break
                            elif curr_ext in ["txt", "log", "md", "py"]:
                                editor = app_editor.NotepadApp(self.tft, self.audio, self.inputs, self.cfg, filepath=full_file)
                                editor.run()
                                break
                            elif curr_ext == "wav":
                                self.play_wav(full_file)
                                break
                            else:
                                self.beep(400, 40)
                time.sleep_ms(20)

    def run(self):
        drives = [
            ("1. FLASH STORAGE ( / )", "/"),
            ("2. MICROSD CARD  ( /sd )", "/sd"),
            ("< BACK TO ROBOTOS", None)
        ]
        sel = 0

        while True:
            self.tft.fill(C_BG)
            self.tft.fill_rect(0, 0, 240, 42, C_HEADER)
            self.tft.text("FILE COMMANDER", 16, 16, C_WHITE)

            y = 70
            for i, (label, path) in enumerate(drives):
                is_act = (i == sel)
                if is_act:
                    self.tft.fill_rect(10, y - 4, 220, 32, C_SEL_BG)
                    self.tft.rect(10, y - 4, 220, 32, C_GLOW)
                    self.tft.text(f"> {label}", 18, y + 8, C_GLOW)
                else:
                    self.tft.text(f"  {label}", 18, y + 8, C_GRAY)
                y += 45

            self.tft.line(0, 276, 240, 276, C_GRAY)
            self.tft.text("SELECT DRIVE: [ENTER]", 20, 290, C_WHITE)
            self.tft.show()

            while True:
                ev = self.inputs.get_event()
                if ev:
                    if ev == 'UP':
                        sel = (sel - 1) % len(drives)
                        self.beep(850, 15); break
                    elif ev == 'DOWN':
                        sel = (sel + 1) % len(drives)
                        self.beep(750, 15); break
                    elif ev in ['BACK', 'ESC'] or (ev == 'ENTER' and sel == 2):
                        self.beep(600, 30)
                        return
                    elif ev == 'ENTER':
                        self.beep(1200, 30)
                        self.browse_dir(drives[sel][1])
                        break
                time.sleep_ms(20)