#!/usr/bin/env python3
"""
Click Galaxy
Record where you click — watch it become a galaxy map.
Dense click areas form bright star clusters; sparse areas drift like lone stars.

macOS note: on first run, grant Accessibility access when prompted
(System Settings → Privacy & Security → Accessibility).
"""
import sys
import os
import math
import time
import random
import datetime
import threading
import subprocess
import tkinter as tk
from tkinter import messagebox

try:
    from pynput import mouse as pynput_mouse
except ImportError:
    print("Run:  pip install pynput")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:
    print("Run:  pip install Pillow")
    sys.exit(1)


# ── screen size ───────────────────────────────────────────────────────────────

def _screen_size():
    root = tk.Tk()
    w, h = root.winfo_screenwidth(), root.winfo_screenheight()
    root.destroy()
    return w, h

SCREEN_W, SCREEN_H = _screen_size()


# ── mouse tracker ─────────────────────────────────────────────────────────────

class MouseTracker:
    def __init__(self):
        self._lock      = threading.Lock()
        self.clicks:    list[tuple[int, int, str, float]] = []
        self.recording  = False
        self.start_time: float | None = None
        self._listener  = None

    def reset(self):
        with self._lock:
            self.clicks     = []
            self.recording  = False
            self.start_time = None
        self._listener = None

    def _on_click(self, x, y, button, pressed):
        if self.recording and pressed:
            t   = time.time() - self.start_time
            btn = 'left' if button == pynput_mouse.Button.left else 'right'
            with self._lock:
                self.clicks.append((x, y, btn, t))

    def _start_listener(self):
        self._listener = pynput_mouse.Listener(on_click=self._on_click)
        self._listener.start()

    def start(self):
        self.reset()
        self.start_time = time.time()
        self.recording  = True
        self._start_listener()

    def stop(self):
        self.recording = False
        if self._listener:
            self._listener.stop()
            self._listener = None

    def is_listener_alive(self) -> bool:
        return self._listener is not None and self._listener.is_alive()

    def ensure_listener(self):
        """Restart listener if it died unexpectedly while recording."""
        if self.recording and not self.is_listener_alive():
            self._start_listener()
            return False
        return True

    @property
    def elapsed(self) -> float:
        return (time.time() - self.start_time) if self.start_time else 0.0

    def snapshot(self):
        with self._lock:
            return list(self.clicks)


# ── image generation ──────────────────────────────────────────────────────────

