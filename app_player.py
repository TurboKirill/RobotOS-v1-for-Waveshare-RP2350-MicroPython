# app_player.py - Музыкальный плеер с регулировкой громкости и переключением треков
import os
import time
import math
import struct
import st7789
import micropython

# Цвета интерфейса плеера
C_BG       = st7789.ST7789.color565(12, 16, 28)
C_HEADER   = st7789.ST7789.color565(130, 30, 190)  # Пурпурный
C_ACCENT   = st7789.ST7789.color565(0, 240, 255)   # Бирюзовый
C_GREEN    = st7789.ST7789.color565(0, 230, 118)   # Зеленый Play
C_WHITE    = 0xFFFF
C_GRAY     = st7789.ST7789.color565(120, 135, 165)
C_BAR_BG   = st7789.ST7789.color565(30, 40, 65)

# ================= МАШИННЫЙ КОД ДЛЯ РЕГУЛИРОВКИ ГРОМКОСТИ =================
@micropython.viper
def apply_volume(buf_ptr: ptr8, num_bytes: int, vol_factor: int):
    """Быстрое масштабирование 16-битного PCM звука на частоте 150 МГц"""
    # vol_factor: 0..100
    idx = 0
    while idx < num_bytes:
        # Считываем 16-битный сэмпл (Little Endian)
        low = int(buf_ptr[idx])
        high = int(buf_ptr[idx + 1])
        sample = low | (high << 8)
        
        # Преобразуем в знаковый int16
        if sample >= 32768:
            sample -= 65536
            
        # Масштабируем громкость
        sample = (sample * vol_factor) // 100
        
        if sample < 0:
            sample += 65536
            
        buf_ptr[idx] = sample & 0xFF
        buf_ptr[idx + 1] = (sample >> 8) & 0xFF
        idx += 2

