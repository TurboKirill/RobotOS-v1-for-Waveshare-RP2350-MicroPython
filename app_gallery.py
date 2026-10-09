# app_gallery.py - Ультрабыстрая галерея с поддержкой 24-bit / 32-bit BMP и защитой от зависаний
import os
import time
import math
import struct
import st7789
import micropython

# ================= МАШИННЫЙ КОД ARM CORTEX-M33 (150 МГц) =================
@micropython.viper
def decode_row_24(src: ptr8, dst: ptr8, width: int):
    """Декодер 24-битного BMP (BGR)"""
    s_idx = 0
    d_idx = 0
    for x in range(width):
        b = int(src[s_idx])
        g = int(src[s_idx + 1])
        r = int(src[s_idx + 2])
        s_idx += 3
        c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        c_swapped = ((c & 0xFF) << 8) | ((c >> 8) & 0xFF)
        dst[d_idx] = c_swapped & 0xFF
        dst[d_idx + 1] = (c_swapped >> 8) & 0xFF
        d_idx += 2

@micropython.viper
def decode_row_32(src: ptr8, dst: ptr8, width: int):
    """Декодер 32-битного BMP (BGRA с пропуском альфа-канала)"""
    s_idx = 0
    d_idx = 0
    for x in range(width):
        b = int(src[s_idx])
        g = int(src[s_idx + 1])
        r = int(src[s_idx + 2])
        s_idx += 4  # Пропускаем 4-й байт альфа-канала
        c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        c_swapped = ((c & 0xFF) << 8) | ((c >> 8) & 0xFF)
        dst[d_idx] = c_swapped & 0xFF
        dst[d_idx + 1] = (c_swapped >> 8) & 0xFF
        d_idx += 2