def _best_font(size: int):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSText.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def generate_art(clicks, width, height) -> Image.Image:
    rng = random.Random(7)
    BG  = (3, 3, 14)

    img = Image.new("RGBA", (width, height), BG + (255,))

    # ── background star field ─────────────────────────────────────────────────
    bg = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bg)
    for _ in range(2200):
        x = rng.randint(0, width - 1)
        y = rng.randint(0, height - 1)
        a = rng.randint(15, 90)
        if rng.random() < 0.75:
            bd.point((x, y), fill=(190, 205, 255, a))
        else:
            bd.ellipse([x-1, y-1, x+1, y+1], fill=(210, 220, 255, a))
    img = Image.alpha_composite(img, bg)

    if not clicks:
        return img.convert("RGB")

    coords  = [(int(cx), int(cy)) for cx, cy, _, _ in clicks]
    n       = len(coords)
    total_t = clicks[-1][3] if n > 0 else 1.0

    # ── density score: neighbors within 250 px, log-scaled ───────────────────
    # Log scaling handles huge dynamic ranges (10 clicks vs 10 000 clicks)
    RADIUS = 250
    densities = []
    for i, (x1, y1) in enumerate(coords):
        count = sum(
            1 for j, (x2, y2) in enumerate(coords)
            if i != j and math.hypot(x1 - x2, y1 - y2) < RADIUS
        )
        densities.append(count)

    max_d = max(densities) if max(densities) > 0 else 1
    # log1p keeps zeros at 0, compresses the top end so sparse points still show
    norm = [math.log1p(d) / math.log1p(max_d) for d in densities]

    # ── color palette: deep blue (early) → vivid orange-gold (late) ──────────
    def click_color(t_norm: float, alpha: int = 255) -> tuple:
        # t=0 → (30, 90, 255)  t=1 → (255, 160, 20)
        r = int(30  + t_norm * 225)
        g = int(90  + t_norm * 70)
        b = int(255 - t_norm * 235)
        return (r, g, b, alpha)

    # ── nebula glow (blurred clouds behind dots) ──────────────────────────────
    nebula = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    nd     = ImageDraw.Draw(nebula)
    for i, (cx, cy) in enumerate(coords):
        d = norm[i]
        if d < 0.05:
            continue
        t      = clicks[i][3] / total_t
        rc, gc, bc, _ = click_color(t)
        alpha  = int(18 + d * 55)
        radius = int(40 + d * 150)
        nd.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                   fill=(rc, gc, bc, alpha))
    img = Image.alpha_composite(img, nebula.filter(ImageFilter.GaussianBlur(50)))

    # ── satellite micro-dots around dense clusters ────────────────────────────
    sat = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd  = ImageDraw.Draw(sat)
    for i, (cx, cy) in enumerate(coords):
        d      = norm[i]
        n_sats = int(d * 28)
        spread = int(20 + d * 110)
        t      = clicks[i][3] / total_t
        for _ in range(n_sats):
            angle = rng.uniform(0, 2 * math.pi)
            dist  = rng.uniform(5, spread)
            sx    = int(cx + math.cos(angle) * dist)
            sy    = int(cy + math.sin(angle) * dist)
            if not (0 <= sx < width and 0 <= sy < height):
                continue
            a = rng.randint(40, 160)
            rc, gc, bc, _ = click_color(t)
            sd.point((sx, sy), fill=(rc, gc, bc, a))
    img = Image.alpha_composite(img, sat)

    # ── soft per-dot glow (blurred) ───────────────────────────────────────────
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(glow)
    for i, (cx, cy) in enumerate(coords):
        d  = norm[i]
        t  = clicks[i][3] / total_t
        gr = int(5 + d * 14)
        a  = int(60 + d * 120)
        rc, gc, bc, _ = click_color(t)
        gd.ellipse([cx - gr, cy - gr, cx + gr, cy + gr], fill=(rc, gc, bc, a))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(7)))

    # ── actual click dots: plain small circles, no spikes ────────────────────
    dots = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    dt   = ImageDraw.Draw(dots)
    for i, (cx, cy) in enumerate(coords):
        d  = norm[i]
        t  = clicks[i][3] / total_t
        rc, gc, bc, _ = click_color(t)
        # radius 1 for sparse, up to 3 for the densest spots
        cr = max(1, round(1 + d * 2))
        dt.ellipse([cx - cr, cy - cr, cx + cr, cy + cr],
                   fill=(rc, gc, bc, 220))
    img = Image.alpha_composite(img, dots)

    # ── convert to RGB ────────────────────────────────────────────────────────
    final = Image.new("RGB", (width, height), BG)
    final.paste(img, mask=img.split()[3])
    draw  = ImageDraw.Draw(final)

    # ── stats overlay ─────────────────────────────────────────────────────────
    dur     = clicks[-1][3] if clicks else 0
    left_n  = sum(1 for c in clicks if c[2] == 'left')
    right_n = len(clicks) - left_n
    hot     = sum(1 for d in norm if d > 0.5)

    font_title = _best_font(22)
    font_body  = _best_font(15)

    lines = [
        ("Click Galaxy",                                        (255, 220, 70),  font_title),
        (f"Duration   {dur:.1f} s",                             (160, 210, 255), font_body),
        (f"Clicks     {len(clicks)}   (L {left_n}  R {right_n})", (160, 210, 255), font_body),
        (f"Hot spots  {hot}",                                   (160, 210, 255), font_body),
        (datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),    (100, 140, 180), font_body),
    ]

    px, py = 22, 22
    for text, color, font in lines:
        draw.text((px + 1, py + 1), text, fill=(0, 0, 0), font=font)
        draw.text((px,     py),     text, fill=color,      font=font)
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            py += (bbox[3] - bbox[1]) + 7
        except AttributeError:
            py += 22

    # ── legend ────────────────────────────────────────────────────────────────
    lx, ly    = width - 180, height - 80
    font_body2 = _best_font(13)
    draw.ellipse([lx, ly,     lx + 10, ly + 10], fill=(120, 190, 255))
    draw.text((lx + 16, ly - 1),  "Early clicks",  fill=(140, 190, 255), font=font_body2)
    draw.ellipse([lx, ly + 22, lx + 10, ly + 32], fill=(255, 240, 160))
    draw.text((lx + 16, ly + 21), "Late clicks",   fill=(140, 190, 255), font=font_body2)
    draw.ellipse([lx, ly + 44, lx + 10, ly + 54], fill=(180, 100, 255))
    draw.text((lx + 16, ly + 43), "Dense cluster", fill=(140, 190, 255), font=font_body2)

    return final


# ── GUI ───────────────────────────────────────────────────────────────────────