class MusicPlayerApp:
    def __init__(self, tft, audio, inputs):
        self.tft = tft
        self.audio = audio
        self.inputs = inputs
        self.playlist = []
        self.current_idx = 0
        self.volume = 80       # Начальная громкость 80%
        self.is_paused = False

    def scan_music(self):
        """Поиск WAV треков на карте памяти"""
        self.playlist = []
        search_dirs = ["/sd/wav", "/sd"]
        for d in search_dirs:
            try:
                for f in sorted(os.listdir(d)):
                    if f.lower().endswith(".wav") and not f.startswith("."):
                        full = (d + "/" + f).replace("//", "/")
                        if full not in self.playlist:
                            self.playlist.append(full)
            except:
                pass
        print(f"🎵 Найдено треков: {len(self.playlist)}")

    def draw_player_ui(self, track_name):
        """Отрисовка стильного пульта плеера"""
        self.tft.fill(C_BG)
        # Шапка
        self.tft.fill_rect(0, 0, 240, 36, C_HEADER)
        self.tft.text("MUSIC PLAYER", 14, 14, C_WHITE)
        self.tft.text("v1.0", 195, 14, C_ACCENT)

        # Номер трека
        num_str = f"TRACK {self.current_idx + 1} OF {len(self.playlist)}"
        self.tft.text(num_str, 20, 55, C_GRAY)

        # Карточка трека (Кассета / Винил)
        self.tft.fill_rect(20, 75, 200, 70, C_BAR_BG)
        self.tft.rect(20, 75, 200, 70, C_ACCENT)
        # Название песни крупно
        display_name = track_name.split("/")[-1][:18]
        self.tft.text(display_name, 30, 95, C_WHITE)
        status_txt = "[ ⏸ PAUSED ]" if self.is_paused else "[ ▶ PLAYING ]"
        status_col = C_GRAY if self.is_paused else C_GREEN
        self.tft.text(status_txt, 30, 120, status_col)

        # Шкала громкости
        self.draw_volume_bar()

        # Панель подсказок по кнопкам
        self.tft.line(0, 240, 240, 240, C_BAR_BG)
        self.tft.text("CONTROLS:", 20, 250, C_ACCENT)
        self.tft.text("LEFT/RIGHT : Prev / Next", 20, 268, C_WHITE)
        self.tft.text("UP/DOWN    : Volume +/-", 20, 284, C_WHITE)
        self.tft.text("ENTER: Pause   ESC: Exit", 20, 300, C_GRAY)

        self.tft.show()

    def draw_volume_bar(self):
        """Отрисовка шкалы громкости"""
        self.tft.fill_rect(20, 160, 200, 60, C_BG)
        self.tft.text(f"VOLUME: {self.volume}%", 20, 165, C_WHITE)
        
        # Корпус полоски
        self.tft.rect(20, 185, 200, 12, C_GRAY)
        # Заливка уровня громкости
        fill_w = int(196 * (self.volume / 100))
        if fill_w > 0:
            self.tft.fill_rect(22, 187, fill_w, 8, C_ACCENT)
        self.tft.show()

    def play_current_track(self):
        """Воспроизведение текущего трека с обработкой клавиш на лету"""
        if not self.playlist: return

        track_path = self.playlist[self.current_idx]
        self.draw_player_ui(track_path)

        try:
            with open(track_path, "rb") as f:
                f.seek(44) # Пропускаем заголовок WAV
                buf = bytearray(1024)

                while True:
                    # 1. Опрос клавиатуры и пульта прямо во время музыки
                    ev = self.inputs.get_event()
                    if ev:
                        if ev == 'BACK':
                            return 'EXIT'
                        elif ev == 'ENTER':
                            # Пауза / Возобновление
                            self.is_paused = not self.is_paused
                            self.draw_player_ui(track_path)
                        elif ev == 'UP':
                            # Громче
                            self.volume = min(100, self.volume + 10)
                            self.draw_volume_bar()
                        elif ev == 'DOWN':
                            # Тише
                            self.volume = max(0, self.volume - 10)
                            self.draw_volume_bar()
                        elif ev == 'RIGHT':
                            # Следующая песня
                            self.current_idx = (self.current_idx + 1) % len(self.playlist)
                            return 'NEXT'
                        elif ev == 'LEFT':
                            # Предыдущая песня
                            self.current_idx = (self.current_idx - 1) % len(self.playlist)
                            return 'PREV'

                    # 2. Если на паузе — ждем
                    if self.is_paused:
                        time.sleep_ms(30)
                        continue

                    # 3. Читаем порцию звука
                    n = f.readinto(buf)
                    if not n:
                        # Трек доиграл до конца — переход к следующему!
                        self.current_idx = (self.current_idx + 1) % len(self.playlist)
                        return 'NEXT'

                    # 4. Аппаратное масштабирование громкости машинным кодом
                    if self.volume < 100:
                        apply_volume(buf, n, self.volume)

                    # 5. Отправляем в динамик
                    self.audio.write(buf[:n])

        except Exception as e:
            print(f"Ошибка трека {track_path}:", e)
            return 'NEXT'

    def run(self):
        self.scan_music()

        if not self.playlist:
            self.tft.fill(C_BG)
            self.tft.fill_rect(0, 0, 240, 36, C_HEADER)
            self.tft.text("MUSIC PLAYER", 16, 14, C_WHITE)
            self.tft.text("No .wav tracks found!", 20, 120, C_WHITE)
            self.tft.text("Put WAV tracks in /sd/wav", 20, 150, C_GRAY)
            self.tft.text("Press [ESC] to exit", 20, 280, C_ACCENT)
            self.tft.show()
            while True:
                ev = self.inputs.get_event()
                if ev in ['BACK', 'ENTER']: break
                time.sleep_ms(25)
            return

        # Главный цикл воспроизведения плейлиста
        while True:
            res = self.play_current_track()
            if res == 'EXIT':
                break