#!/usr/bin/env python3
"""
Mouse Painter
Record your mouse journey, then watch it turn into glowing art.

macOS note: on first run, grant Accessibility access when prompted
(System Settings → Privacy & Security → Accessibility).
"""
import sys
import os
import math
import time
import colorsys
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
        self.positions: list[tuple[int, int, float]]       = []
        self.clicks:    list[tuple[int, int, str, float]]  = []
        self.recording  = False
        self.start_time: float | None = None
        self._listener  = None

    def reset(self):
        with self._lock:
            self.positions  = []
            self.clicks     = []
            self.recording  = False
            self.start_time = None
        self._listener = None

    def _on_move(self, x, y):
        if self.recording:
            t = time.time() - self.start_time
            with self._lock:
                self.positions.append((x, y, t))

    def _on_click(self, x, y, button, pressed):
        if self.recording and pressed:
            t   = time.time() - self.start_time
            btn = 'left' if button == pynput_mouse.Button.left else 'right'
            with self._lock:
                self.clicks.append((x, y, btn, t))

    def _start_listener(self):
        self._listener = pynput_mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
        )
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
            return False  # was dead, restarted
        return True  # was alive

    @property
    def elapsed(self) -> float:
        return (time.time() - self.start_time) if self.start_time else 0.0

    def snapshot(self):
        with self._lock:
            return list(self.positions), list(self.clicks)



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


