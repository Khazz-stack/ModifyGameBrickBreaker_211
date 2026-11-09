"""
Block Breaker - Neon Edition
============================
Kontrol:
    Panah / A-D / Mouse  gerakkan paddle
    SPACE / klik         luncurkan bola
    P                    jeda
    M                    suara hidup / mati
    ESC                  keluar

Semua efek suara dibuat lewat kode (tanpa file audio).
"""
import array
import math
import random

import pygame

pygame.mixer.pre_init(22050, -16, 1, 512)
pygame.init()


# =============================================================================
# KONFIGURASI
# =============================================================================
WIDTH, HEIGHT = 700, 600
FPS = 60

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Block Breaker - Neon Edition")
clock = pygame.time.Clock()

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GOLD = (255, 215, 0)
RED = (255, 80, 80)
CYAN = (80, 220, 255)
PINK = (255, 120, 220)

# Warna blok per baris
ROW_COLORS = [
    (255, 70, 110),
    (255, 140, 60),
    (255, 220, 70),
    (90, 230, 130),
    (70, 190, 255),
    (170, 110, 255),
]

# Jenis power-up: nama -> (huruf, warna)
POWERUPS = {
    "wide": ("W", CYAN),
    "slow": ("S", GOLD),
    "life": ("+", RED),
    "multi": ("M", PINK),
}


def load_font(size, bold=False):
    try:
        return pygame.font.SysFont("Verdana", size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size + 8)


font_small = load_font(15)
font_med = load_font(22, True)
font_big = load_font(46, True)
font_title = load_font(60, True)


# =============================================================================
# UTILITAS GAMBAR
# =============================================================================
def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def lighten(c, amt):
    return tuple(min(255, v + amt) for v in c)


def darken(c, amt):
    return tuple(max(0, v - amt) for v in c)


def hsv_color(h, s=60, v=100):
    c = pygame.Color(0)
    c.hsva = (h % 360, s, v, 100)
    return (c.r, c.g, c.b)


def draw_text(surface, text, fnt, color, center=None, topleft=None, shadow=True):
    img = fnt.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = center
    if topleft:
        rect.topleft = topleft
    if shadow:
        surface.blit(fnt.render(text, True, BLACK), rect.move(2, 2))
    surface.blit(img, rect)
    return rect


