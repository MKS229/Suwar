"""Tkinter user interface for Suwar: login page + role-based main window."""
import os
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import config
from .mysql_repository import DatabaseError
from .reports import REPORT_TYPES

GREEN_DARK = "#1b5e20"
GREEN = "#2e7d32"
GREEN_LIGHT = "#e8f5e9"
GREEN_MID = "#c8e6c9"
BLUE = "#1e88e5"
RED = "#c62828"
RED_LIGHT = "#ffcdd2"
GREY = "#9e9e9e"
FONT = "Segoe UI"

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def load_image(name):
    """Load a PNG from assets/; returns None if it is missing (the UI still works)."""
    try:
        return tk.PhotoImage(file=os.path.join(ASSETS, name))
    except tk.TclError:
        return None


def setup_style():
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TNotebook", background=GREEN_LIGHT, borderwidth=0)
    style.configure("TNotebook.Tab", padding=(14, 8), font=(FONT, 10, "bold"),
                    background=GREEN_MID, foreground=GREEN_DARK)
    style.map("TNotebook.Tab", background=[("selected", GREEN)], foreground=[("selected", "white")])
    style.configure("Treeview", rowheight=26, font=(FONT, 10), background="white", fieldbackground="white")
    style.configure("Treeview.Heading", font=(FONT, 10, "bold"), background=GREEN_MID, foreground=GREEN_DARK)
    style.configure("Green.TButton", font=(FONT, 10, "bold"), background=GREEN, foreground="white",
                    padding=(14, 6))
    style.map("Green.TButton", background=[("active", GREEN_DARK)])
    style.configure("Red.TButton", font=(FONT, 10, "bold"), background=RED, foreground="white",
                    padding=(14, 6))
    style.map("Red.TButton", background=[("active", "#8e0000")])
    style.configure("Light.TButton", font=(FONT, 10), padding=(10, 5))


# =====================================================================================
#  Login page
# =====================================================================================
class LoginView(tk.Frame):
    def __init__(self, root, controller, on_success):
        super().__init__(root, bg="white")
        self.controller = controller
        self.on_success = on_success
        self.pack(fill="both", expand=True)

        card = tk.Frame(self, bg="white")
        card.place(relx=0.5, rely=0.5, anchor="center")

        self.logo = load_image("logo_full.png")
        if self.logo:
            tk.Label(card, image=self.logo, bg="white").pack(pady=(0, 6))
        else:
            tk.Label(card, text="SUWAR", font=(FONT, 34, "bold"), fg=GREEN, bg="white").pack()

        tk.Label(card, text="Sign in to your account", font=(FONT, 13, "bold"), fg=GREEN_DARK,
                 bg="white").pack(pady=(6, 12))

        form = tk.Frame(card, bg="white")
        form.pack()
        tk.Label(form, text="Username", bg="white", fg="#555", font=(FONT, 10)).grid(row=0, column=0, sticky="w")
        self.username = tk.StringVar()
        self.user_entry = ttk.Entry(form, textvariable=self.username, width=32, font=(FONT, 11))
        self.user_entry.grid(row=1, column=0, pady=(2, 10), ipady=3)

        tk.Label(form, text="Password", bg="white", fg="#555", font=(FONT, 10)).grid(row=2, column=0, sticky="w")
        self.password = tk.StringVar()
        self.pass_entry = ttk.Entry(form, textvariable=self.password, show="•", width=32, font=(FONT, 11))
        self.pass_entry.grid(row=3, column=0, pady=(2, 4), ipady=3)

        self.show_var = tk.BooleanVar(value=False)
        tk.Checkbutton(form, text="Show password", variable=self.show_var, command=self._toggle_password,
                       bg="white", activebackground="white", fg="#555", font=(FONT, 9),
                       highlightthickness=0).grid(row=4, column=0, sticky="w")

        self.error = tk.Label(card, text="", fg=RED, bg="white", font=(FONT, 10), wraplength=300)
        self.error.pack(pady=(8, 2))
        self.button = ttk.Button(card, text="Sign in", style="Green.TButton", command=self._submit)
        self.button.pack(fill="x", pady=(4, 0), ipady=3)
        tk.Label(card, text="Username format: first.last  (e.g. nasser.harthi)", bg="white", fg=GREY,
                 font=(FONT, 9)).pack(pady=(12, 0))

        for entry in (self.user_entry, self.pass_entry):
            entry.bind("<Return>", lambda e: self._submit())
        self.user_entry.focus_set()

    def _toggle_password(self):
        self.pass_entry.config(show="" if self.show_var.get() else "•")

    def _submit(self):
        try:
            result = self.controller.login(self.username.get(), self.password.get())
        except DatabaseError as exc:
            self.error.config(text=f"Database problem: {exc}")
            return
        if result:
            self.password.set("")
            self.error.config(text="")
            self.on_success(result.data)
        else:
            self.error.config(text=result.message)
            self.password.set("")
            self.pass_entry.focus_set()


