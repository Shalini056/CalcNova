import ast
import math
import operator
import random
import sqlite3
import threading
import urllib.parse
import urllib.request
import json
import tkinter as tk
from datetime import datetime
import customtkinter as ctk
from PIL import Image, ImageTk

APP_NAME = "CalcNova"
DB_FILE = "calcnova_history.db"

# ---------- Safe mathematical evaluator (does not use Python eval) ----------
BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.Mod: operator.mod,
}
UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
FUNCTIONS = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
    "tan": math.tan, "asin": math.asin, "acos": math.acos,
    "atan": math.atan, "log": math.log10, "ln": math.log,
    "factorial": math.factorial, "abs": abs, "floor": math.floor,
    "ceil": math.ceil, "exp": math.exp,
}
CONSTANTS = {"pi": math.pi, "e": math.e}

def safe_calculate(expression):
    expression = expression.replace("×", "*").replace("÷", "/").replace("^", "**")
    expression = expression.replace("π", "pi")
    tree = ast.parse(expression, mode="eval")

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.Name) and node.id in CONSTANTS:
            return CONSTANTS[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in BIN_OPS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 1000:
                raise ValueError("Exponent is too large")
            return BIN_OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY_OPS:
            return UNARY_OPS[type(node.op)](visit(node.operand))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
            if name not in FUNCTIONS or node.keywords or len(node.args) != 1:
                raise ValueError("Unsupported function")
            return FUNCTIONS[name](visit(node.args[0]))
        raise ValueError("Invalid expression")

    result = visit(tree)
    if isinstance(result, complex) or not math.isfinite(float(result)):
        raise ValueError("Result is not a finite real number")
    return result

# ---------- App (customtkinter) ----------
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class CalcNova(ctk.CTk):
    THEMES = {
        "Violet": {"accent": "#8B5CF6", "hover": "#A78BFA", "glow": "#C4B5FD"},
        "Cyber Blue": {"accent": "#0EA5E9", "hover": "#38BDF8", "glow": "#7DD3FC"},
        "Neon Pink": {"accent": "#DB2777", "hover": "#F472B6", "glow": "#F9A8D4"},
        "Emerald": {"accent": "#059669", "hover": "#10B981", "glow": "#6EE7B7"},
    }

    def __init__(self):
        super().__init__()
        self.title("CalcNova | Smart Calculation Space")
        self.geometry("980x720")
        self.minsize(850, 650)
        self.configure(fg_color="#A9B5D5")
        self.theme_name = "Violet"
        self.history = []
        self.sound_on = True
        self.expression = tk.StringVar()
        self.status = tk.StringVar(value="Ready when you are.")
        self._init_db()
        self._setup_ambient_background()
        self._build_ui()
        self._load_history()
        self.bind("<Return>", lambda _e: self.calculate())
        self.bind("<Escape>", lambda _e: self.clear_display())

    @property
    def palette(self):
        return self.THEMES[self.theme_name]

    def _init_db(self):
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expression TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""")

    # ---------- Full-window animated neon background ----------
    def _setup_ambient_background(self):
        self.ambient_canvas = tk.Canvas(
            self, bg="#A9B5D5", highlightthickness=0, bd=0
        )
        self.ambient_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.neon_particles = []
        self._gradient_redraw_pending = False
        self.ambient_canvas.bind("<Configure>", self._schedule_gradient_redraw)
        self.after(250, self._draw_ambient_gradient)
        self.after(300, self._create_neon_particles)

    def _schedule_gradient_redraw(self, _event=None):
        if getattr(self, "_gradient_redraw_pending", False):
            return
        self._gradient_redraw_pending = True

        def redraw():
            self._gradient_redraw_pending = False
            if self.winfo_exists():
                self._draw_ambient_gradient()

        self.after_idle(redraw)

    def _draw_ambient_gradient(self):
        if not self.winfo_exists():
            return
        canvas = self.ambient_canvas
        canvas.delete("gradient")
        width = max(canvas.winfo_width(), 850)
        height = max(canvas.winfo_height(), 650)

        stops = [
            (0.0, (184, 126, 218)),  # luminous lavender
            (0.48, (79, 166, 207)),  # bright cyan-blue
            (1.0, (222, 139, 190)),  # soft rose pink
        ]

        def mix(a, b, t):
            return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

        bands = 140
        for i in range(bands):
            t = i / max(bands - 1, 1)
            if t <= stops[1][0]:
                local = t / stops[1][0]
                rgb = mix(stops[0][1], stops[1][1], local)
            else:
                local = (t - stops[1][0]) / (stops[2][0] - stops[1][0])
                rgb = mix(stops[1][1], stops[2][1], local)
            color = "#%02x%02x%02x" % rgb
            x0 = int(i * width / bands)
            x1 = int((i + 1) * width / bands) + 1
            canvas.create_rectangle(
                x0, 0, x1, height, fill=color, outline=color, tags="gradient"
            )

    def _create_neon_particles(self):
        if not self.winfo_exists():
            return

        width = max(self.winfo_width(), 980)
        height = max(self.winfo_height(), 720)

        for _ in range(48):
            x = random.uniform(0, width)
            y = random.uniform(0, height)
            radius = random.choice([2, 2, 3, 4])
            item = self.ambient_canvas.create_oval(
                x-radius, y-radius, x+radius, y+radius,
                fill=random.choice(["#8B5CF6", "#6D5BCE", "#3876A8", "#A78BFA"]),
                outline=""
            )
            self.neon_particles.append({
                "x": x, "y": y,
                "vx": random.choice([-1.35, -0.9, 0.9, 1.35]),
                "vy": random.choice([-0.8, -0.5, 0.5, 0.8]),
                "base_radius": radius,
                "phase": random.uniform(0, 6.28),
                "item": item
            })

        self._animate_neon_background()

    def _animate_neon_background(self):
        if not self.winfo_exists():
            return

        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)

        for particle in self.neon_particles:
            particle["x"] += particle["vx"]
            particle["y"] += particle["vy"]

            # Wrap particles around the full window so movement never stops.
            if particle["x"] < 0:
                particle["x"] = width
            elif particle["x"] > width:
                particle["x"] = 0

            if particle["y"] < 0:
                particle["y"] = height
            elif particle["y"] > height:
                particle["y"] = 0

            particle["phase"] += 0.12
            pulse = 1 if math.sin(particle["phase"]) > 0.55 else 0
            x, y = particle["x"], particle["y"]
            radius = particle["base_radius"] + pulse
            self.ambient_canvas.coords(
                particle["item"],
                x-radius, y-radius, x+radius, y+radius
            )

        # Rebuild faint connection lines every frame.
        self.ambient_canvas.delete("neon_link")
        for i, first in enumerate(self.neon_particles):
            for second in self.neon_particles[i+1:]:
                dx = first["x"] - second["x"]
                dy = first["y"] - second["y"]
                if dx*dx + dy*dy < 105*105:
                    self.ambient_canvas.create_line(
                        first["x"], first["y"],
                        second["x"], second["y"],
                        fill="#302451", width=1, tags="neon_link"
                    )

        self.after(30, self._animate_neon_background)

    def _build_ui(self):
        # Dashboard shell inspired by the supplied glassmorphism reference.
        shell = ctk.CTkFrame(self, fg_color="transparent")
        shell.pack(fill="both", expand=True, padx=18, pady=16)

        sidebar = ctk.CTkFrame(
            shell, width=188, corner_radius=22,
            fg_color="#8F9FC9", border_width=1, border_color="#F6E9FF"
        )
        sidebar.pack(side="left", fill="y", padx=(0, 16))
        sidebar.pack_propagate(False)

        ctk.CTkLabel(
            sidebar, text="✦  CALCNOVA", font=("Segoe UI", 21, "bold"),
            text_color="#F1E9FF"
        ).pack(anchor="w", padx=17, pady=(25, 2))
        ctk.CTkLabel(
            sidebar, text="SMART CALCULATION SPACE",
            font=("Segoe UI", 8, "bold"), text_color="#C4D5F4"
        ).pack(anchor="w", padx=18, pady=(0, 28))

        ctk.CTkLabel(
            sidebar, text="WORKSPACE", font=("Segoe UI", 9, "bold"),
            text_color="#B7C8EB"
        ).pack(anchor="w", padx=18, pady=(0, 8))

        self.nav_buttons = {}
        nav_items = [
            ("⌗", "Calculator", "Calculator"),
            ("∑", "Scientific", "Calculator"),
            ("％", "GST & %", "GST & %"),
            ("⇄", "Currency", "Currency"),
            ("◷", "History", "History"),
        ]
        for symbol, label, tab_name in nav_items:
            button = ctk.CTkButton(
                sidebar,
                text=f"{symbol}   {label}",
                anchor="w", height=42, corner_radius=12,
                font=("Segoe UI", 12, "bold"),
                fg_color="#7053A7" if label == "Calculator" else "transparent",
                hover_color="#8067B4",
                text_color="#F5F2FF",
                command=lambda t=tab_name, l=label: self.navigate(t, l)
            )
            button.pack(fill="x", padx=10, pady=4)
            self.nav_buttons[label] = button

        spacer = ctk.CTkFrame(sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)
        ctk.CTkFrame(
            sidebar, height=2, fg_color="#D7B7FF"
        ).pack(fill="x", padx=14, pady=(8, 12))
        ctk.CTkLabel(
            sidebar, text="✧  NEON EDITION",
            font=("Segoe UI", 10, "bold"), text_color="#D9D0FF"
        ).pack(anchor="w", padx=17, pady=(0, 18))

        main = ctk.CTkFrame(shell, fg_color="transparent")
        main.pack(side="left", fill="both", expand=True)

        header = ctk.CTkFrame(main, fg_color="transparent")
        header.pack(fill="x", pady=(4, 14))
        heading = ctk.CTkFrame(header, fg_color="transparent")
        heading.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            heading, text="Welcome to CalcNova  ✨",
            font=("Segoe UI", 24, "bold"), text_color="#FFFFFF"
        ).pack(anchor="w")
        ctk.CTkLabel(
            heading, text="Your smart space for numbers, formulas and conversions.",
            font=("Segoe UI", 11), text_color="#E0E8FF"
        ).pack(anchor="w", pady=(3, 0))

        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.pack(side="right", padx=(10, 10))
        self.theme_menu = ctk.CTkOptionMenu(
            controls, values=list(self.THEMES), width=126,
            command=self.change_theme, fg_color=self.palette["accent"],
            button_color=self.palette["accent"], text_color="#FFFFFF"
        )
        self.theme_menu.pack(side="left", padx=(0, 10))
        self.sound_button = ctk.CTkButton(
            controls, text="♫ SOUND ON", width=116,
            fg_color="#8F9FC9", hover_color="#A88AD8",
            command=self.toggle_sound
        )
        self.sound_button.pack(side="left")

        # Top shortcut cards removed for a cleaner workspace.

        self.tabs = ctk.CTkTabview(
            main, corner_radius=20, fg_color="transparent",
            segmented_button_selected_color=self.palette["accent"],
            segmented_button_selected_hover_color=self.palette["hover"]
        )
        self.tabs.pack(fill="both", expand=True, pady=(18, 0))
        for tab in ("Calculator", "GST & %", "Currency", "History"):
            self.tabs.add(tab)

        # The left navigation is the primary navigation, so hide the tab strip.
        try:
            self.tabs._segmented_button.pack_forget()
        except Exception:
            pass

        self._build_calculator_tab()
        self._build_gst_tab()
        self._build_currency_tab()
        self._build_history_tab()
        self._start_equals_glow()
        self.tabs.set("Calculator")

        footer = ctk.CTkLabel(
            main, textvariable=self.status, text_color="#F0E8FF",
            font=("Segoe UI", 10)
        )
        footer.pack(fill="x", pady=(8, 0))

    def navigate(self, tab_name, nav_label=None):
        self.tabs.set(tab_name)

        # Keep the normal calculator clean and wide. Show the scientific
        # toolkit only when the user explicitly selects Scientific.
        if tab_name == "Calculator" and hasattr(self, "scientific_panel"):
            if nav_label == "Scientific":
                self.tabs.tab("Calculator").grid_columnconfigure(0, weight=3)
                self.tabs.tab("Calculator").grid_columnconfigure(1, weight=2)
                self.scientific_panel.grid(
                    row=0, column=1, sticky="nsew", padx=(6, 6), pady=8
                )
                self.scientific_panel_visible = True
                self.tabs.tab("Calculator").grid_slaves(row=0, column=0)[0].grid_configure(
                    columnspan=1, padx=(6, 6)
                )
            else:
                self.scientific_panel.grid_forget()
                self.scientific_panel_visible = False
                self.tabs.tab("Calculator").grid_columnconfigure(0, weight=1)
                self.tabs.tab("Calculator").grid_columnconfigure(1, weight=0)
                self.tabs.tab("Calculator").grid_slaves(row=0, column=0)[0].grid_configure(
                    columnspan=2, padx=(8, 5)
                )

        for label, button in self.nav_buttons.items():
            active = label == (nav_label or tab_name)
            button.configure(
                fg_color="#7053A7" if active else "transparent",
                hover_color="#8067B4"
            )
        self.status.set(f"{tab_name} workspace selected.")

    def _start_equals_glow(self):
        """Apply a steady neon treatment once; no blinking or pulsing."""
        button = getattr(self, "equals_button", None)
        display = getattr(self, "display", None)

        if button is not None:
            button.configure(
                fg_color=self.palette["accent"],
                hover_color=self.palette["hover"],
                border_width=3,
                border_color=self.palette["glow"],
                text_color="#FFFFFF"
            )

        if display is not None:
            display.configure(
                border_width=3,
                border_color=self.palette["glow"]
            )

    def panel(self, parent, **kwargs):
        """Glass-style panel: sampled gradient underlay, permanent violet rim and particles."""
        frame = ctk.CTkFrame(
            parent,
            fg_color="transparent",
            corner_radius=22,
            border_width=1,
            border_color="#D7B7FF",
            **kwargs
        )

        canvas = tk.Canvas(
            frame,
            bg="#B9C8E8",
            highlightthickness=0,
            bd=0
        )
        # Keep the canvas inside the rounded frame so it never squares the corners.
        canvas.place(x=6, y=6, relwidth=1, relheight=1, width=-12, height=-12)

        frame._glass_image = None
        frame._glass_photo = None

        def refresh_glass(_event=None):
            if not frame.winfo_exists():
                return
            width = max(canvas.winfo_width(), 120)
            height = max(canvas.winfo_height(), 100)

            # Recreate the same violet -> blue -> rose gradient as the main
            # background, then blend a cool translucent glass tint over it.
            root = self
            try:
                panel_x = frame.winfo_rootx() - root.winfo_rootx()
                root_width = max(root.winfo_width(), 850)
            except Exception:
                panel_x, root_width = 0, 1200

            left_rgb = (184, 126, 218)
            mid_rgb = (79, 166, 207)
            right_rgb = (222, 139, 190)

            def blend(a, b, t):
                return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

            base = Image.new("RGB", (width, height))
            pixels = base.load()
            for x in range(width):
                gx = min(1.0, max(0.0, (panel_x + x) / max(root_width, 1)))
                if gx < 0.48:
                    bg = blend(left_rgb, mid_rgb, gx / 0.48)
                else:
                    bg = blend(mid_rgb, right_rgb, (gx - 0.48) / 0.52)

                # Bright frosted glass: keep the pastel gradient visible beneath
                # a milky lavender-blue veil, matching the user's Lumina reference.
                glass = blend(bg, (239, 235, 255), 0.43)
                glass = blend(glass, (185, 224, 246), 0.12)
                for y in range(height):
                    # Gentle top-to-bottom light, like the supplied glass dashboard.
                    lift = max(0, int(9 * (1 - y / max(height, 1))))
                    pixels[x, y] = tuple(min(255, c + lift) for c in glass)

            # Round the gradient image itself. Without this mask, the
            # rectangular Canvas exposes a second square edge inside the
            # rounded CTkFrame border.
            from PIL import ImageDraw
            glass_rgba = base.convert("RGBA")
            mask = Image.new("L", (width, height), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle(
                (0, 0, width - 1, height - 1),
                radius=16, fill=255
            )
            glass_rgba.putalpha(mask)

            frame._glass_image = glass_rgba
            frame._glass_photo = ImageTk.PhotoImage(glass_rgba)
            canvas.delete("glass_bg")
            canvas.create_image(0, 0, image=frame._glass_photo, anchor="nw", tags="glass_bg")
            canvas.tag_lower("glass_bg")

            # The rounded CTkFrame supplies the single permanent glass rim.
            # Do not draw a second square canvas border inside it.
            canvas.delete("glass_rim")
            canvas.tag_raise("particle")
            canvas.tag_raise("particle_link")

        canvas.bind("<Configure>", refresh_glass)

        particles = []
        colors = ["#DCCBFF", "#BFA6FF", "#9CE7FF", "#F5C8F0"]
        for _ in range(18):
            x = random.randint(8, 420)
            y = random.randint(8, 300)
            radius = random.choice([1, 2, 2])
            dot = canvas.create_oval(
                x-radius, y-radius, x+radius, y+radius,
                fill=random.choice(colors), outline="", tags="particle"
            )
            particles.append({
                "x": float(x), "y": float(y),
                "vx": random.choice([-0.7, -0.4, 0.4, 0.7]),
                "vy": random.choice([-0.35, -0.2, 0.2, 0.35]),
                "r": radius, "item": dot
            })

        def animate_panel_particles():
            if not frame.winfo_exists():
                return
            width = max(canvas.winfo_width() - 8, 100)
            height = max(canvas.winfo_height() - 8, 100)

            for particle in particles:
                particle["x"] = 4 + ((particle["x"] - 4 + particle["vx"]) % width)
                particle["y"] = 4 + ((particle["y"] - 4 + particle["vy"]) % height)
                x, y, r = particle["x"], particle["y"], particle["r"]
                canvas.coords(particle["item"], x-r, y-r, x+r, y+r)

            canvas.delete("particle_link")
            for i, first in enumerate(particles):
                for second in particles[i+1:]:
                    dx = first["x"] - second["x"]
                    dy = first["y"] - second["y"]
                    if dx*dx + dy*dy < 78*78:
                        canvas.create_line(
                            first["x"], first["y"],
                            second["x"], second["y"],
                            fill="#C3A9F0", width=1, tags=("particle_link",)
                        )
            canvas.tag_raise("particle_link")
            canvas.tag_raise("particle")
            frame.after(45, animate_panel_particles)

        frame.after(250, animate_panel_particles)
        return frame

    def _build_calculator_tab(self):
        tab = self.tabs.tab("Calculator")
        # Standard mode uses the full width. Scientific mode reveals the
        # toolkit panel on the right when selected from the sidebar.
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=0)
        tab.grid_rowconfigure(0, weight=1)

        left = self.panel(tab)
        left.grid(row=0, column=0, columnspan=2, sticky="nsew",
                  padx=10, pady=8)
        right = self.panel(tab)
        self.scientific_panel = right
        self.scientific_panel_visible = False

        self.display = ctk.CTkEntry(left, textvariable=self.expression, height=62,
                     font=("Segoe UI", 25), justify="right", corner_radius=12,
                     border_width=2, border_color="#F6E8FF",
                     fg_color="#E9EAFB", text_color="#26345A")
        self.display.pack(fill="x", padx=16, pady=(10, 9))
        self.result_label = ctk.CTkLabel(left, text="0", font=("Segoe UI", 29, "bold"),
                                         text_color="#3B315E",
                                         fg_color="#B9CBEA", anchor="e")
        self.result_label.pack(fill="x", padx=16, pady=(0, 12))

        keys = [
            ["AC", "⌫", "(", ")", "÷"],
            ["7", "8", "9", "×", "√"],
            ["4", "5", "6", "-", "x²"],
            ["1", "2", "3", "+", "^"],
            ["±", "0", ".", "%", "="],
        ]
        self.keypad_buttons = []
        self.equals_button = None
        pad = ctk.CTkFrame(left, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=12, pady=(2, 12))
        for r, row in enumerate(keys):
            pad.grid_rowconfigure(r, weight=1)
            for col, key in enumerate(row):
                pad.grid_columnconfigure(col, weight=1)
                is_operator = key in {"÷", "×", "-", "+", "^", "=", "√", "x²", "%"}
                is_special = key in {"AC", "⌫"}
                color = "#C3D9F0" if not is_operator and not is_special else (
                    "#9276C9" if is_operator else "#C77FAE")
                if key == "=":
                    color = self.palette["accent"]
                btn = ctk.CTkButton(
                    pad, text=key, height=48, corner_radius=12,
                    font=("Segoe UI", 17, "bold"),
                    fg_color=color,
                    hover_color=self.palette["hover"],
                    border_width=2 if is_operator else 1,
                    border_color="#E9D8FF" if is_operator else "#DDEBFA",
                    text_color="#FFFFFF" if (is_operator or is_special) else "#26345A",
                    command=lambda k=key: self.press(k)
                )
                btn.configure(command=lambda k=key, w=btn: self.press_animated(k, w))
                btn.grid(row=r, column=col, sticky="nsew", padx=4, pady=4)
                self.keypad_buttons.append((btn, key, color))
                if key == "=":
                    self.equals_button = btn

        ctk.CTkLabel(right, text="SCIENTIFIC TOOLKIT", font=("Segoe UI", 12, "bold"),
                     text_color="#3B315E", fg_color="#B9CBEA", padx=6).pack(
                         anchor="w", padx=(12, 8), pady=(16, 9))
        sci = [
            ("sin", "sin("), ("cos", "cos("), ("tan", "tan("),
            ("asin", "asin("), ("acos", "acos("), ("atan", "atan("),
            ("log", "log("), ("ln", "ln("), ("√", "sqrt("),
            ("π", "pi"), ("e", "e"), ("n!", "factorial("),
            ("abs", "abs("), ("floor", "floor("), ("ceil", "ceil("),
        ]
        grid = ctk.CTkFrame(right, fg_color="transparent")
        grid.pack(fill="x", padx=12)
        for i, (label, value) in enumerate(sci):
            b = ctk.CTkButton(grid, text=label, height=38, corner_radius=10,
                fg_color="#BBD6EE", hover_color="#A88AD8",
                text_color="#26345A", border_width=1,
                border_color="#E9E4FF",
                command=lambda v=value: self.insert_text(v))
            b.grid(row=i//3, column=i%3, sticky="ew", padx=2, pady=4)
        for c in range(3):
            grid.grid_columnconfigure(c, weight=1)
        ctk.CTkLabel(right, text="Angles: sin/cos/tan use radians.\nPress Enter to calculate.",
                     text_color="#405477", fg_color="#B9CBEA",
                     justify="left", padx=6).pack(anchor="w", padx=12, pady=14)

    def _build_gst_tab(self):
        tab = self.tabs.tab("GST & %")
        card = self.panel(tab)
        card.pack(fill="both", expand=True, padx=12, pady=10)
        ctk.CTkLabel(card, text="GST & PERCENTAGE STUDIO", font=("Segoe UI", 19, "bold"),
                     fg_color="#C3C9EA", text_color="#3B315E", padx=6).pack(anchor="w", padx=16, pady=(14, 6))
        self.gst_amount = self._field(card, "Amount (₹)", "1000")
        self.gst_rate = self._field(card, "GST rate (%)", "18")
        self.gst_mode = ctk.CTkSegmentedButton(card, values=["Add GST", "Remove GST"],
                                              selected_color=self.palette["accent"])
        self.gst_mode.pack(fill="x", padx=16, pady=6)
        self.gst_mode.set("Add GST")
        ctk.CTkButton(card, text="CALCULATE GST", height=44,
                      fg_color=self.palette["accent"], hover_color=self.palette["hover"],
                      command=self.calculate_gst).pack(fill="x", padx=16, pady=5)
        self.gst_result = ctk.CTkLabel(card, text="Your breakdown will appear here.",
                    font=("Segoe UI", 16), text_color="#3B315E",
                    fg_color="#B9CBEA", justify="left", padx=6)
        self.gst_result.pack(anchor="w", padx=16, pady=7)
        ctk.CTkLabel(card, text="QUICK PERCENTAGE", font=("Segoe UI", 15, "bold"),
                     fg_color="transparent", text_color="#FFFFFF").pack(anchor="w", padx=16, pady=(8, 3))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16)
        self.percent_base = ctk.CTkEntry(
            row, placeholder_text="Value", height=34,
            fg_color="#E9EAFB", text_color="#26345A",
            placeholder_text_color="#68799B", border_color="#F5E7FF"
        )
        self.percent_base.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.percent_rate = ctk.CTkEntry(
            row, placeholder_text="% rate", height=34,
            fg_color="#E9EAFB", text_color="#26345A",
            placeholder_text_color="#68799B", border_color="#F5E7FF"
        )
        self.percent_rate.pack(side="left", fill="x", expand=True, padx=6)
        ctk.CTkButton(row, text="Find %", width=90, command=self.calculate_percent,
                      fg_color=self.palette["accent"]).pack(side="left", padx=(6, 0))
        self.percent_result = ctk.CTkLabel(card, text="", text_color="#3B315E",
                                           fg_color="#B9CBEA",
                                           font=("Segoe UI", 16, "bold"))
        self.percent_result.pack(anchor="w", padx=16, pady=5)

    def _field(self, parent, label, default):
        ctk.CTkLabel(
            parent, text=label, text_color="#27365B",
            fg_color="#B9CBEA", font=("Segoe UI", 12, "bold"), padx=6
        ).pack(anchor="w", padx=16, pady=(8, 3))
        entry = ctk.CTkEntry(
            parent, height=40, fg_color="#EEF0FF",
            text_color="#27365B", placeholder_text_color="#7382A5",
            border_color="#EAD9FF"
        )
        entry.pack(fill="x", padx=16)
        entry.insert(0, default)
        return entry

    def _build_currency_tab(self):
        tab = self.tabs.tab("Currency")
        card = self.panel(tab)
        card.pack(fill="both", expand=True, padx=12, pady=10)
        ctk.CTkLabel(card, text="CURRENCY EXCHANGE", font=("Segoe UI", 20, "bold"),
                     fg_color="#C3C9EA", text_color="#3B315E").pack(anchor="w", padx=16, pady=(16, 6))
        ctk.CTkLabel(card, text="Live reference rates powered by Frankfurter. Internet required.",
                     fg_color="#B9CBEA", text_color="#405477", padx=6).pack(anchor="w", padx=16, pady=(0, 14))
        self.currency_amount = self._field(card, "Amount", "1")
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=10)
        self.from_currency = ctk.CTkComboBox(
            row, values=["INR", "USD", "EUR", "GBP", "JPY", "AED", "CAD", "AUD"],
            fg_color="#EEF0FF", text_color="#27365B",
            border_color="#EAD9FF", button_color="#A88AD8",
            dropdown_fg_color="#EEF0FF", dropdown_text_color="#27365B"
        )
        self.from_currency.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.from_currency.set("USD")
        ctk.CTkLabel(row, text="→", font=("Segoe UI", 22, "bold"),
                     text_color=self.palette["glow"]).pack(side="left", padx=8)
        self.to_currency = ctk.CTkComboBox(
            row, values=["INR", "USD", "EUR", "GBP", "JPY", "AED", "CAD", "AUD"],
            fg_color="#EEF0FF", text_color="#27365B",
            border_color="#EAD9FF", button_color="#A88AD8",
            dropdown_fg_color="#EEF0FF", dropdown_text_color="#27365B"
        )
        self.to_currency.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.to_currency.set("INR")
        self.currency_button = ctk.CTkButton(card, text="GET EXCHANGE RATE", height=44,
                fg_color=self.palette["accent"], hover_color=self.palette["hover"],
                command=self.convert_currency)
        self.currency_button.pack(fill="x", padx=16, pady=8)
        self.currency_result = ctk.CTkLabel(
            card, text="Ready to convert.", font=("Segoe UI", 22, "bold"),
            fg_color="#C3C9EA", text_color="#3B315E", wraplength=600, padx=6
        )
        self.currency_result.pack(padx=16, pady=16)
        self.currency_note = ctk.CTkLabel(
            card, text="Rates are indicative and may differ from bank/card rates.",
            fg_color="#B9CBEA", text_color="#405477", padx=6
        )
        self.currency_note.pack(anchor="w", padx=16)

    def _build_history_tab(self):
        tab = self.tabs.tab("History")
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=10)
        ctk.CTkLabel(
            top, text="YOUR RECENT CALCULATIONS",
            font=("Segoe UI", 17, "bold"),
            text_color="#3B315E", fg_color="transparent"
        ).pack(side="left")
        ctk.CTkButton(
            top, text="Clear history", width=116,
            fg_color=self.palette["accent"], hover_color=self.palette["hover"],
            text_color="#FFFFFF", corner_radius=10,
            command=self.clear_history
        ).pack(side="right", padx=12)
        self.history_frame = ctk.CTkScrollableFrame(
            tab, fg_color="#C8D5EC", corner_radius=16,
            border_width=1, border_color="#E8D9FF"
        )
        self.history_frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

    # ---------- Interactions ----------
    def play_click(self):
        if not self.sound_on:
            return
        try:
            import winsound
            winsound.Beep(880, 35)
        except Exception:
            self.bell()

    def toggle_sound(self):
        self.sound_on = not self.sound_on
        self.sound_button.configure(text="♫ SOUND ON" if self.sound_on else "♫ SOUND OFF")
        self.status.set("Sound enabled." if self.sound_on else "Sound muted.")

    def change_theme(self, name):
        self.theme_name = name
        self.status.set(f"{name} theme selected. Accent updates on newly created controls and highlights.")
        self.result_label.configure(text_color="#303B63")
        self.display.configure(border_color=self.palette["glow"], border_width=3)
        for button, key, base_color in getattr(self, "keypad_buttons", []):
            is_operator = key in {"÷", "×", "-", "+", "^", "=", "√", "x²", "%"}
            button.configure(
                hover_color=self.palette["hover"],
                border_color=self.palette["glow"] if key == "=" else (
                    self.palette["accent"] if is_operator else "#3B4565"
                ),
                border_width=3 if key == "=" else (2 if is_operator else 1)
            )
        if getattr(self, "equals_button", None):
            self.equals_button.configure(
                fg_color=self.palette["accent"],
                hover_color=self.palette["hover"],
                border_color=self.palette["glow"],
                border_width=3
            )
        self.theme_menu.configure(fg_color=self.palette["accent"], button_color=self.palette["accent"])
        self.tabs.configure(segmented_button_selected_color=self.palette["accent"],
                            segmented_button_selected_hover_color=self.palette["hover"])

    def animate(self, widget):
        original = widget.cget("fg_color")
        widget.configure(fg_color=self.palette["hover"])
        self.after(110, lambda: widget.configure(fg_color=original))

    def press_animated(self, key, widget):
        # No flash or blink: keep the neon styling constant while calculating.
        self.press(key)

    def press(self, key):
        if key == "AC":
            self.play_click()
            self.clear_display()
        elif key == "⌫":
            self.play_click()
            self.expression.set(self.expression.get()[:-1])
        elif key == "=":
            self.play_click()
            self.calculate()
        elif key == "√":
            self.insert_text("sqrt(")
        elif key == "x²":
            self.insert_text("**2")
        elif key == "±":
            self.play_click()
            value = self.expression.get()
            self.expression.set(f"-({value})" if value else "-")
        elif key == "%":
            self.insert_text("/100")
        else:
            self.insert_text({"×": "*", "÷": "/"}.get(key, key))

    def insert_text(self, value):
        self.display.focus_set()
        self.display.insert(tk.INSERT, value)
        self.play_click()

    def clear_display(self):
        self.expression.set("")
        self.result_label.configure(text="0")
        self.status.set("Display cleared.")

    def calculate(self):
        expr = self.expression.get().strip()
        if not expr:
            return
        try:
            result = safe_calculate(expr)
            result_text = f"{result:,.10g}" if isinstance(result, float) else f"{result:,}"
            self.result_label.configure(text=result_text)
            self._save_history(expr, str(result))
            self.status.set("Calculation complete.")
        except ZeroDivisionError:
            self.result_label.configure(text="Cannot divide by zero")
            self.status.set("Math error: division by zero.")
        except Exception as exc:
            self.result_label.configure(text="Check expression")
            self.status.set(f"Could not calculate: {exc}")

    def _save_history(self, expr, result):
        stamp = datetime.now().strftime("%d %b %Y, %I:%M %p")
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("INSERT INTO history(expression,result,created_at) VALUES(?,?,?)",
                         (expr, result, stamp))
        self._load_history()

    def _load_history(self):
        for child in self.history_frame.winfo_children() if hasattr(self, "history_frame") else []:
            child.destroy()
        with sqlite3.connect(DB_FILE) as conn:
            rows = conn.execute("SELECT expression,result,created_at FROM history ORDER BY id DESC LIMIT 100").fetchall()
        if not hasattr(self, "history_frame"):
            return
        if not rows:
            ctk.CTkLabel(
                self.history_frame,
                text="No calculations yet. Your results will appear here.",
                text_color="#52658A", fg_color="transparent"
            ).pack(pady=25)
        for expr, result, stamp in rows:
            item = ctk.CTkFrame(
                self.history_frame, fg_color="#E8ECFA",
                corner_radius=12, border_width=1, border_color="#F7F0FF"
            )
            item.pack(fill="x", padx=10, pady=6)
            ctk.CTkLabel(
                item, text=expr, font=("Segoe UI", 14),
                text_color="#34466D", fg_color="transparent"
            ).pack(anchor="w", padx=14, pady=(10, 1))
            ctk.CTkLabel(
                item, text=f"= {result}", font=("Segoe UI", 17, "bold"),
                text_color="#6545A5", fg_color="transparent"
            ).pack(anchor="w", padx=14)
            ctk.CTkLabel(
                item, text=stamp, font=("Segoe UI", 9),
                text_color="#7182A5", fg_color="transparent"
            ).pack(anchor="w", padx=14, pady=(1, 8))
            ctk.CTkButton(
                item, text="Use again", width=96, height=30,
                command=lambda e=expr: self.use_history(e),
                fg_color=self.palette["accent"], hover_color=self.palette["hover"],
                text_color="#FFFFFF", corner_radius=9
            ).pack(anchor="e", padx=12, pady=(0, 10))

    def use_history(self, expr):
        self.tabs.set("Calculator")
        self.expression.set(expr)
        self.status.set("Previous expression restored.")

    def clear_history(self):
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("DELETE FROM history")
        self._load_history()
        self.status.set("Calculation history cleared.")

    def calculate_gst(self):
        try:
            amount = float(self.gst_amount.get())
            rate = float(self.gst_rate.get())
            if amount < 0 or rate < 0:
                raise ValueError()
            if self.gst_mode.get() == "Add GST":
                gst = amount * rate / 100
                total = amount + gst
                text = f"Base amount: ₹{amount:,.2f}\nGST ({rate:g}%): ₹{gst:,.2f}\nTotal including GST: ₹{total:,.2f}"
            else:
                base = amount / (1 + rate / 100)
                gst = amount - base
                text = f"Original total: ₹{amount:,.2f}\nBase amount: ₹{base:,.2f}\nGST included ({rate:g}%): ₹{gst:,.2f}"
            self.gst_result.configure(text=text)
            self.status.set("GST breakdown calculated.")
        except Exception:
            self.gst_result.configure(text="Please enter valid non-negative numbers.")

    def calculate_percent(self):
        try:
            base = float(self.percent_base.get())
            rate = float(self.percent_rate.get())
            result = base * rate / 100
            self.percent_result.configure(text=f"{rate:g}% of {base:g} = {result:,.4f}")
        except Exception:
            self.percent_result.configure(text="Enter a valid value and percentage.")

    def convert_currency(self):
        try:
            amount = float(self.currency_amount.get())
            source, target = self.from_currency.get().upper(), self.to_currency.get().upper()
            if amount < 0 or len(source) != 3 or len(target) != 3:
                raise ValueError()
        except Exception:
            self.currency_result.configure(text="Enter a valid amount and 3-letter currency codes.")
            return
        self.currency_button.configure(state="disabled", text="FETCHING RATE…")
        self.currency_result.configure(text="Connecting to exchange-rate service…")

        def worker():
            try:
                url = f"https://api.frankfurter.app/latest?from={urllib.parse.quote(source)}&to={urllib.parse.quote(target)}"
                request = urllib.request.Request(url, headers={"User-Agent": "CalcNova/1.0"})
                with urllib.request.urlopen(request, timeout=12) as response:
                    data = json.loads(response.read().decode("utf-8"))
                rate = data["rates"][target]
                converted = amount * rate
                message = f"{amount:,.2f} {source}  =  {converted:,.2f} {target}\nRate: 1 {source} = {rate:.6g} {target}\nDate: {data.get('date', 'Latest available')}"
            except Exception as exc:
                message = f"Could not fetch rates. Check your internet and currency codes.\nDetails: {exc}"
            self.after(0, lambda: self._currency_done(message))

        threading.Thread(target=worker, daemon=True).start()

    def _currency_done(self, message):
        self.currency_result.configure(text=message)
        self.currency_button.configure(state="normal", text="GET EXCHANGE RATE")
        self.status.set("Currency lookup finished.")

if __name__ == "__main__":
    app = CalcNova()
    app.mainloop()