def glow_text(surface, text, fnt, color, center, strength=0.8):
    """Cahaya neon di belakang teks (blur lewat scale down lalu up)."""
    img = fnt.render(text, True, color)
    pad = 24
    w, h = img.get_size()
    base = pygame.Surface((w + pad * 2, h + pad * 2))
    base.blit(img, (pad, pad))
    bw, bh = base.get_size()
    small = pygame.transform.smoothscale(base, (max(1, bw // 6), max(1, bh // 6)))
    blur = pygame.transform.smoothscale(small, (bw, bh))
    k = int(255 * strength * 0.55)
    blur.fill((k, k, k), special_flags=pygame.BLEND_RGB_MULT)
    surface.blit(blur, blur.get_rect(center=(int(center[0]), int(center[1]))),
                 special_flags=pygame.BLEND_RGB_ADD)


def overlay(surface, alpha=170):
    shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    shade.fill((0, 0, 0, alpha))
    surface.blit(shade, (0, 0))


def make_background():
    """Gradasi vertikal, dibuat sekali lalu dipakai ulang tiap frame."""
    bg = pygame.Surface((WIDTH, HEIGHT))
    top, bottom = (12, 10, 40), (4, 4, 14)
    for y in range(HEIGHT):
        pygame.draw.line(bg, lerp_color(top, bottom, y / HEIGHT), (0, y), (WIDTH, y))
    return bg


def make_nebula():
    """Kabut halus: gumpalan gaussian dihitung kecil, lalu diperbesar."""
    sw, sh = 70, 60
    small = pygame.Surface((sw, sh), pygame.SRCALPHA)
    blobs = [(15, 15, 14, (120, 60, 255), 95),
             (55, 20, 15, (0, 150, 255), 85),
             (35, 48, 17, (255, 60, 170), 75)]
    for y in range(sh):
        for x in range(sw):
            r = g = b = a = 0.0
            for bx, by, rad, col, mx in blobs:
                w = math.exp(-((x - bx) ** 2 + (y - by) ** 2) / (2 * (rad * 0.6) ** 2)) * mx
                r += col[0] * w
                g += col[1] * w
                b += col[2] * w
                a += w
            if a > 0:
                small.set_at((x, y), (int(r / a), int(g / a), int(b / a), int(min(a, 110))))
    return pygame.transform.smoothscale(small, (WIDTH + 80, HEIGHT + 80))


BACKGROUND = make_background()
NEBULA = make_nebula()


# =============================================================================
# SUARA (sintesis gelombang sederhana, tanpa file audio)
# =============================================================================
# Soundtrack menu: 8 bar (loop), 128 BPM, kunci A minor (Am - F - C - G)
MENU_BPM = 128
MENU_BARS = 8
MUSIC_NAME = "Neon Drive"
CHORDS = [                      # (nada bass MIDI, triad MIDI)
    (45, (69, 72, 76)),         # Am
    (41, (65, 69, 72)),         # F
    (48, (67, 72, 76)),         # C
    (43, (67, 71, 74)),         # G
]
ARP_PATTERN = (0, 1, 2, 3, 2, 1, 2, 3, 0, 1, 2, 3, 2, 1, 2, 1)
LEAD = [                        # bar 5-8: (langkah 1/16, nada MIDI, panjang langkah)
    [(0, 76, 3), (3, 79, 3), (6, 76, 2), (8, 74, 2), (10, 72, 4)],
    [(0, 77, 3), (3, 76, 3), (6, 72, 2), (8, 69, 4), (12, 72, 4)],
    [(0, 79, 3), (3, 76, 3), (6, 79, 2), (8, 81, 4), (12, 79, 4)],
    [(0, 74, 3), (3, 79, 3), (6, 83, 2), (8, 81, 2), (10, 79, 2), (12, 74, 4)],
]


def midi_freq(m):
    return 440.0 * 2 ** ((m - 69) / 12)


class SoundBank:
    """Membuat efek suara retro saat start, lalu memutarnya dengan play(nama)."""

    def __init__(self):
        self.enabled = False
        self.muted = False
        self.sounds = {}
        self.music = None
        self.beat_seconds = 60.0 / MENU_BPM
        self._music_start = None
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(22050, -16, 1, 512)
            self.rate, fmt, self.channels = pygame.mixer.get_init()
        except pygame.error:
            return  # tidak ada perangkat audio: game tetap jalan tanpa suara
        if fmt != -16:
            return
        self.enabled = True
        pygame.mixer.set_reserved(1)            # channel 0 khusus musik
        self.music_channel = pygame.mixer.Channel(0)
        self._build()
        self._render_track()

    # ---- sintesis ----------------------------------------------------------
    def _tone(self, freq, dur, shape="square", vol=0.4, slide=0.0, decay=4.0):
        """Satu nada. slide = perubahan frekuensi (Hz per detik)."""
        n = int(self.rate * dur)
        fade = self.rate * 0.01
        out, phase = [], 0.0
        for i in range(n):
            t = i / self.rate
            phase += max(20.0, freq + slide * t) / self.rate
            p = phase % 1.0
            if shape == "sine":
                v = math.sin(math.tau * p)
            elif shape == "square":
                v = 1.0 if p < 0.5 else -1.0
            elif shape == "saw":
                v = 2.0 * p - 1.0
            elif shape == "triangle":
                v = 4.0 * abs(p - 0.5) - 1.0
            else:  # noise
                v = random.uniform(-1.0, 1.0)
            env = min(1.0, t / 0.004) * math.exp(-decay * t / dur) * min(1.0, (n - i) / fade)
            out.append(v * env * vol)
        return out

    def _notes(self, notes, shape="square", vol=0.3, decay=3.0):
        """Rangkaian nada berurutan: [(frekuensi, durasi), ...]."""
        out = []
        for freq, dur in notes:
            out.extend(self._tone(freq, dur, shape, vol, decay=decay))
        return out

    def _pcm(self, samples):
        """Ubah sampel float (-1..1) menjadi data PCM 16-bit."""
        ints = [int(max(-1.0, min(1.0, v)) * 32767) for v in samples]
        if self.channels > 1:
            ints = [v for v in ints for _ in range(self.channels)]
        return array.array("h", ints)

    def _make(self, *layers):
        """Campur beberapa lapisan sampel menjadi satu objek Sound."""
        length = max(len(layer) for layer in layers)
        mixed = [sum(layer[i] for layer in layers if i < len(layer)) for i in range(length)]
        return pygame.mixer.Sound(buffer=self._pcm(mixed).tobytes())

    def _build(self):
        tone, notes, make = self._tone, self._notes, self._make
        s = self.sounds

        s["start"] = make(notes([(440, .07), (660, .07), (880, .16)], "square", .28))
        s["launch"] = make(tone(300, .18, "sine", .5, slide=3500, decay=2))
        s["paddle"] = make(tone(260, .09, "triangle", .6, slide=-600, decay=5))
        s["wall"] = make(tone(160, .05, "triangle", .35, decay=6))
        s["hit"] = make(tone(480, .07, "square", .25, slide=-800, decay=5),
                        tone(0, .04, "noise", .12, decay=8))

        # Suara pecah blok naik nadanya sesuai combo (1..5)
        for k in range(1, 6):
            f = 392 * 2 ** ((k - 1) * 2 / 12)
            s[f"break{k}"] = make(tone(f, .14, "square", .3, slide=f * 2, decay=4),
                                  tone(0, .08, "noise", .25, decay=7))

        s["wide"] = make(notes([(330, .06), (440, .06), (550, .14)], "triangle", .5))
        s["slow"] = make(tone(800, .32, "sine", .5, slide=-1500, decay=2))
        s["life"] = make(notes([(523, .08), (784, .08), (1047, .18)], "sine", .5))
        s["multi"] = make(notes([(392, .05), (523, .05), (659, .05),
                                 (784, .05), (988, .05), (1175, .14)], "square", .25))

        s["life_lost"] = make(tone(420, .5, "saw", .35, slide=-700, decay=3),
                              tone(0, .25, "noise", .2, decay=5))
        s["level_up"] = make(notes([(523, .1), (659, .1), (784, .1),
                                    (1047, .1), (784, .08), (1047, .3)], "square", .25))
        s["pause"] = make(notes([(600, .05), (400, .08)], "square", .22))
        s["game_over"] = make(notes([(392, .2), (370, .2), (349, .2), (294, .55)], "saw", .3))
        s["record"] = make(notes([(523, .1), (523, .1), (523, .1),
                                  (659, .2), (784, .45)], "square", .28))

    # ---- soundtrack --------------------------------------------------------
    def _render_track(self):
        """Susun lagu menu 8 bar (loop mulus) dari drum, bass, arp, pad, dan lead."""
        rate = self.rate
        tone = self._tone
        step_n = int(rate * 60.0 / MENU_BPM / 4)        # sampel per nada 1/16
        beat_n = step_n * 4
        bar_n = beat_n * 4
        total = bar_n * MENU_BARS
        self.beat_seconds = beat_n / rate

        drums = [0.0] * total
        music = [0.0] * total      # bass, arp, pad, lead (kena sidechain)
        cache = {}

        def mix(buf, pos, samples, gain=1.0):
            for i, v in enumerate(samples[:max(0, total - pos)], pos):
                buf[i] += v * gain

        def layer(*parts):
            out = [0.0] * max(off + len(smp) for off, smp, _ in parts)
            for off, smp, gain in parts:
                for i, v in enumerate(smp, off):
                    out[i] += v * gain
            return out

        def highpass(x):
            return [x[0]] + [x[i] - x[i - 1] for i in range(1, len(x))]

        def cached(key, make):
            if key not in cache:
                cache[key] = make()
            return cache[key]

        # -- suara drum
        kick = layer((0, tone(150, .3, "sine", .95, slide=-480, decay=5), 1),
                     (0, tone(0, .012, "noise", .35, decay=2), 1))
        hat = highpass(tone(0, .05, "noise", .5, decay=9))
        open_hat = highpass(tone(0, .13, "noise", .4, decay=5))
        burst = tone(0, .2, "noise", .5, decay=8)
        d = int(rate * .012)
        clap = layer((0, burst, 1.0), (d, burst, .8), (d * 2, burst, .9))
        snare = layer((0, tone(0, .12, "noise", .5, decay=8), 1),
                      (0, tone(190, .09, "triangle", .5, decay=6), 1))
        crash = highpass(tone(0, .9, "noise", .35, decay=3.5))
        riser = [random.uniform(-1, 1) * 0.3 * (i / bar_n) ** 2 for i in range(bar_n)]

        # -- suara musikal (di-cache karena pola berulang)
        def bass_note(m):
            f = midi_freq(m)
            return cached(("bass", m), lambda: layer(
                (0, tone(f, .2, "saw", .3, decay=3.5), 1),
                (0, tone(f, .2, "sine", .5, decay=3.5), 1)))

        def arp_note(m):
            return cached(("arp", m), lambda: tone(midi_freq(m), .11, "square", .2, decay=6))

        def pad_note(m):
            return cached(("pad", m), lambda: tone(midi_freq(m), bar_n / rate, "sine", .09, decay=.4))

        def lead_note(m, length):
            dur = length * step_n / rate
            f = midi_freq(m)
            return cached(("lead", m, length), lambda: layer(
                (0, tone(f, dur, "saw", .14, decay=1.6), 1),
                (0, tone(f * 1.01, dur, "saw", .14, decay=1.6), 1)))

        # -- aransemen: intro (bar 1-2) -> drop (3-4) -> lead (5-8) + fill di bar terakhir
        mix(drums, 0, crash)
        for bar in range(MENU_BARS):
            bar_pos = bar * bar_n
            bass_midi, triad = CHORDS[bar % 4]
            arp_notes = list(triad) + [triad[0] + 12]
            last = bar == MENU_BARS - 1

            for st in range(16):
                pos = bar_pos + st * step_n
                if st % 4 == 0:
                    mix(drums, pos, kick)
                if st % 4 == 2:
                    mix(drums, pos, open_hat, .8)
                    mix(music, pos, bass_note(bass_midi))
                elif bar >= 2 and st % 2 == 1:
                    mix(drums, pos, hat, .55)
                if bar >= 2 and st in (4, 12) and not (last and st == 12):
                    mix(drums, pos, clap, .8)
                if bar >= 2:
                    mix(music, pos, arp_note(arp_notes[ARP_PATTERN[st]]))
                if last and st >= 8:
                    mix(drums, pos, snare, .25 + .75 * (st - 8) / 7)

            if bar >= 2:
                for m in triad:
                    mix(music, bar_pos, pad_note(m))
            if bar >= 4:
                for st, m, length in LEAD[bar % 4]:
                    mix(music, bar_pos + st * step_n, lead_note(m, length))
            if last:
                mix(drums, bar_pos, riser)

        # -- sidechain: musik "dipompa" turun tiap kali kick berbunyi
        curve = [0.2 + 0.8 * min(1.0, i / (beat_n * 0.6)) ** 2 for i in range(beat_n)]
        out = [0.0] * total
        for base in range(0, total, beat_n):
            for i in range(beat_n):
                out[base + i] = drums[base + i] * 0.9 + music[base + i] * curve[i]
        fade = int(rate * 0.006)        # ujung loop dipelankan agar tidak berklik
        for i in range(fade):
            out[total - 1 - i] *= i / fade
        peak = max(max(out), -min(out)) or 1.0
        scale = 0.9 / peak
        self.music = pygame.mixer.Sound(buffer=self._pcm([v * scale for v in out]).tobytes())

    MUSIC_VOLUME = 0.55

    def start_music(self):
        """Putar soundtrack menu berulang-ulang."""
        self._music_start = pygame.time.get_ticks()
        if self.enabled and self.music:
            self.music.set_volume(0.0 if self.muted else self.MUSIC_VOLUME)
            self.music_channel.play(self.music, loops=-1)

    def stop_music(self, fade_ms=600):
        if self.enabled:
            self.music_channel.fadeout(fade_ms) if fade_ms else self.music_channel.stop()
        self._music_start = None

    @property
    def music_active(self):
        return self.enabled and not self.muted and self._music_start is not None

    def beat_clock(self):
        """Posisi lagu dalam hitungan beat (desimal), atau None bila musik tidak berjalan."""
        if self._music_start is None:
            return None
        return (pygame.time.get_ticks() - self._music_start) / 1000.0 / self.beat_seconds

    # ---- efek suara --------------------------------------------------------
    def play(self, name):
        if self.enabled and not self.muted:
            self.sounds[name].play()

    def toggle_mute(self):
        self.muted = not self.muted
        if not self.enabled:
            return
        if self.muted:
            for snd in self.sounds.values():
                snd.stop()
        if self.music:
            self.music.set_volume(0.0 if self.muted else self.MUSIC_VOLUME)


# =============================================================================
# EFEK VISUAL
# =============================================================================
class Star:
    """Bintang latar dengan 3 lapis kecepatan (efek parallax)."""

    def __init__(self):
        self.x = random.uniform(0, WIDTH)
        self.y = random.uniform(0, HEIGHT)
        self.layer = random.choice([1, 2, 3])
        self.speed = self.layer * 0.15
        self.size = self.layer
        b = 70 + self.layer * 45
        self.color = (b, b, min(255, b + 30))

    def update(self):
        self.y += self.speed
        if self.y > HEIGHT:
            self.y = 0
            self.x = random.uniform(0, WIDTH)

    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.size)


class Particle:
    def __init__(self, x, y, color):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(1.5, 5.5)
        self.x, self.y = x, y
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = self.max_life = random.randint(25, 45)
        self.size = random.uniform(2, 5)
        self.color = color

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.12  # gravitasi
        self.life -= 1

    def draw(self, surface):
        t = self.life / self.max_life
        pygame.draw.circle(surface, lerp_color(BLACK, self.color, t),
                           (int(self.x), int(self.y)), max(1, int(self.size * t)))


class FloatingText:
    LIFE = 50

    def __init__(self, text, x, y, color):
        self.text, self.x, self.y, self.color = text, x, y, color
        self.life = self.LIFE

    def update(self):
        self.y -= 0.8
        self.life -= 1

    def draw(self, surface):
        img = font_small.render(self.text, True, self.color)
        img.set_alpha(int(255 * self.life / self.LIFE))
        surface.blit(img, img.get_rect(center=(self.x, self.y)))


class ShootingStar:
    """Bintang jatuh untuk latar menu."""

    def __init__(self):
        self.x = random.uniform(150, WIDTH + 100)
        self.y = random.uniform(-20, 220)
        self.vx = -random.uniform(8, 12)
        self.vy = random.uniform(4, 7)
        self.life = 40

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1

    def draw(self, surface):
        fade = self.life / 40
        for i in range(12):
            t = i / 12
            pos = (int(self.x - self.vx * i * 0.6), int(self.y - self.vy * i * 0.6))
            pygame.draw.circle(surface, lerp_color(BLACK, WHITE, (1 - t) * fade),
                               pos, max(1, int(3 * (1 - t))))


class FloatingBlock:
    """Blok transparan yang melayang naik di latar menu."""

    def __init__(self):
        self.w, self.h = 50, 22
        self.x = random.uniform(0, WIDTH)
        self.y = random.uniform(0, HEIGHT)
        self.vy = -random.uniform(0.2, 0.6)
        self.phase = random.uniform(0, math.tau)
        self.color = random.choice(ROW_COLORS)
        self.cx = self.x

    def update(self, t):
        self.y += self.vy
        if self.y < -40:
            self.y = HEIGHT + 40
            self.x = random.uniform(0, WIDTH)
        self.cx = self.x + math.sin(t + self.phase) * 14

    def draw(self, layer):
        r = pygame.Rect(0, 0, self.w, self.h)
        r.center = (int(self.cx), int(self.y))
        pygame.draw.rect(layer, (*self.color, 55), r, border_radius=5)
        pygame.draw.rect(layer, (*lighten(self.color, 60), 130), r, 2, border_radius=5)


class DemoBall:
    """Bola dekoratif yang memantul di latar menu."""

    def __init__(self):
        self.x, self.y = WIDTH / 2, HEIGHT / 2
        self.vx, self.vy = 3.4, 2.8
        self.trail = []

    def update(self):
        self.trail.append((self.x, self.y))
        if len(self.trail) > 22:
            self.trail.pop(0)
        self.x += self.vx
        self.y += self.vy
        if self.x < 10 or self.x > WIDTH - 10:
            self.vx *= -1
        if self.y < 10 or self.y > HEIGHT - 10:
            self.vy *= -1

    def draw(self, surface):
        for i, (tx, ty) in enumerate(self.trail):
            t = (i + 1) / len(self.trail)
            pygame.draw.circle(surface, lerp_color(BLACK, (110, 200, 255), t * 0.55),
                               (int(tx), int(ty)), max(1, int(7 * t)))
        glow = pygame.Surface((60, 60), pygame.SRCALPHA)
        pygame.draw.circle(glow, (150, 220, 255, 40), (30, 30), 26)
        pygame.draw.circle(glow, (150, 220, 255, 70), (30, 30), 16)
        surface.blit(glow, glow.get_rect(center=(int(self.x), int(self.y))))
        pygame.draw.circle(surface, WHITE, (int(self.x), int(self.y)), 7)


# =============================================================================
# OBJEK PERMAINAN
# =============================================================================
class Striker:
    """Paddle pemain."""

    BASE_WIDTH = 110
    SPEED = 12                  # kecepatan paddle saat memakai keyboard

    def __init__(self):
        self.width = self.BASE_WIDTH
        self.height = 16
        self.speed = self.SPEED
        self.posx = WIDTH / 2 - self.width / 2
        self.posy = HEIGHT - 50
        self.rect = pygame.Rect(self.posx, self.posy, self.width, self.height)
        self.wide_timer = 0

    def update(self, direction, mouse_x=None):
        if mouse_x is not None:
            self.posx = mouse_x - self.width / 2
        else:
            self.posx += self.speed * direction

        # Lebar paddle bergerak halus menuju target (power-up lebar)
        target = self.BASE_WIDTH * 1.6 if self.wide_timer > 0 else self.BASE_WIDTH
        center = self.posx + self.width / 2
        self.width += (target - self.width) * 0.15
        self.posx = center - self.width / 2
        self.wide_timer = max(0, self.wide_timer - 1)

        self.posx = max(0, min(WIDTH - self.width, self.posx))
        self.rect = pygame.Rect(int(self.posx), self.posy, int(self.width), self.height)

    def draw(self, surface):
        glow = pygame.Surface((self.rect.width + 40, self.height + 30), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (80, 200, 255, 50), glow.get_rect())
        surface.blit(glow, (self.rect.x - 20, self.rect.y - 10))

        pygame.draw.rect(surface, (40, 120, 200), self.rect, border_radius=8)
        top = pygame.Rect(self.rect.x, self.rect.y, self.rect.width, self.height // 2 + 2)
        pygame.draw.rect(surface, CYAN, top, border_radius=8)
        pygame.draw.rect(surface, WHITE, self.rect, 2, border_radius=8)


class Block:
    def __init__(self, x, y, w, h, color, hp):
        self.rect = pygame.Rect(x, y, w, h)
        self.color = color
        self.max_hp = hp
        self.hp = hp
        self.flash = 0

    def hit(self):
        self.hp -= 1
        self.flash = 6

    def draw(self, surface):
        base = self.color
        if self.max_hp > 1:
            # Blok kuat berwarna metalik, makin berwarna saat HP berkurang
            base = lerp_color((150, 150, 165), self.color, 1 - (self.hp - 1) / self.max_hp)
        if self.flash > 0:
            base = lighten(base, 80)
            self.flash -= 1

        pygame.draw.rect(surface, darken(base, 70), self.rect, border_radius=5)
        inner = self.rect.inflate(-2, -2)
        pygame.draw.rect(surface, base, inner, border_radius=5)
        shine = pygame.Rect(inner.x + 2, inner.y + 2, inner.width - 4, inner.height // 2 - 1)
        pygame.draw.rect(surface, lighten(base, 55), shine, border_radius=4)

        if self.hp < self.max_hp:  # retakan
            cx, cy = self.rect.center
            pygame.draw.lines(surface, darken(base, 110), False,
                              [(cx - 8, cy - 6), (cx - 2, cy), (cx - 6, cy + 2), (cx + 2, cy + 6)], 2)


class PowerUp:
    def __init__(self, x, y, kind):
        self.kind = kind
        self.x, self.y = x, y
        self.rect = pygame.Rect(0, 0, 28, 28)
        self.rect.center = (x, y)
        self.t = 0

    def update(self):
        self.y += 2.5
        self.t += 0.15
        self.rect.center = (self.x + math.sin(self.t) * 4, self.y)

    def draw(self, surface):
        letter, color = POWERUPS[self.kind]
        pygame.draw.rect(surface, darken(color, 90), self.rect, border_radius=8)
        pygame.draw.rect(surface, color, self.rect, 3, border_radius=8)
        draw_text(surface, letter, font_small, WHITE, center=self.rect.center, shadow=False)


class Ball:
    RADIUS = 8

    def __init__(self):
        self.radius = self.RADIUS
        self.trail = []
        self.hit_wall = False
        self.reset()

    def reset(self):
        """Bola menempel di paddle sampai diluncurkan."""
        self.posx = WIDTH / 2
        self.posy = HEIGHT - 70
        self.vx = self.vy = 0.0
        self.stuck = True
        self.trail.clear()

    def launch(self, speed):
        angle = math.radians(random.uniform(-25, 25))
        self.vx = math.sin(angle) * speed
        self.vy = -math.cos(angle) * speed
        self.stuck = False

    def set_speed(self, speed):
        cur = math.hypot(self.vx, self.vy)
        if cur > 0:
            self.vx, self.vy = self.vx / cur * speed, self.vy / cur * speed

    def split(self, angle_deg):
        """Bola baru dari bola ini, arahnya diputar beberapa derajat."""
        b = Ball()
        b.posx, b.posy = self.posx, self.posy
        a = math.radians(angle_deg)
        b.vx = self.vx * math.cos(a) - self.vy * math.sin(a)
        b.vy = self.vx * math.sin(a) + self.vy * math.cos(a)
        if abs(b.vy) < 1.5:  # hindari lintasan yang terlalu datar
            b.vy = -1.5 if b.vy <= 0 else 1.5
        b.set_speed(math.hypot(self.vx, self.vy))
        b.stuck = False
        return b

    def update(self, striker):
        """Gerakkan bola. Return True bila bola jatuh ke bawah layar."""
        self.hit_wall = False
        if self.stuck:
            self.posx = striker.rect.centerx
            self.posy = striker.rect.top - self.radius - 1
            return False

        self.trail.append((self.posx, self.posy))
        if len(self.trail) > 14:
            self.trail.pop(0)

        self.posx += self.vx
        self.posy += self.vy

        if self.posx - self.radius <= 0:
            self.posx, self.vx, self.hit_wall = self.radius, abs(self.vx), True
        elif self.posx + self.radius >= WIDTH:
            self.posx, self.vx, self.hit_wall = WIDTH - self.radius, -abs(self.vx), True
        if self.posy - self.radius <= 0:
            self.posy, self.vy, self.hit_wall = self.radius, abs(self.vy), True

        return self.posy - self.radius > HEIGHT

    def get_rect(self):
        return pygame.Rect(self.posx - self.radius, self.posy - self.radius,
                           self.radius * 2, self.radius * 2)

    def draw(self, surface):
        for i, (tx, ty) in enumerate(self.trail):
            t = (i + 1) / len(self.trail)
            pygame.draw.circle(surface, lerp_color(BLACK, (120, 200, 255), t * 0.6),
                               (int(tx), int(ty)), max(1, int(self.radius * t * 0.8)))
        glow = pygame.Surface((self.radius * 6, self.radius * 6), pygame.SRCALPHA)
        for r, a in ((self.radius * 3, 25), (self.radius * 2, 45)):
            pygame.draw.circle(glow, (150, 220, 255, a), glow.get_rect().center, r)
        pos = (int(self.posx), int(self.posy))
        surface.blit(glow, glow.get_rect(center=pos))
        pygame.draw.circle(surface, WHITE, pos, self.radius)
        pygame.draw.circle(surface, CYAN, pos, self.radius, 2)


def build_level(level):
    """Susun blok untuk level tertentu (pola dan kekuatan blok berubah tiap level)."""
    blocks = []
    cols, gap, margin, bh = 10, 6, 30, 22
    bw = (WIDTH - margin * 2 - gap * (cols - 1)) // cols
    rows = min(4 + level, 8)
    for r in range(rows):
        for c in range(cols):
            if level % 3 == 2 and (r + c) % 5 == 0:
                continue
            if level % 3 == 0 and c in (4, 5) and r % 2 == 1:
                continue
            roll = random.random()
            hp = 1
            if roll < 0.12 + level * 0.02:
                hp = 3
            elif roll < 0.35 + level * 0.03:
                hp = 2
            x = margin + c * (bw + gap)
            y = 70 + r * (bh + gap)
            blocks.append(Block(x, y, bw, bh, ROW_COLORS[r % len(ROW_COLORS)], hp))
    return blocks


# =============================================================================
# LAYAR MENU
# =============================================================================
def wave_title(surface, text, fnt, center, t):
    """Judul dengan huruf bergelombang dan warna bergradasi."""
    spacing = 3
    widths = [fnt.size(ch)[0] for ch in text]
    x = center[0] - (sum(widths) + spacing * (len(text) - 1)) / 2
    for i, ch in enumerate(text):
        cx = x + widths[i] / 2
        cy = center[1] + math.sin(t * 3 + i * 0.5) * 8
        if ch != " ":
            color = hsv_color(190 + 100 * (math.sin(t + i * 0.35) + 1) / 2, 60, 100)
            glow_text(surface, ch, fnt, color, (cx, cy), 0.9)
            draw_text(surface, ch, fnt, color, center=(cx, cy))
        x += widths[i] + spacing


def draw_divider(surface, y):
    """Garis hias emas yang memudar di kiri dan kanan subjudul."""
    for side in (-1, 1):
        for i in range(60):
            a = 1 - i / 60
            x = WIDTH // 2 + side * (110 + i)
            surface.set_at((x, y), lerp_color(BLACK, GOLD, a))
            surface.set_at((x, y + 1), lerp_color(BLACK, GOLD, a * 0.5))


def draw_keycap(surface, label, x, y):
    img = font_small.render(label, True, WHITE)
    rect = pygame.Rect(x, y, img.get_width() + 18, 28)
    pygame.draw.rect(surface, (20, 20, 45), rect.move(0, 3), border_radius=6)
    pygame.draw.rect(surface, (55, 60, 110), rect, border_radius=6)
    pygame.draw.rect(surface, CYAN, rect, 1, border_radius=6)
    surface.blit(img, img.get_rect(center=rect.center))
    return rect.width


def draw_controls(surface, y):
    items = [(["<", ">"], "Gerak"), (["SPACE"], "Luncur"), (["P"], "Jeda"),
             (["M"], "Suara"), (["ESC"], "Keluar")]

    def item_width(keys, label):
        keys_w = sum(font_small.size(k)[0] + 18 + 6 for k in keys)
        return keys_w + font_small.size(label)[0] + 8

    total = sum(item_width(k, l) for k, l in items) + 24 * (len(items) - 1)
    x = WIDTH // 2 - total / 2
    for keys, label in items:
        for k in keys:
            x += draw_keycap(surface, k, x, y) + 6
        txt = draw_text(surface, label, font_small, (180, 185, 220),
                        topleft=(x + 2, y + 4), shadow=False)
        x = txt.right + 24


def draw_start_button(surface, btn, pulse, hover):
    glow = pygame.Surface((btn.width + 60, btn.height + 60), pygame.SRCALPHA)
    alpha = int(25 + 55 * pulse + (30 if hover else 0))
    pygame.draw.rect(glow, (90, 200, 255, alpha), glow.get_rect(), border_radius=30)
    surface.blit(glow, glow.get_rect(center=btn.center))
    pygame.draw.rect(surface, (14, 16, 48), btn, border_radius=16)
    pygame.draw.rect(surface, lerp_color((60, 160, 255), PINK, pulse), btn, 3, border_radius=16)
    if hover:
        pygame.draw.rect(surface, WHITE, btn.inflate(-8, -8), 1, border_radius=12)
    draw_text(surface, "MULAI MAIN", font_med, WHITE, center=(btn.centerx, btn.centery - 8))
    draw_text(surface, "[SPACE]", font_small, (150, 200, 255),
              center=(btn.centerx, btn.centery + 16), shadow=False)


def draw_high_score_panel(surface, high_score, center):
    panel = pygame.Rect(0, 0, 260, 44)
    panel.center = center
    box = pygame.Surface(panel.size, pygame.SRCALPHA)
    pygame.draw.rect(box, (255, 215, 0, 25), box.get_rect(), border_radius=12)
    pygame.draw.rect(box, (255, 215, 0, 160), box.get_rect(), 2, border_radius=12)
    surface.blit(box, panel)
    draw_text(surface, f"HIGH SCORE   {high_score}", font_small, GOLD, center=panel.center)


class MenuBackdrop:
    """Latar animasi menu: nebula, bintang, bintang jatuh, blok melayang, bola demo."""

    def __init__(self, stars):
        self.stars = stars
        self.blocks = [FloatingBlock() for _ in range(14)]
        self.demo = DemoBall()
        self.shooters = []
        self.layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    def draw(self, surface, t, beats=None):
        surface.blit(BACKGROUND, (0, 0))
        surface.blit(NEBULA, (-40 + math.sin(t * 0.6) * 25, -40 + math.cos(t * 0.5) * 20))
        for s in self.stars:
            s.update()
            s.draw(surface)

        if random.random() < 0.012:
            self.shooters.append(ShootingStar())
        for sh in self.shooters[:]:
            sh.update()
            sh.draw(surface)
            if sh.life <= 0:
                self.shooters.remove(sh)

        self.layer.fill((0, 0, 0, 0))
        if beats is not None:  # gelombang cahaya yang melebar tiap beat
            color = hsv_color(190 + 15 * (int(beats // 4) % MENU_BARS))
            for shift in (0.0, 0.5):
                phase = (beats + shift) % 1.0
                alpha = int(120 * (1 - phase) ** 1.5)
                pygame.draw.circle(self.layer, (*color, alpha), (WIDTH // 2, 330),
                                   int(30 + phase * 420), 3)
        for b in self.blocks:
            b.update(t * 2)
            b.draw(self.layer)
        surface.blit(self.layer, (0, 0))

        self.demo.update()
        self.demo.draw(surface)


def draw_equalizer(surface, t, kick, baseline=512):
    """Equalizer dekoratif yang melonjak mengikuti kick."""
    bars, bar_w, gap = 32, 8, 4
    x0 = WIDTH // 2 - (bars * (bar_w + gap) - gap) // 2
    for i in range(bars):
        wobble = abs(math.sin(t * 3.1 + i * 0.55) * math.sin(t * 1.7 + i * 0.31))
        h = 6 + 38 * (0.3 + 0.7 * wobble) * (0.5 + 0.5 * kick)
        rect = pygame.Rect(x0 + i * (bar_w + gap), baseline - h, bar_w, h)
        pygame.draw.rect(surface, lerp_color(CYAN, PINK, i / (bars - 1)), rect, border_radius=3)


def menu_screen(stars, sound, high_score):
    """Return True untuk mulai main, False untuk keluar."""
    backdrop = MenuBackdrop(stars)
    btn = pygame.Rect(0, 0, 330, 64)
    btn.center = (WIDTH // 2, 350)
    t = 0.0
    sound.start_music()

    while True:
        hover = btn.collidepoint(pygame.mouse.get_pos())
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                sound.stop_music(0)
                return False
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_SPACE, pygame.K_RETURN):
                    sound.play("start")
                    sound.stop_music(800)
                    return True
                if e.key == pygame.K_m:
                    sound.toggle_mute()
                if e.key == pygame.K_ESCAPE:
                    sound.stop_music(0)
                    return False
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and hover:
                sound.play("start")
                sound.stop_music(800)
                return True

        t += 0.03
        beats = sound.beat_clock() if sound.music_active else None
        if beats is not None:
            kick = (1 - beats % 1) ** 3          # 1.0 tepat di ketukan, lalu meluruh
            pulse = 0.25 + 0.75 * kick
        else:
            kick = 0.0
            pulse = (math.sin(t * 6) + 1) / 2

        backdrop.draw(screen, t, beats)
        wave_title(screen, "BLOCK BREAKER", font_title, (WIDTH // 2, 140), t)
        glow_text(screen, "NEON EDITION", font_med, GOLD, (WIDTH // 2, 205), 0.6)
        draw_text(screen, "NEON EDITION", font_med, GOLD, center=(WIDTH // 2, 205))
        draw_divider(screen, 205)
        draw_start_button(screen, btn, pulse, hover)
        draw_high_score_panel(screen, high_score, (WIDTH // 2, 440))
        if beats is not None:
            draw_equalizer(screen, t, kick)
        draw_controls(screen, HEIGHT - 60)

        if sound.muted:
            draw_text(screen, "SUARA MATI  -  tekan [M] untuk menyalakan", font_small,
                      (150, 150, 180), center=(WIDTH // 2, 24))
        elif beats is not None:
            draw_text(screen, f"NOW PLAYING   {MUSIC_NAME}   {MENU_BPM} BPM", font_small,
                      (170, 180, 235), center=(WIDTH // 2, 24))

        pygame.display.flip()
        clock.tick(FPS)


def game_over_screen(stars, sound, score, high_score, new_record):
    """Return True untuk main lagi, False untuk keluar."""
    sound.play("record" if new_record else "game_over")
    t = 0.0
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_SPACE:
                    return True
                if e.key == pygame.K_m:
                    sound.toggle_mute()
                if e.key == pygame.K_ESCAPE:
                    return False
        t += 0.05
        screen.blit(BACKGROUND, (0, 0))
        for s in stars:
            s.update()
            s.draw(screen)
        overlay(screen, 120)

        draw_text(screen, "GAME OVER", font_big, RED, center=(WIDTH // 2, 190))
        draw_text(screen, f"Skor: {score}", font_med, WHITE, center=(WIDTH // 2, 265))
        if new_record:
            draw_text(screen, "REKOR BARU!", font_med, GOLD,
                      center=(WIDTH // 2, 305 + math.sin(t * 4) * 3))
        else:
            draw_text(screen, f"High Score: {high_score}", font_small, GOLD,
                      center=(WIDTH // 2, 305))
        draw_text(screen, "[SPACE] Main Lagi     [ESC] Keluar", font_small, WHITE,
                  center=(WIDTH // 2, 380))

        pygame.display.flip()
        clock.tick(FPS)


# =============================================================================
# PERMAINAN
# =============================================================================
class Game:
    """Satu sesi permainan: dari bola pertama sampai nyawa habis."""

    START_LIVES = 3
    MAX_LIVES = 5
    MAX_BALLS = 9
    DROP_CHANCE = 0.15          # peluang blok pecah menjatuhkan power-up
    BASE_BALL_SPEED = 9         # kecepatan bola di level 1 (piksel per frame)
    LEVEL_SPEED_STEP = 0.6      # tambahan kecepatan tiap naik level
    MAX_BALL_SPEED = 14         # batas atas supaya bola tidak menembus blok
    WIDE_FRAMES = FPS * 10
    SLOW_FRAMES = FPS * 8
    BANNER_FRAMES = 120

    LEFT_KEYS = (pygame.K_LEFT, pygame.K_a)
    RIGHT_KEYS = (pygame.K_RIGHT, pygame.K_d)

    def __init__(self, stars, sound, high_score):
        self.stars = stars
        self.sound = sound
        self.high_score = high_score
        self.canvas = pygame.Surface((WIDTH, HEIGHT))

        self.striker = Striker()
        self.balls = [Ball()]
        self.blocks = build_level(1)
        self.powerups, self.particles, self.floats = [], [], []

        self.lives = self.START_LIVES
        self.score = 0
        self.level = 1
        self.combo = 0
        self.slow_timer = 0
        self.shake = 0
        self.banner = self.BANNER_FRAMES

        self.paused = False
        self.game_over = False
        self.direction = 0
        self.use_mouse = False

    # ---- loop utama --------------------------------------------------------
    def run(self):
        """Return (skor, high_score, rekor_baru), atau None bila pemain keluar."""
        while True:
            if not self.handle_events():
                return None
            self.update()
            if self.game_over:
                return self.score, max(self.score, self.high_score), self.score > self.high_score
            self.draw()
            pygame.display.flip()
            clock.tick(FPS)

    # ---- input -------------------------------------------------------------
    def handle_events(self):
        """Return False bila pemain ingin keluar."""
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            if e.type == pygame.KEYDOWN:
                if e.key in self.LEFT_KEYS:
                    self.direction, self.use_mouse = -1, False
                elif e.key in self.RIGHT_KEYS:
                    self.direction, self.use_mouse = 1, False
                elif e.key == pygame.K_SPACE:
                    self.launch()
                elif e.key == pygame.K_p:
                    self.paused = not self.paused
                    self.sound.play("pause")
                elif e.key == pygame.K_m:
                    self.sound.toggle_mute()
                elif e.key == pygame.K_ESCAPE:
                    return False
            elif e.type == pygame.KEYUP:
                if e.key in self.LEFT_KEYS and self.direction == -1:
                    self.direction = 0
                elif e.key in self.RIGHT_KEYS and self.direction == 1:
                    self.direction = 0
            elif e.type == pygame.MOUSEMOTION:
                self.use_mouse = True
            elif e.type == pygame.MOUSEBUTTONDOWN:
                self.launch()
        return True

    def launch(self):
        if self.paused:
            return
        stuck = [b for b in self.balls if b.stuck]
        for ball in stuck:
            ball.launch(self.ball_speed())
        if stuck:
            self.sound.play("launch")

    def ball_speed(self):
        base = self.BASE_BALL_SPEED + (self.level - 1) * self.LEVEL_SPEED_STEP
        base = min(base, self.MAX_BALL_SPEED)
        return base * (0.7 if self.slow_timer > 0 else 1.0)

    # ---- update ------------------------------------------------------------
    def update(self):
        for s in self.stars:
            s.update()
        if self.paused:
            return

        mouse_x = pygame.mouse.get_pos()[0] if self.use_mouse else None
        self.striker.update(self.direction, mouse_x)

        self.update_balls()
        if self.game_over:
            return
        self.update_powerups()
        self.check_level_clear()
        self.update_effects()

    def update_balls(self):
        for ball in self.balls[:]:
            if ball.update(self.striker):
                self.balls.remove(ball)
            elif ball.hit_wall:
                self.sound.play("wall")

        if self.slow_timer > 0:
            self.slow_timer -= 1
            if self.slow_timer == 0:
                self.apply_ball_speed()

        if not self.balls:  # semua bola jatuh
            self.lose_life()
            return

        for ball in self.balls:
            self.bounce_on_striker(ball)
            self.collide_blocks(ball)

    def apply_ball_speed(self):
        for ball in self.balls:
            if not ball.stuck:
                ball.set_speed(self.ball_speed())

    def lose_life(self):
        self.lives -= 1
        self.combo = 0
        self.shake = 14
        self.powerups.clear()
        if self.lives <= 0:
            self.game_over = True
        else:
            self.balls = [Ball()]
            self.sound.play("life_lost")

    def bounce_on_striker(self, ball):
        striker = self.striker
        if ball.stuck or ball.vy <= 0 or not striker.rect.colliderect(ball.get_rect()):
            return
        # Sudut pantul ditentukan oleh posisi benturan di paddle
        offset = (ball.posx - striker.rect.centerx) / (striker.rect.width / 2)
        offset = max(-0.95, min(0.95, offset))
        speed = self.ball_speed()
        ball.vx = offset * speed * 0.9
        ball.vy = -math.sqrt(max(speed ** 2 - ball.vx ** 2, 1))
        ball.posy = striker.rect.top - ball.radius
        self.combo = 0
        self.sound.play("paddle")

    def collide_blocks(self, ball):
        rect = ball.get_rect()
        for block in self.blocks:
            if not rect.colliderect(block.rect):
                continue
            # Sisi tabrakan ditentukan dari overlap terkecil
            dx = min(rect.right - block.rect.left, block.rect.right - rect.left)
            dy = min(rect.bottom - block.rect.top, block.rect.bottom - rect.top)
            if dx < dy:
                ball.vx *= -1
            else:
                ball.vy *= -1

            block.hit()
            if block.hp <= 0:
                self.destroy_block(block)
            else:
                self.score += 2
                self.sound.play("hit")
            return  # satu blok per bola per frame

    def destroy_block(self, block):
        self.blocks.remove(block)
        self.combo += 1
        gained = 10 * block.max_hp * min(self.combo, 5)
        self.score += gained
        self.shake = max(self.shake, 4)

        for _ in range(16):
            self.particles.append(Particle(*block.rect.center, block.color))
        label = f"+{gained}" + (f"  x{self.combo}" if self.combo > 1 else "")
        self.floats.append(FloatingText(label, *block.rect.center, WHITE))
        self.sound.play(f"break{min(self.combo, 5)}")

        if random.random() < self.DROP_CHANCE:
            self.powerups.append(PowerUp(*block.rect.center, random.choice(list(POWERUPS))))

    def update_powerups(self):
        for p in self.powerups[:]:
            p.update()
            if p.rect.colliderect(self.striker.rect):
                self.powerups.remove(p)
                self.apply_powerup(p.kind)
            elif p.y > HEIGHT + 20:
                self.powerups.remove(p)

    def apply_powerup(self, kind):
        if kind == "wide":
            self.striker.wide_timer = self.WIDE_FRAMES
            text = "PADDLE LEBAR!"
        elif kind == "slow":
            self.slow_timer = self.SLOW_FRAMES
            self.apply_ball_speed()
            text = "BOLA LAMBAT!"
        elif kind == "life":
            self.lives = min(self.lives + 1, self.MAX_LIVES)
            text = "NYAWA +1"
        else:  # multi
            self.split_balls()
            text = "MULTI BOLA!"

        color = POWERUPS[kind][1]
        self.floats.append(FloatingText(text, self.striker.rect.centerx,
                                        self.striker.rect.top - 20, color))
        self.sound.play(kind)

    def split_balls(self):
        """Tiap bola yang melaju terbelah menjadi tiga (dibatasi MAX_BALLS)."""
        extra = []
        for ball in self.balls:
            if not ball.stuck:
                extra.append(ball.split(-24))
                extra.append(ball.split(24))
        self.balls.extend(extra[:max(0, self.MAX_BALLS - len(self.balls))])

    def check_level_clear(self):
        if self.blocks:
            return
        self.level += 1
        self.blocks = build_level(self.level)
        self.balls = [Ball()]
        self.powerups.clear()
        self.banner = self.BANNER_FRAMES
        self.score += 100 * (self.level - 1)
        self.sound.play("level_up")

    def update_effects(self):
        for fx in self.particles + self.floats:
            fx.update()
        self.particles = [p for p in self.particles if p.life > 0]
        self.floats = [f for f in self.floats if f.life > 0]
        self.shake = max(0, self.shake - 1)
        self.banner = max(0, self.banner - 1)

    # ---- gambar ------------------------------------------------------------
    def draw(self):
        c = self.canvas
        c.blit(BACKGROUND, (0, 0))
        for s in self.stars:
            s.draw(c)
        for obj in self.blocks + self.powerups:
            obj.draw(c)
        self.striker.draw(c)
        for ball in self.balls:
            ball.draw(c)
        for fx in self.particles + self.floats:
            fx.draw(c)

        self.draw_hud(c)
        if self.paused:
            overlay(c, 150)
            draw_text(c, "JEDA", font_big, WHITE, center=(WIDTH // 2, HEIGHT // 2))
            draw_text(c, "Tekan [P] untuk lanjut", font_small, WHITE,
                      center=(WIDTH // 2, HEIGHT // 2 + 50))

        # Screen shake
        s = self.shake
        ox = random.randint(-s, s) if s else 0
        oy = random.randint(-s, s) if s else 0
        screen.fill(BLACK)
        screen.blit(c, (ox, oy))

    def draw_hud(self, c):
        pygame.draw.line(c, (50, 50, 90), (0, 45), (WIDTH, 45), 1)
        draw_text(c, f"SKOR  {self.score}", font_small, WHITE, topleft=(20, 14))
        draw_text(c, f"LEVEL {self.level}", font_small, CYAN, center=(WIDTH // 2, 25))
        for i in range(self.lives):
            pos = (WIDTH - 30 - i * 24, 25)
            pygame.draw.circle(c, RED, pos, 8)
            pygame.draw.circle(c, WHITE, pos, 8, 2)

        # Status power-up aktif (kiri bawah) dan suara (kanan bawah)
        x = 20
        statuses = []
        if self.slow_timer > 0:
            statuses.append(("SLOW", GOLD))
        if self.striker.wide_timer > 0:
            statuses.append(("WIDE", CYAN))
        if len(self.balls) > 1:
            statuses.append((f"BOLA x{len(self.balls)}", PINK))
        for text, color in statuses:
            rect = draw_text(c, text, font_small, color, topleft=(x, HEIGHT - 28))
            x = rect.right + 18
        if self.sound.muted:
            draw_text(c, "MUTE", font_small, (150, 150, 180), topleft=(WIDTH - 70, HEIGHT - 28))

        if any(b.stuck for b in self.balls) and not self.paused and self.banner <= 0:
            draw_text(c, "Tekan [SPACE] untuk meluncurkan bola", font_small,
                      (200, 200, 230), center=(WIDTH // 2, HEIGHT // 2 + 60))

        if self.banner > 0:
            txt = font_big.render(f"LEVEL {self.level}", True, GOLD)
            txt.set_alpha(min(255, self.banner * 6))
            c.blit(txt, txt.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 40)))


# =============================================================================
# MAIN
# =============================================================================
def show_loading():
    screen.blit(BACKGROUND, (0, 0))
    draw_text(screen, "Memuat suara...", font_med, WHITE, center=(WIDTH // 2, HEIGHT // 2))
    pygame.display.flip()


def main():
    stars = [Star() for _ in range(90)]
    show_loading()
    sound = SoundBank()
    high_score = 0

    if menu_screen(stars, sound, high_score):
        while True:
            result = Game(stars, sound, high_score).run()
            if result is None:
                break
            score, high_score, new_record = result
            if not game_over_screen(stars, sound, score, high_score, new_record):
                break

    pygame.quit()


if __name__ == "__main__":
    main()