# =====================================================================================
#  Main window (after login)
# =====================================================================================
class MainView(tk.Frame):
    def __init__(self, root, controller, user, on_logout):
        super().__init__(root, bg=GREEN_LIGHT)
        self.root = root
        self.controller = controller
        self.user = user
        self.on_logout = on_logout
        self._after_id = None
        self.pack(fill="both", expand=True)

        self._build_header()
        self._build_banner()
        self._build_tabs()
        self._build_status_bar()

        try:
            self.controller.coordinate_components()      # first sensor reading right away
        except DatabaseError as exc:
            self.status_var.set(f"⚠ Database problem: {exc}")
        self.refresh_all()
        self._after_id = self.root.after(config.REFRESH_SECONDS * 1000, self._tick)

    def destroy(self):
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        super().destroy()

    # ================================================================== layout
    def _build_header(self):
        header = tk.Frame(self, bg="white", highlightbackground=GREEN, highlightthickness=0)
        header.pack(fill="x")
        left = tk.Frame(header, bg="white")
        left.pack(side="left", padx=16, pady=6)
        self.logo = load_image("logo_header.png")
        if self.logo:
            tk.Label(left, image=self.logo, bg="white").pack(side="left", padx=(0, 12))
        titles = tk.Frame(left, bg="white")
        titles.pack(side="left")
        tk.Label(titles, text="SUWAR", font=(FONT, 20, "bold"), bg="white", fg=GREEN).pack(anchor="w")
        tk.Label(titles, text="FLOWING FORWARD WITH OUR ROOTS", font=(FONT, 8, "bold"),
                 bg="white", fg=BLUE).pack(anchor="w")

        right = tk.Frame(header, bg="white")
        right.pack(side="right", padx=16)
        info = tk.Frame(right, bg="white")
        info.pack(side="left", padx=(0, 12))
        tk.Label(info, text=self.user.name, font=(FONT, 11, "bold"), bg="white", fg=GREEN_DARK,
                 anchor="e").pack(anchor="e")
        tk.Label(info, text=self.user.role.capitalize(), font=(FONT, 9), bg="white", fg="#666",
                 anchor="e").pack(anchor="e")
        ttk.Button(right, text="⚙ Settings", style="Light.TButton",
                   command=self._open_settings).pack(side="left", padx=4)
        ttk.Button(right, text="Log out", style="Green.TButton", command=self._logout).pack(side="left", padx=4)
        tk.Frame(self, bg=GREEN, height=3).pack(fill="x")          # green line under the header

    def _build_banner(self):
        self.banner = tk.Label(self, text="", bg=RED, fg="white", anchor="w", font=(FONT, 11, "bold"),
                               padx=20, pady=8, cursor="hand2")
        self.banner.bind("<Button-1>", lambda e: self.notebook.select(self.tab_alerts))

    def _build_tabs(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(8, 0))
        self.tab_home = self._make_tab("🏠  My Farm")
        self.tab_flow = self._make_tab("💧  Water Flow")
        self.tab_slots = self._make_tab("🗓  Time Slots")
        self.tab_alerts = self._make_tab("🚨  Leak Alerts")
        self._build_home()
        self._build_flow()
        self._build_slots()
        self._build_alerts()
        if self.user.is_staff:                              # technician, engineer, supervisor, director, admin
            self.tab_gates = self._make_tab("🚪  Gates")
            self.tab_reports = self._make_tab("📊  Reports")
            self._build_gates()
            self._build_reports()
        if self.user.is_admin:                              # administrator only
            self.tab_users = self._make_tab("👥  Users")
            self._build_users()

    def _make_tab(self, title):
        frame = tk.Frame(self.notebook, bg=GREEN_LIGHT)
        self.notebook.add(frame, text=title)
        return frame

    def _build_status_bar(self):
        self.status_var = tk.StringVar(value="Starting...")
        tk.Label(self, textvariable=self.status_var, anchor="w", bg=GREEN_MID, fg=GREEN_DARK,
                 font=(FONT, 9), padx=12, pady=4).pack(fill="x", side="bottom")

    def _make_tree(self, parent, columns, widths, height=10):
        wrap = tk.Frame(parent, bg=GREEN_LIGHT)
        tree = ttk.Treeview(wrap, columns=[c[0] for c in columns], show="headings", height=height,
                            selectmode="browse")
        for (cid, heading), width in zip(columns, widths):
            tree.heading(cid, text=heading)
            tree.column(cid, width=width, anchor="w")
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        tree.tag_configure("leak", background=RED_LIGHT)
        tree.tag_configure("taken", foreground=GREY)
        tree.tag_configure("mine", background=GREEN_MID)
        tree.tag_configure("active", background=RED_LIGHT)
        return wrap, tree

    @staticmethod
    def _fill(tree, rows):
        """rows: list of (iid, values, tags). Keeps the user's selection."""
        selected = tree.selection()
        tree.delete(*tree.get_children())
        for iid, values, tags in rows:
            tree.insert("", "end", iid=str(iid), values=values, tags=tags)
        if selected and tree.exists(selected[0]):
            tree.selection_set(selected[0])

    @staticmethod
    def _heading(parent, text, pady=(12, 4)):
        tk.Label(parent, text=text, bg=GREEN_LIGHT, fg=GREEN_DARK, font=(FONT, 14, "bold")).pack(
            anchor="w", padx=16, pady=pady)

    def _show(self, result, title):
        (messagebox.showinfo if result else messagebox.showwarning)(title, result.message)

    # ================================================================== header actions
    def _logout(self):
        self.on_logout()

    def _open_settings(self):
        new = simpledialog.askstring("Settings - change password",
                                     f"New password (at least {config.MIN_PASSWORD_LENGTH} characters):",
                                     show="•", parent=self.root)
        if new is None:
            return
        confirm = simpledialog.askstring("Settings - change password", "Repeat the new password:",
                                         show="•", parent=self.root)
        if confirm != new:
            messagebox.showwarning("Settings", "The two passwords do not match.")
            return
        self._show(self.user.adjust_settings(new_password=new), "Settings")

    # ================================================================== tab: My Farm
    def _build_home(self):
        card = tk.Frame(self.tab_home, bg="white", highlightbackground=GREEN_MID, highlightthickness=2)
        card.pack(fill="x", padx=30, pady=30)
        self.home_title = tk.Label(card, bg="white", fg=GREEN_DARK, font=(FONT, 18, "bold"), anchor="w")
        self.home_title.pack(fill="x", padx=24, pady=(20, 4))
        self.home_sub = tk.Label(card, bg="white", fg="#555", font=(FONT, 11), anchor="w", justify="left")
        self.home_sub.pack(fill="x", padx=24, pady=(0, 14))
        stats = tk.Frame(card, bg="white")
        stats.pack(fill="x", padx=24, pady=(0, 20))
        self.stat_flow = self._stat_box(stats, "Current flow")
        self.stat_status = self._stat_box(stats, "Falaj status")
        self.stat_slots = self._stat_box(stats, "My reservations")
        self.stat_system = self._stat_box(stats, "System")
        tk.Label(self.tab_home, bg=GREEN_LIGHT, fg=GREEN_DARK, font=(FONT, 11),
                 text="Use the tabs above to monitor water flow, reserve irrigation slots and follow leak alerts."
                 ).pack(pady=10)

    @staticmethod
    def _stat_box(parent, caption):
        box = tk.Frame(parent, bg=GREEN_LIGHT, padx=20, pady=12)
        box.pack(side="left", padx=(0, 14))
        tk.Label(box, text=caption, bg=GREEN_LIGHT, fg="#555", font=(FONT, 9)).pack(anchor="w")
        value = tk.Label(box, text="-", bg=GREEN_LIGHT, fg=GREEN_DARK, font=(FONT, 16, "bold"))
        value.pack(anchor="w")
        return value

    def _refresh_home(self, sensors):
        user = self.user
        self.home_title.config(text=f"Welcome, {user.name}")
        self.stat_system.config(text=self.controller.status,
                                fg=RED if self.controller.status == "Alert" else GREEN)
        if user.is_farmer and user.farm:
            farm = user.farm
            self.home_sub.config(text=f"{farm.location}  |  Falaj {farm.falaj_name}  |  {farm.size:.1f} hectares")
            sensor = next((s for s in sensors if s.falaj_name == farm.falaj_name), None)
            if sensor:
                status = sensor.report_status()
                self.stat_flow.config(text=f"{sensor.value:.1f} L/s")
                self.stat_status.config(text="⚠ Leak" if status == "Leak" else "✓ Normal",
                                        fg=RED if status == "Leak" else GREEN)
            used = self.controller.user_slot_count(user)
            self.stat_slots.config(text=f"{used} / {self.controller.schedule_manager.max_slots_for(user)}")
        else:
            self.home_sub.config(text=f"Role: {user.role}  |  Staff accounts monitor and maintain the system "
                                      "but do not reserve irrigation slots.")
            leaking = sum(s.report_status() == "Leak" for s in sensors)
            self.stat_flow.config(text=f"{len(sensors)} sensors")
            self.stat_status.config(text=f"{leaking} leaking", fg=RED if leaking else GREEN)
            self.stat_slots.config(text="-")

    # ================================================================== tab: Water Flow
    def _build_flow(self):
        self._heading(self.tab_flow, "Real-Time Water Flow Monitoring", (12, 4))
        wrap, self.flow_tree = self._make_tree(
            self.tab_flow, [("falaj", "Falaj"), ("loc", "Location"), ("flow", "Flow (L/s)"),
                            ("status", "Status"), ("cal", "Last calibrated")],
            [180, 150, 110, 110, 170], height=8)
        wrap.pack(fill="x", padx=16)
        self.flow_tree.bind("<<TreeviewSelect>>", lambda e: self._draw_chart())

        bar = tk.Frame(self.tab_flow, bg=GREEN_LIGHT)
        bar.pack(fill="x", padx=16, pady=(8, 0))
        self.chart_title = tk.Label(bar, text="Select a sensor to see its flow trend", bg=GREEN_LIGHT,
                                    fg=GREEN_DARK, font=(FONT, 11, "bold"))
        self.chart_title.pack(side="left")
        if self.user.is_staff:
            ttk.Button(bar, text="Calibrate selected sensor", style="Light.TButton",
                       command=self._calibrate).pack(side="right")
        self.chart = tk.Canvas(self.tab_flow, bg="white", height=230, highlightthickness=1,
                               highlightbackground=GREEN_MID)
        self.chart.pack(fill="both", expand=True, padx=16, pady=(4, 12))
        self.chart.bind("<Configure>", lambda e: self._draw_chart())

    def _refresh_flow(self, sensors):
        rows = []
        for s in sensors:
            status = s.report_status()
            cal = s.last_calibrated.strftime("%Y-%m-%d %H:%M") if s.last_calibrated else "never"
            rows.append((s.sensor_id, (s.falaj_name, s.location, f"{s.value:.1f}",
                                       "⚠ Leak" if status == "Leak" else "✓ Normal", cal),
                         ("leak",) if status == "Leak" else ()))
        self._fill(self.flow_tree, rows)
        self._draw_chart()

    def _calibrate(self):
        selection = self.flow_tree.selection()
        if not selection:
            messagebox.showinfo("Select a sensor", "Please select a sensor first.")
            return
        self._show(self.controller.calibrate_sensor(self.user, selection[0]), "Calibration")
        self.refresh_all()

    def _draw_chart(self):
        canvas = self.chart
        canvas.delete("all")
        selection = self.flow_tree.selection()
        if not selection:
            return
        sensor_id = int(selection[0])
        sensor = next((s for s in self.controller.get_sensors() if s.sensor_id == sensor_id), None)
        values = self.controller.get_flow_history(sensor_id, 30)
        self.chart_title.config(text=f"Flow trend - {sensor.falaj_name if sensor else sensor_id} "
                                     f"(last {len(values)} readings)")
        w, h = canvas.winfo_width(), canvas.winfo_height()
        left, right, top, bottom = 50, 20, 15, 30
        y_max = max(12.0, max(values, default=0) + 1)

        def px(i):
            return left + (w - left - right) * (i / max(len(values) - 1, 1))

        def py(v):
            return h - bottom - (h - top - bottom) * (v / y_max)

        for tick in range(0, int(y_max) + 1, 2):
            canvas.create_line(left, py(tick), w - right, py(tick), fill="#eee")
            canvas.create_text(left - 8, py(tick), text=str(tick), anchor="e", fill="#666")
        canvas.create_line(left, py(config.LEAK_THRESHOLD), w - right, py(config.LEAK_THRESHOLD),
                           fill=RED, dash=(6, 4))
        canvas.create_text(w - right, py(config.LEAK_THRESHOLD) - 8, text="leak threshold", anchor="e",
                           fill=RED, font=(FONT, 8))
        canvas.create_text(12, h / 2, text="L/s", angle=90, fill="#666")
        if len(values) >= 2:
            points = [c for i, v in enumerate(values) for c in (px(i), py(v))]
            canvas.create_line(*points, fill=GREEN, width=2)
            for i, v in enumerate(values):
                colour = RED if v > config.LEAK_THRESHOLD else GREEN
                canvas.create_oval(px(i) - 3, py(v) - 3, px(i) + 3, py(v) + 3, fill=colour, outline="")
        else:
            canvas.create_text(w / 2, h / 2, text="Collecting data...", fill="#888")

    # ================================================================== tab: Time Slots
    def _build_slots(self):
        top = tk.Frame(self.tab_slots, bg=GREEN_LIGHT)
        top.pack(fill="x", padx=16, pady=(12, 6))
        tk.Label(top, text="Irrigation Time Slot Reservation", bg=GREEN_LIGHT, fg=GREEN_DARK,
                 font=(FONT, 14, "bold")).pack(side="left")
        self.falaj_var = tk.StringVar(value=self.user.farm.falaj_name if self.user.farm else "All falaj")
        names = ["All falaj"] + [s.falaj_name for s in self.controller.get_sensors()]
        self.falaj_combo = ttk.Combobox(top, textvariable=self.falaj_var, values=names, state="readonly",
                                        width=18)
        self.falaj_combo.pack(side="right")
        tk.Label(top, text="Show:", bg=GREEN_LIGHT, fg=GREEN_DARK).pack(side="right", padx=6)
        self.falaj_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_slots())

        wrap, self.slot_tree = self._make_tree(
            self.tab_slots, [("id", "Slot"), ("falaj", "Falaj"), ("time", "Time"), ("status", "Status")],
            [80, 200, 170, 300], height=14)
        wrap.pack(fill="both", expand=True, padx=16)

        buttons = tk.Frame(self.tab_slots, bg=GREEN_LIGHT)
        buttons.pack(fill="x", padx=16, pady=10)
        if self.user.is_farmer:
            ttk.Button(buttons, text="Reserve selected slot", style="Green.TButton",
                       command=self._reserve).pack(side="left")
            ttk.Button(buttons, text="Cancel my reservation", style="Red.TButton",
                       command=self._cancel).pack(side="left", padx=10)
        if self.user.is_staff:
            ttk.Button(buttons, text="Add slot", style="Green.TButton", command=self._add_slot).pack(side="left")
            ttk.Button(buttons, text="Change time", style="Light.TButton",
                       command=self._change_slot).pack(side="left", padx=10)
        self.slot_hint = tk.Label(buttons, bg=GREEN_LIGHT, fg=GREEN_DARK, font=(FONT, 9))
        self.slot_hint.pack(side="right")

    def _refresh_slots(self):
        choice = self.falaj_var.get()
        falaj = None if choice in ("", "All falaj") else choice
        rows = []
        for s in self.controller.get_slots(falaj):
            text = self.controller.describe_reservation(s, self.user)
            tags = ("mine",) if text == "Reserved by you" else ("taken",) if s.is_reserved else ()
            rows.append((s.slot_id, (s.slot_id, s.falaj_name, f"{s.start_time} - {s.end_time}", text), tags))
        self._fill(self.slot_tree, rows)
        if self.user.is_farmer:
            used = self.controller.user_slot_count(self.user)
            limit = self.controller.schedule_manager.max_slots_for(self.user)
            self.slot_hint.config(text=f"You have {used} of {limit} slots")
        else:
            self.slot_hint.config(text="Only farmers can reserve slots")

    def _selected_slot_id(self):
        selection = self.slot_tree.selection()
        if not selection:
            messagebox.showinfo("Select a slot", "Please select a time slot from the list first.")
            return None
        return int(selection[0])

    def _reserve(self):
        slot_id = self._selected_slot_id()
        if slot_id is not None:
            self._show(self.user.reserve_time_slot(slot_id), "Reservation")
            self.refresh_all()

    def _cancel(self):
        slot_id = self._selected_slot_id()
        if slot_id is not None:
            self._show(self.controller.schedule_manager.cancel_reservation(self.user.user_id, slot_id),
                       "Cancellation")
            self.refresh_all()

    def _add_slot(self):
        falaj = self.falaj_var.get()
        if falaj in ("", "All falaj"):
            messagebox.showinfo("Add slot", "Choose a falaj in the 'Show' box first.")
            return
        value = simpledialog.askstring("Add slot", f"Start time for {falaj} (HH:MM, between "
                                       f"{config.SCHEDULE_START} and {config.SCHEDULE_END}):", parent=self.root)
        if value:
            self._show(self.controller.schedule_manager.create_schedule(falaj, value), "Add slot")
            self.refresh_all()

    def _change_slot(self):
        slot_id = self._selected_slot_id()
        if slot_id is None:
            return
        value = simpledialog.askstring("Change time", "New start time (HH:MM):", parent=self.root)
        if value:
            self._show(self.controller.schedule_manager.update_schedule(slot_id, value), "Change time")
            self.refresh_all()

    # ================================================================== tab: Leak Alerts
    def _build_alerts(self):
        self.alert_header = tk.Label(self.tab_alerts, text="", font=(FONT, 13, "bold"), anchor="w",
                                     padx=16, pady=10)
        self.alert_header.pack(fill="x", padx=16, pady=(12, 6))
        wrap, self.active_tree = self._make_tree(
            self.tab_alerts, [("id", "Alert"), ("loc", "Location"), ("status", "Status"),
                              ("time", "Detected at"), ("sched", "Maintenance date")],
            [70, 260, 120, 170, 140], height=6)
        wrap.pack(fill="x", padx=16)

        buttons = tk.Frame(self.tab_alerts, bg=GREEN_LIGHT)
        buttons.pack(fill="x", padx=16, pady=8)
        ttk.Button(buttons, text="Acknowledge", style="Red.TButton", command=self._ack).pack(side="left")
        if self.user.is_staff:
            ttk.Button(buttons, text="Schedule maintenance", style="Green.TButton",
                       command=self._schedule).pack(side="left", padx=10)
            ttk.Button(buttons, text="Mark resolved", style="Light.TButton",
                       command=self._resolve).pack(side="left")

        tk.Label(self.tab_alerts, text="Leak History", bg=GREEN_LIGHT, fg=GREEN_DARK,
                 font=(FONT, 12, "bold")).pack(anchor="w", padx=16)
        wrap2, self.history_tree = self._make_tree(
            self.tab_alerts, [("id", "Alert"), ("loc", "Location"), ("time", "Detected at"), ("status", "Status")],
            [70, 260, 180, 140], height=8)
        wrap2.pack(fill="both", expand=True, padx=16, pady=(2, 12))

    def _refresh_alerts(self):
        active = self.controller.get_active_maintenance()
        history = self.controller.get_maintenance_history(50)
        open_count = sum(m.status == "Open" for m in active)
        if open_count:
            self.alert_header.config(text=f"🚨  {open_count} new leak alert(s) - action required",
                                     bg=RED, fg="white")
        elif active:
            self.alert_header.config(text=f"🔧  {len(active)} issue(s) being handled", bg="#ffe0b2", fg="#e65100")
        else:
            self.alert_header.config(text="✓  No active leak alerts", bg=GREEN_MID, fg=GREEN_DARK)
        fmt = "%Y-%m-%d %H:%M:%S"
        self._fill(self.active_tree, [
            (m.maintenance_id, (m.maintenance_id, m.location, m.status, m.reported_date.strftime(fmt),
                                m.scheduled_date.strftime("%Y-%m-%d") if m.scheduled_date else "-"),
             ("active",) if m.status == "Open" else ()) for m in active])
        self._fill(self.history_tree, [
            (m.maintenance_id, (m.maintenance_id, m.location, m.reported_date.strftime(fmt), m.status),
             ("active",) if m.status == "Open" else ()) for m in history])
        self._update_banner(open_alerts=[m for m in active if m.status == "Open"])

    def _update_banner(self, open_alerts):
        if open_alerts:
            latest = open_alerts[0]
            self.banner.config(text=f"🚨 {latest.send_maintenance_alert()}   ({len(open_alerts)} new alert(s)) "
                                    "- click to view")
            if not self.banner.winfo_ismapped():
                self.banner.pack(fill="x", before=self.notebook)
        else:
            self.banner.pack_forget()

    def _selected_alert_id(self):
        selection = self.active_tree.selection()
        if not selection:
            messagebox.showinfo("Select an alert", "Please select an alert from the top list first.")
            return None
        return int(selection[0])

    def _ack(self):
        mid = self._selected_alert_id()
        if mid is not None:
            self._show(self.controller.acknowledge_alert(self.user, mid), "Acknowledge")
            self.refresh_all()

    def _schedule(self):
        mid = self._selected_alert_id()
        if mid is None:
            return
        default = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        value = simpledialog.askstring("Schedule maintenance", "Maintenance date (YYYY-MM-DD):",
                                       initialvalue=default, parent=self.root)
        if not value:
            return
        try:
            when = datetime.strptime(value.strip(), "%Y-%m-%d").date()
        except ValueError:
            messagebox.showwarning("Schedule maintenance", "Please enter the date as YYYY-MM-DD.")
            return
        self._show(self.controller.schedule_maintenance(self.user, mid, when), "Schedule maintenance")
        self.refresh_all()

    def _resolve(self):
        mid = self._selected_alert_id()
        if mid is not None:
            self._show(self.controller.resolve_issue(self.user, mid), "Resolve")
            self.refresh_all()

    # ================================================================== tab: Gates (staff)
    def _build_gates(self):
        self._heading(self.tab_gates, "Gate Control")
        wrap, self.gate_tree = self._make_tree(
            self.tab_gates, [("id", "Gate"), ("falaj", "Falaj"), ("loc", "Location"), ("status", "Status")],
            [70, 220, 160, 220], height=12)
        wrap.pack(fill="both", expand=True, padx=16)
        buttons = tk.Frame(self.tab_gates, bg=GREEN_LIGHT)
        buttons.pack(fill="x", padx=16, pady=10)
        ttk.Button(buttons, text="Open gate", style="Green.TButton",
                   command=lambda: self._gate("open")).pack(side="left")
        ttk.Button(buttons, text="Close gate", style="Red.TButton",
                   command=lambda: self._gate("close")).pack(side="left", padx=10)
        ttk.Button(buttons, text="Set flow rate", style="Light.TButton",
                   command=lambda: self._gate("adjust")).pack(side="left")

    def _refresh_gates(self):
        self._fill(self.gate_tree, [(g.gate_id, (g.gate_id, g.falaj_name, g.location, g.get_gate_status()),
                                     () if g.is_open else ("taken",)) for g in self.controller.get_gates()])

    def _gate(self, action):
        selection = self.gate_tree.selection()
        if not selection:
            messagebox.showinfo("Select a gate", "Please select a gate first.")
            return
        rate = None
        if action == "adjust":
            rate = simpledialog.askfloat("Set flow rate", f"Flow rate in L/s (0 - {config.MAX_GATE_FLOW:g}):",
                                         parent=self.root)
            if rate is None:
                return
        self._show(self.controller.operate_gate(self.user, selection[0], action, rate), "Gate control")
        self.refresh_all()

    # ================================================================== tab: Reports (staff)
    def _build_reports(self):
        self._heading(self.tab_reports, "Reports")
        bar = tk.Frame(self.tab_reports, bg=GREEN_LIGHT)
        bar.pack(fill="x", padx=16, pady=(0, 6))
        self.report_type = tk.StringVar(value=REPORT_TYPES[0])
        ttk.Combobox(bar, textvariable=self.report_type, values=list(REPORT_TYPES), state="readonly",
                     width=24).pack(side="left")
        ttk.Button(bar, text="Generate report", style="Green.TButton", command=self._generate_report).pack(
            side="left", padx=10)
        ttk.Button(bar, text="Export to CSV", style="Light.TButton", command=self._export_report).pack(side="left")

        body = tk.Frame(self.tab_reports, bg=GREEN_LIGHT)
        body.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        left = tk.Frame(body, bg=GREEN_LIGHT)
        left.pack(side="left", fill="y")
        tk.Label(left, text="Saved reports (encrypted in the database)", bg=GREEN_LIGHT, fg=GREEN_DARK,
                 font=(FONT, 10, "bold")).pack(anchor="w")
        wrap, self.report_tree = self._make_tree(left,
                                                 [("id", "#"), ("type", "Type"), ("date", "Generated")],
                                                 [40, 150, 130], height=14)
        wrap.pack(fill="y", expand=True)
        self.report_tree.bind("<<TreeviewSelect>>", self._on_report_select)
        self.report_text = tk.Text(body, wrap="none", font=("Consolas", 10), bg="white", state="disabled",
                                   relief="flat", highlightthickness=1, highlightbackground=GREEN_MID)
        self.report_text.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self.current_report = None
        self.saved_reports = {}

    def _refresh_reports(self):
        try:
            reports = self.controller.get_saved_reports(self.user)
        except PermissionError:
            return
        self.saved_reports = {r.report_id: r for r in reports}
        self._fill(self.report_tree, [(r.report_id, (r.report_id, r.type, r.generated_date.strftime("%Y-%m-%d %H:%M")), ())
                                      for r in reports])

    def _generate_report(self):
        report = self.controller.generate_report(self.user, self.report_type.get())
        self.current_report = report
        self._show_report(report)
        self._refresh_reports()

    def _on_report_select(self, _event=None):
        selection = self.report_tree.selection()
        if selection and int(selection[0]) in self.saved_reports:
            self.current_report = self.saved_reports[int(selection[0])]
            self._show_report(self.current_report)

    def _show_report(self, report):
        lines = [f"{report.type}", f"Generated: {report.generated_date:%Y-%m-%d %H:%M:%S}", ""]
        rows = report.data["rows"]
        if rows:
            headers = list(rows[0].keys())
            widths = [max(len(str(h)), *(len(str(r[h])) for r in rows)) for h in headers]
            lines.append("  ".join(str(h).ljust(w) for h, w in zip(headers, widths)))
            lines.append("  ".join("-" * w for w in widths))
            for r in rows:
                lines.append("  ".join(str(r[h]).ljust(w) for h, w in zip(headers, widths)))
        lines += ["", "Analysis"]
        lines += [f"  {k}: {v}" for k, v in report.data["analysis"].items()] or ["  (no data)"]
        self.report_text.config(state="normal")
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", "\n".join(lines))
        self.report_text.config(state="disabled")

    def _export_report(self):
        if self.current_report is None:
            messagebox.showinfo("Export", "Generate or select a report first.")
            return
        stamp = self.current_report.generated_date.strftime("%Y%m%d_%H%M")
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")],
                                            initialfile=f"suwar_report_{stamp}.csv")
        if path:
            try:
                self.current_report.export_report(path)
                messagebox.showinfo("Export", f"Report saved to:\n{path}")
            except OSError as exc:
                messagebox.showerror("Export", f"Could not save the file:\n{exc}")

    # ================================================================== tab: Users (admin only)
    def _build_users(self):
        top = tk.Frame(self.tab_users, bg=GREEN_LIGHT)
        top.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(top, text="System Users (administrator only)", bg=GREEN_LIGHT, fg=GREEN_DARK,
                 font=(FONT, 14, "bold")).pack(side="left")
        ttk.Button(top, text="Run security audit", style="Light.TButton", command=self._audit).pack(side="right")
        wrap, self.user_tree = self._make_tree(
            self.tab_users, [("id", "ID"), ("username", "Username"), ("name", "Name"), ("role", "Role"),
                             ("farm", "Farm / Falaj"), ("slots", "Reserved slots")],
            [50, 150, 200, 100, 220, 110], height=18)
        wrap.pack(fill="both", expand=True, padx=16, pady=(0, 12))

    def _refresh_users(self):
        users = self.controller.get_users(self.user)          # raises PermissionError if not admin
        self._fill(self.user_tree, [
            (u.user_id, (u.user_id, u.username, u.name, u.role,
                         f"{u.farm.location} / {u.farm.falaj_name}" if u.farm else "-",
                         self.controller.user_slot_count(u)), ()) for u in users])

    def _audit(self):
        findings = self.controller.run_security_audit(self.user)
        stamp = self.controller.security.last_audit
        if not findings:
            messagebox.showinfo("Security audit", f"No problems found.\n(Audit time {stamp:%Y-%m-%d %H:%M:%S})")
            return
        shown = "\n".join(f"• {f}" for f in findings[:12])
        extra = f"\n... and {len(findings) - 12} more" if len(findings) > 12 else ""
        messagebox.showwarning("Security audit", f"{len(findings)} finding(s):\n\n{shown}{extra}\n\n"
                                                 "Ask each user to change their password in Settings.")

    # ================================================================== refresh loop
    def refresh_all(self):
        try:
            sensors = self.controller.get_sensors()
            self._refresh_home(sensors)
            self._refresh_flow(sensors)
            self._refresh_slots()
            self._refresh_alerts()
            if self.user.is_staff:
                self._refresh_gates()
                self._refresh_reports()
            if self.user.is_admin:
                self._refresh_users()
            self.status_var.set(f"Connected to MySQL  |  Last update {datetime.now():%H:%M:%S}  |  "
                                f"Auto-refresh every {config.REFRESH_SECONDS}s")
        except DatabaseError as exc:
            self.status_var.set(f"⚠ Database problem: {exc}")

    def _tick(self):
        try:
            self.controller.coordinate_components()
        except DatabaseError as exc:
            self.status_var.set(f"⚠ Database problem: {exc}")
        else:
            self.refresh_all()
        self._after_id = self.root.after(config.REFRESH_SECONDS * 1000, self._tick)


# =====================================================================================
#  Application shell: switches between the login page and the main window
# =====================================================================================
class SuwarApp:
    def __init__(self, root, controller):
        self.root = root
        self.controller = controller
        self.view = None
        root.title("Suwar - Irrigation Management System")
        root.geometry("1100x720")
        root.minsize(960, 620)
        root.configure(bg="white")
        setup_style()
        self.show_login()

    def _clear(self):
        if self.view is not None:
            self.view.destroy()
            self.view = None

    def show_login(self):
        self._clear()
        self.root.configure(bg="white")
        self.view = LoginView(self.root, self.controller, self.show_main)

    def show_main(self, user):
        self._clear()
        self.root.configure(bg=GREEN_LIGHT)
        self.view = MainView(self.root, self.controller, user, self.show_login)