DARK   = "#0d0d1a"
MID    = "#161630"
ACCENT = "#ffdc50"
DIM    = "#556688"
GREEN  = "#1a7a2e"
RED    = "#8b1a1a"
CYAN   = "#44ddff"


class App:
    def __init__(self):
        self.tracker      = MouseTracker()
        self.is_recording = False
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self.root = tk.Tk()
        self.root.title("Click Galaxy")
        self.root.geometry("340x290")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=DARK)

        tk.Label(self.root, text="✦  Click Galaxy  ✦",
                 font=("Helvetica", 17, "bold"),
                 fg=ACCENT, bg=DARK).pack(pady=(18, 3))

        tk.Label(self.root, text="Click anywhere — we'll map it like a galaxy",
                 font=("Helvetica", 10), fg=DIM, bg=DARK).pack()

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self.root, textvariable=self.status_var,
                 font=("Helvetica", 11), fg="#aabbcc", bg=DARK).pack(pady=(12, 2))

        self.timer_var = tk.StringVar(value="00:00")
        tk.Label(self.root, textvariable=self.timer_var,
                 font=("Courier", 26, "bold"), fg=CYAN, bg=DARK).pack()

        self.counter_var = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self.counter_var,
                 font=("Helvetica", 10), fg=DIM, bg=DARK).pack(pady=(2, 0))

        self.btn = tk.Button(
            self.root,
            text="▶   Start Recording",
            font=("Helvetica", 12, "bold"),
            fg="white", bg=GREEN,
            activebackground="#258a37", activeforeground="white",
            relief="flat", padx=24, pady=9,
            command=self.toggle,
            cursor="hand2",
        )
        self.btn.pack(pady=16)

        tk.Label(self.root,
                 text="点击开始后窗口自动最小化\n点击越密集，星团越亮",
                 font=("Helvetica", 9), fg=DIM, bg=DARK, justify="center").pack()

    # ── recording control ─────────────────────────────────────────────────────

    def toggle(self):
        if not self.is_recording:
            self._start()
        else:
            self._stop()

    def _start(self):
        self.is_recording = True
        self.tracker.start()
        self.btn.config(text="■   Stop & Render", bg=RED, activebackground="#aa2222")
        self.status_var.set("Recording  •  click freely!")
        self._tick()
        self.root.after(800, self.root.iconify)

    def _tick(self):
        if not self.is_recording:
            return
        e = self.tracker.elapsed
        self.timer_var.set(f"{int(e//60):02d}:{int(e%60):02d}")
        clk = self.tracker.snapshot()

        alive = self.tracker.ensure_listener()
        if not alive:
            self.status_var.set("⚠️  Interrupted — check Accessibility permission")
        else:
            self.status_var.set("Recording  •  click freely!")

        self.counter_var.set(f"{len(clk)} clicks recorded")
        self.root.after(400, self._tick)

    def _stop(self):
        self.is_recording = False
        self.tracker.stop()
        clicks = self.tracker.snapshot()

        self.btn.config(state="disabled", text="Rendering…", bg=MID)
        self.status_var.set("Generating your galaxy…")
        self.counter_var.set("")

        threading.Thread(target=self._generate, args=(clicks,),
                         daemon=True).start()

    # ── art generation (background thread) ───────────────────────────────────

    def _generate(self, clicks):
        if not clicks:
            self.root.after(0, lambda: messagebox.showinfo(
                "Nothing recorded", "No clicks detected."))
            self.root.after(0, self._reset_ui)
            return

        img  = generate_art(clicks, SCREEN_W, SCREEN_H)
        ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(os.path.expanduser("~/Desktop"), f"click_galaxy_{ts}.png")
        img.save(path)

        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
            elif sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass

        self.root.after(0, lambda: self._done(path, len(clicks)))

    def _done(self, path, n_clk):
        self.status_var.set("Your galaxy is ready!")
        self.timer_var.set("00:00")
        self._reset_ui()
        self.root.deiconify()
        self.root.lift()
        messagebox.showinfo(
            "Click Galaxy Complete!",
            f"Mapped {n_clk} clicks into a galaxy.\n\n"
            f"Saved to Desktop:\n{os.path.basename(path)}\n\n"
            "The image has been opened for you.",
        )

    def _reset_ui(self):
        self.btn.config(state="normal",
                        text="▶   Start Recording", bg=GREEN,
                        activebackground="#258a37")
        self.status_var.set("Ready")
        self.counter_var.set("")

    # ── run ───────────────────────────────────────────────────────────────────

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