def generate_art(positions, clicks, width, height) -> Image.Image:
    BG = (60, 65, 120)
    img = Image.new("RGBA", (width, height), BG + (255,))

    n = len(positions)

    # ── glowing path ──────────────────────────────────────────────────────────
    if n > 1:
        # wide blurred glow
        glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        gd   = ImageDraw.Draw(glow)
        for i in range(1, n):
            t = i / n
            r, g, b = [int(c * 255) for c in colorsys.hsv_to_rgb(t * 0.85, 0.75, 0.65)]
            x1, y1 = int(positions[i-1][0]), int(positions[i-1][1])
            x2, y2 = int(positions[i][0]),   int(positions[i][1])
            gd.line([(x1, y1), (x2, y2)], fill=(r, g, b, 160), width=10)
        img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(14)))

        # crisp line on top
        sharp = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        sd    = ImageDraw.Draw(sharp)
        for i in range(1, n):
            t = i / n
            r, g, b = [int(c * 255) for c in colorsys.hsv_to_rgb(t * 0.85, 1.0, 1.0)]
            x1, y1 = int(positions[i-1][0]), int(positions[i-1][1])
            x2, y2 = int(positions[i][0]),   int(positions[i][1])
            sd.line([(x1, y1), (x2, y2)], fill=(r, g, b, 230), width=2)
        img = Image.alpha_composite(img, sharp)

    # ── start / end markers ───────────────────────────────────────────────────
    if n > 0:
        d  = ImageDraw.Draw(img)
        sx, sy = int(positions[0][0]),  int(positions[0][1])
        ex, ey = int(positions[-1][0]), int(positions[-1][1])
        d.polygon([(sx, sy-11), (sx+11, sy), (sx, sy+11), (sx-11, sy)],
                  fill=(30, 255, 90, 220))
        d.polygon([(ex, ey-11), (ex+11, ey), (ex, ey+11), (ex-11, ey)],
                  fill=(255, 50, 50, 220))

    # ── glowing click dots ────────────────────────────────────────────────────
    if clicks:
        cg = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        cd = ImageDraw.Draw(cg)
        for cx, cy, btn, _ in clicks:
            cx, cy = int(cx), int(cy)
            gc = (20, 150, 255, 70) if btn == 'left' else (255, 100, 20, 70)
            for r in (35, 22, 13):
                cd.ellipse([cx-r, cy-r, cx+r, cy+r], fill=gc)
        img = Image.alpha_composite(img, cg.filter(ImageFilter.GaussianBlur(16)))

        dots = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        dd   = ImageDraw.Draw(dots)
        for cx, cy, btn, _ in clicks:
            cx, cy = int(cx), int(cy)
            if btn == 'left':
                fill, rim = (70, 200, 255, 255), (210, 245, 255, 255)
            else:
                fill, rim = (255, 130, 45, 255), (255, 220, 170, 255)
            dd.ellipse([cx-10, cy-10, cx+10, cy+10], fill=fill, outline=rim, width=2)
            dd.ellipse([cx-3,  cy-3,  cx+3,  cy+3],  fill=(255, 255, 255, 255))
        img = Image.alpha_composite(img, dots)

    # ── convert to RGB ────────────────────────────────────────────────────────
    final = Image.new("RGB", (width, height), (60, 65, 120))
    final.paste(img, mask=img.split()[3])
    draw  = ImageDraw.Draw(final)

    # ── stats overlay (top-left) ──────────────────────────────────────────────
    dur        = positions[-1][2] if positions else 0
    left_n     = sum(1 for c in clicks if c[2] == 'left')
    right_n    = len(clicks) - left_n
    total_px   = sum(
        math.hypot(positions[i][0]-positions[i-1][0],
                   positions[i][1]-positions[i-1][1])
        for i in range(1, n)
    )

    font_title  = _best_font(22)
    font_body   = _best_font(15)

    lines = [
        ("Mouse Art",                                  (255, 220, 70),  font_title),
        (f"Duration  {dur:.1f} s",                     (160, 210, 255), font_body),
        (f"Points    {n:,}",                           (160, 210, 255), font_body),
        (f"Distance  {total_px:,.0f} px",              (160, 210, 255), font_body),
        (f"Clicks    {len(clicks)}   (L {left_n}  R {right_n})",
                                                        (160, 210, 255), font_body),
        (datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                                                        (100, 140, 180), font_body),
    ]

    px, py = 22, 22
    for text, color, font in lines:
        draw.text((px+1, py+1), text, fill=(0, 0, 0),  font=font)
        draw.text((px,   py),   text, fill=color,       font=font)
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            py += (bbox[3] - bbox[1]) + 7
        except AttributeError:
            py += 22

    # ── legend (bottom-right) ─────────────────────────────────────────────────
    lx, ly = width - 170, height - 110
    draw.ellipse([lx, ly, lx+14, ly+14], fill=(70, 200, 255))
    draw.text((lx+20, ly-1), "Left click",  fill=(160, 210, 255), font=font_body)
    draw.ellipse([lx, ly+26, lx+14, ly+40], fill=(255, 130, 45))
    draw.text((lx+20, ly+25), "Right click", fill=(160, 210, 255), font=font_body)

    # ── start / end legend ────────────────────────────────────────────────────
    draw.polygon([(lx+7, ly+52), (lx+14, ly+59), (lx+7, ly+66), (lx, ly+59)],
                 fill=(30, 255, 90))
    draw.text((lx+20, ly+51), "Start",  fill=(160, 210, 255), font=font_body)
    draw.polygon([(lx+7, ly+74), (lx+14, ly+81), (lx+7, ly+88), (lx, ly+81)],
                 fill=(255, 50, 50))
    draw.text((lx+20, ly+77), "End",    fill=(160, 210, 255), font=font_body)

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
        self.root.title("Mouse Painter")
        self.root.geometry("340x290")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=DARK)

        # title
        tk.Label(self.root, text="✦  Mouse Painter  ✦",
                 font=("Helvetica", 17, "bold"),
                 fg=ACCENT, bg=DARK).pack(pady=(18, 3))

        tk.Label(self.root, text="Move & click freely — we'll turn it into art",
                 font=("Helvetica", 10), fg=DIM, bg=DARK).pack()

        # status
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self.root, textvariable=self.status_var,
                 font=("Helvetica", 11), fg="#aabbcc", bg=DARK).pack(pady=(12, 2))

        # timer
        self.timer_var = tk.StringVar(value="00:00")
        tk.Label(self.root, textvariable=self.timer_var,
                 font=("Courier", 26, "bold"), fg=CYAN, bg=DARK).pack()

        # live counters
        self.counter_var = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self.counter_var,
                 font=("Helvetica", 10), fg=DIM, bg=DARK).pack(pady=(2, 0))

        # button
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

        # hint
        tk.Label(self.root,
                 text="点击开始后窗口自动最小化\n鼠标轨迹全程后台记录",
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
        self.btn.config(text="■   Stop & Paint", bg=RED, activebackground="#aa2222")
        self.status_var.set("Recording  •  move your mouse freely!")
        self._tick()
        # Minimize so the user can work normally; tracking continues in background
        self.root.after(800, self.root.iconify)

    def _tick(self):
        if not self.is_recording:
            return
        e = self.tracker.elapsed
        self.timer_var.set(f"{int(e//60):02d}:{int(e%60):02d}")
        pos, clk = self.tracker.snapshot()

        alive = self.tracker.ensure_listener()
        if not alive:
            # Listener had died — show warning, it's been restarted
            self.status_var.set("⚠️  Tracking interrupted — check Accessibility permission")
        else:
            self.status_var.set("Recording  •  move your mouse freely!")

        self.counter_var.set(f"{len(pos):,} points  •  {len(clk)} clicks")
        self.root.after(400, self._tick)

    def _stop(self):
        self.is_recording = False
        self.tracker.stop()
        positions, clicks = self.tracker.snapshot()

        self.btn.config(state="disabled", text="Painting…", bg=MID)
        self.status_var.set("Generating your artwork…")
        self.counter_var.set("")

        threading.Thread(target=self._generate, args=(positions, clicks),
                         daemon=True).start()

    # ── art generation (background thread) ───────────────────────────────────

    def _generate(self, positions, clicks):
        if not positions:
            self.root.after(0, lambda: messagebox.showinfo(
                "Nothing recorded", "No mouse movement detected."))
            self.root.after(0, self._reset_ui)
            return

        img  = generate_art(positions, clicks, SCREEN_W, SCREEN_H)
        ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(os.path.expanduser("~/Desktop"), f"mouse_art_{ts}.png")
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

        self.root.after(0, lambda: self._done(path, len(positions), len(clicks)))

    def _done(self, path, n_pos, n_clk):
        self.status_var.set("Your art is ready!")
        self.timer_var.set("00:00")
        self._reset_ui()
        self.root.deiconify()   # restore window when art is ready
        self.root.lift()
        messagebox.showinfo(
            "Mouse Art Complete!",
            f"Recorded {n_pos:,} path points and {n_clk} clicks.\n\n"
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