class GalleryApp:
    def __init__(self, tft, audio, inputs, config=None):
        self.tft = tft
        self.audio = audio
        self.inputs = inputs
        self.cfg = config if config else {"vol_ui": 30, "mute": False}
        self.photos = []
        self.current_idx = 0

    def beep(self, freq=1100, ms=12):
        """Тихий щелчок при перелистывании фото"""
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

    def scan_photos(self):
        """Сканируем только целевую папку /sd/pictures"""
        self.photos = []
        target_dir = "/sd/pictures"
        try:
            for f in sorted(os.listdir(target_dir)):
                if f.lower().endswith(".bmp") and not f.startswith("."):
                    self.photos.append(target_dir + "/" + f)
        except Exception as e:
            print(f"Ошибка чтения {target_dir}:", e)

        # Если в pictures пусто, пробуем корень
        if not self.photos:
            try:
                for f in sorted(os.listdir("/sd")):
                    if f.lower().endswith(".bmp") and not f.startswith("."):
                        self.photos.append("/sd/" + f)
            except:
                pass

        print(f"🖼️ Найдено фотографий: {len(self.photos)}")
        for i, p in enumerate(self.photos):
            print(f"   [{i+1}] {p}")

    def show_photo_fast(self, path):
        t0 = time.ticks_ms()
        try:
            with open(path, "rb") as f:
                header = f.read(54)
                if header[:2] != b'BM':
                    self.draw_error("Неверный формат BMP")
                    return

                w = int.from_bytes(header[18:22], "little")
                h = int.from_bytes(header[22:26], "little")
                bpp = int.from_bytes(header[28:30], "little")
                offset = int.from_bytes(header[10:14], "little")

                # Проверка глубины цвета
                if bpp not in [24, 32]:
                    self.draw_error(f"BMP {bpp}bit не поддерживается")
                    return

                f.seek(offset)
                bytes_per_pixel = bpp // 8
                row_len = w * bytes_per_pixel
                pad = (4 - (row_len % 4)) % 4
                raw_row = bytearray(row_len + pad)

                tft_buf = self.tft.buffer
                w_target = min(w, 240)
                decode_func = decode_row_32 if bpp == 32 else decode_row_24

                # Отрисовка снизу вверх
                for y in range(min(h, 320) - 1, -1, -1):
                    f.readinto(raw_row)
                    dst_offset = y * 240 * 2
                    decode_func(raw_row, memoryview(tft_buf)[dst_offset:], w_target)

            # Нижняя информационная плашка
            fname = path.split("/")[-1][:13]
            info = f"[{self.current_idx + 1}/{len(self.photos)}] {fname}"
            self.tft.fill_rect(0, 296, 240, 24, 0x0000)
            self.tft.text(info, 8, 304, 0xFFFF)
            self.tft.text("< > Flip", 175, 304, 0x07FF)
            self.tft.show()

            dt = time.ticks_diff(time.ticks_ms(), t0)
            print(f"⚡ Загружено за {dt} мс: {path} ({w}x{h}, {bpp}bit)")

        except Exception as e:
            print("Ошибка загрузки:", e)
            self.draw_error("Ошибка файла")

    def draw_error(self, msg):
        self.tft.fill(0x0000)
        self.tft.fill_rect(10, 130, 220, 50, 0x0000)
        self.tft.rect(10, 130, 220, 50, 0xF800)
        self.tft.text(msg, 20, 142, 0xF800)
        self.tft.text("Press [ < > ] to skip", 20, 160, 0xFFFF)
        self.tft.show()

    def run(self):
        self.scan_photos()

        if not self.photos:
            self.tft.fill(0x0000)
            self.tft.text("PHOTO GALLERY", 16, 14, 0xFFFF)
            self.tft.text("No .bmp photos found!", 20, 120, 0xFFFF)
            self.tft.text("Put 240x320 BMP into", 20, 145, 0x7BEF)
            self.tft.text("/sd/pictures", 20, 160, 0x07FF)
            self.tft.text("Press [ESC] to exit", 20, 280, 0x07FF)
            self.tft.show()
            while True:
                ev = self.inputs.get_event()
                if ev in ['BACK', 'ENTER']: break
                time.sleep_ms(25)
            return

        self.show_photo_fast(self.photos[self.current_idx])

        while True:
            ev = self.inputs.get_event()
            if ev:
                if ev == 'BACK':
                    self.beep(600, 30)
                    break
                elif ev == 'RIGHT':
                    self.beep(1200, 15)
                    self.current_idx = (self.current_idx + 1) % len(self.photos)
                    self.show_photo_fast(self.photos[self.current_idx])
                elif ev == 'LEFT':
                    self.beep(1000, 15)
                    self.current_idx = (self.current_idx - 1) % len(self.photos)
                    self.show_photo_fast(self.photos[self.current_idx])
            time.sleep_ms(20)
    def run_from_file(self, start_path):
        """Запуск галереи из проводника с выбранного фото с листанием всей папки"""
        # Определяем папку, где лежит выбранное фото
        folder = "/".join(start_path.rstrip("/").split("/")[:-1])
        if not folder: folder = "/"
        
        self.photos = []
        try:
            for f in sorted(os.listdir(folder)):
                if f.lower().endswith(".bmp") and not f.startswith("."):
                    self.photos.append((folder + "/" + f).replace("//", "/"))
        except:
            self.photos = [start_path]

        # Находим индекс выбранного файла в списке
        try:
            self.current_idx = self.photos.index(start_path)
        except:
            self.current_idx = 0

        # Запускаем полноэкранный показ с листанием!
        if self.photos:
            self.show_photo_fast(self.photos[self.current_idx])
            while True:
                ev = self.inputs.get_event()
                if ev:
                    if ev in ['BACK', 'ESC']:
                        self.beep(600, 30)
                        break
                    elif ev == 'RIGHT':
                        self.beep(1200, 15)
                        self.current_idx = (self.current_idx + 1) % len(self.photos)
                        self.show_photo_fast(self.photos[self.current_idx])
                    elif ev == 'LEFT':
                        self.beep(1000, 15)
                        self.current_idx = (self.current_idx - 1) % len(self.photos)
                        self.show_photo_fast(self.photos[self.current_idx])
                time.sleep_ms(20)