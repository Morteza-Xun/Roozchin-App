import flet as ft
import json
import os
import multiprocessing
import threading
import queue
import asyncio
from datetime import datetime
import ctypes
import sys

# --- Path helpers for dev & packaged modes ---
def _is_frozen():
    return getattr(sys, 'frozen', False)

def _bundle_dir():
    if _is_frozen() and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def _exe_dir():
    if _is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def _appdata_dir():
    base = os.environ.get('APPDATA') or os.path.expanduser('~')
    d = os.path.join(base, 'Roozchin')
    os.makedirs(d, exist_ok=True)
    return d

def _pick_data_dir():
    if _is_frozen():
        exe_d = _exe_dir()
        try:
            tf = os.path.join(exe_d, '.roozchin_write_test')
            with open(tf, 'w') as f:
                f.write('x')
            os.remove(tf)
            return exe_d
        except Exception:
            pass
    return _appdata_dir()

ASSETS_DIR = os.path.join(_bundle_dir(), 'assets')
DATA_DIR = _pick_data_dir()
DATA_FILE = os.path.join(DATA_DIR, 'days.json')

def _migrate_if_needed():
    if not _is_frozen() or os.path.exists(DATA_FILE):
        return
    exe_d = _exe_dir()
    search_dirs = [exe_d, os.path.dirname(exe_d), os.path.dirname(os.path.dirname(exe_d))]
    for d in search_dirs:
        candidate = os.path.join(d, 'days.json')
        if os.path.exists(candidate) and os.path.abspath(candidate) != os.path.abspath(DATA_FILE):
            try:
                import shutil
                shutil.copy2(candidate, DATA_FILE)
                print(f"[migrate] {candidate} -> {DATA_FILE}")
                return
            except Exception as e:
                print(f"[migrate] fail: {e}")

_migrate_if_needed()

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("roozchin.app.1")
except Exception:
    pass

try:
    import jdatetime
    HAS_JDATETIME = True
except ImportError:
    HAS_JDATETIME = False

try:
    import pystray
    from PIL import Image
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False


CATEGORIES = ["تحصیل", "مهارت", "ورزش", "خانواده", "سرگرمی"]

JALALI_MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
                 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']

CATEGORY_ICONS = {
    "تحصیل": ft.Icons.SCHOOL,
    "مهارت": ft.Icons.PSYCHOLOGY,
    "ورزش": ft.Icons.FITNESS_CENTER,
    "خانواده": ft.Icons.FAMILY_RESTROOM,
    "سرگرمی": ft.Icons.SPORTS_ESPORTS,
}

CATEGORY_COLORS = {
    "تحصیل": "#FF6B9D",
    "مهارت": "#A29BFE",
    "ورزش": "#00B894",
    "خانواده": "#FDCB6E",
    "سرگرمی": "#74B9FF",
}


def to_persian_digits(s):
    return str(s).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def today_jalali():
    if HAS_JDATETIME:
        return jdatetime.datetime.now().strftime("%Y/%m/%d")
    return datetime.now().strftime("%Y/%m/%d")


def format_date_long(date_str):
    if not HAS_JDATETIME:
        return date_str
    try:
        d = jdatetime.datetime.strptime(date_str, "%Y/%m/%d")
        weekdays = {0: 'شنبه', 1: 'یک‌شنبه', 2: 'دوشنبه', 3: 'سه‌شنبه',
                    4: 'چهارشنبه', 5: 'پنج‌شنبه', 6: 'جمعه'}
        weekday_fa = weekdays[d.weekday()]
        month_fa = JALALI_MONTHS[d.month - 1]
        return to_persian_digits(f"{weekday_fa} ، {d.day} {month_fa} {d.year}")
    except Exception:
        return date_str


def get_theme_colors(theme_id):
    if theme_id == 0:
        return {"bg": "#F5F5F5", "gradient": None, "text": "#111111",
                "text_sub": "#555555", "glass_bg": "#FFFFFF", "glass_border": "#E0E0E0",
                "icon": "#111111", "widget_bg": "#EEFFFFFF"}
    elif theme_id == 1:
        return {"bg": "#000000", "gradient": None, "text": "#FFFFFF",
                "text_sub": "#AAAAAA", "glass_bg": "#151515", "glass_border": "#333333",
                "icon": "#FFFFFF", "widget_bg": "#EE151515"}
    else:
        return {"bg": "#0F0C29", "gradient": ["#0F0C29", "#302B63", "#24243E"],
                "text": "#FFFFFF", "text_sub": "#AAAADD", "glass_bg": "#22FFFFFF",
                "glass_border": "#33FFFFFF", "icon": "#FFFFFF", "widget_bg": "#DD1E1E2E"}


def load_data():
    if not os.path.exists(DATA_FILE):
        return {"days": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for day in data.get("days", []):
                if "categories" in day:
                    old_cats = day.pop("categories")
                    day["custom_categories"] = []
                    for cat_name, tasks in old_cats.items():
                        if not tasks:
                            continue
                        ctype = cat_name if cat_name in CATEGORIES else "شخصی"
                        if ctype == "شخصی":
                            ctype = "تحصیل"
                        day["custom_categories"].append({
                            "id": f"{cat_name}_{day['date']}",
                            "name": cat_name,
                            "type": ctype,
                            "tasks": tasks,
                            "expanded": True
                        })
                if "lesson" not in day:
                    day["lesson"] = ""
                if "custom_categories" not in day:
                    day["custom_categories"] = []
                for cat in day.get("custom_categories", []):
                    if "expanded" not in cat:
                        cat["expanded"] = True
            return data
    except Exception:
        return {"days": []}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------- Floating Widget Process ----------
def show_floating_widget(data_file, theme_id, target_date, q_show_main):
    try:
        import tkinter as _tk
        _r = _tk.Tk()
        _r.withdraw()
        SCREEN_W = _r.winfo_screenwidth()
        SCREEN_H = _r.winfo_screenheight()
        _r.destroy()
    except Exception:
        SCREEN_W, SCREEN_H = 1920, 1080

    COLLAPSED_W = 48
    EXPANDED_W = 340
    WIDGET_H = min(600, SCREEN_H - 100)
    RIGHT_MARGIN = 10
    WIDGET_TOP = (SCREEN_H - WIDGET_H) // 2
    ANIM_MS = 320

    def load_widget_data():
        if not os.path.exists(data_file):
            return {"days": []}
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"days": []}

    data = load_widget_data()
    initial_day = next((d for d in data["days"] if d["date"] == target_date), None)
    colors = get_theme_colors(theme_id)

    def widget_main(page: ft.Page):
        page.title = f"روزچین - {format_date_long(target_date)}"
        page.rtl = True
        page.padding = 0
        page.window.resizable = False
        page.window.maximizable = False
        page.window.frameless = True
        page.window.always_on_top = True
        page.window.width = EXPANDED_W
        page.window.height = WIDGET_H
        page.window.top = WIDGET_TOP
        page.window.left = SCREEN_W - EXPANDED_W - RIGHT_MARGIN
        page.bgcolor = ft.Colors.TRANSPARENT
        page.window.bgcolor = ft.Colors.TRANSPARENT

        page.fonts = {"Vazir": "Vazir-Medium.ttf", "Vazir Bold": "Vazir-Bold.ttf"}
        page.theme = ft.Theme(font_family="Vazir")
        page.dark_theme = ft.Theme(font_family="Vazir")

        ui = {"expanded": True, "animating": False, "day": initial_day, "task_col": None}

        sidebar = ft.Container(
            width=EXPANDED_W,
            animate=ft.Animation(ANIM_MS, ft.AnimationCurve.EASE_IN_OUT_CUBIC),
        )
        root = ft.Container(content=sidebar, alignment=ft.Alignment.CENTER_RIGHT, expand=True)
        page.add(root)

        def close_widget(e):
            os._exit(0)

        def go_back(e):
            q_show_main.put("show_main")
            os._exit(0)

        async def toggle(e):
            if ui["animating"]:
                return
            ui["animating"] = True
            try:
                if ui["expanded"]:
                    ui["expanded"] = False
                    sidebar.width = COLLAPSED_W
                    page.update()
                    await asyncio.sleep((ANIM_MS + 60) / 1000)
                    sidebar.content = build_collapsed()
                    page.update()
                else:
                    ui["expanded"] = True
                    d = load_widget_data()
                    ui["day"] = next((x for x in d["days"] if x["date"] == target_date), None)
                    sidebar.content = build_expanded()
                    sidebar.width = EXPANDED_W
                    page.update()
                    await asyncio.sleep((ANIM_MS + 60) / 1000)
            finally:
                ui["animating"] = False

        def refresh(e=None):
            d = load_widget_data()
            ui["day"] = next((x for x in d["days"] if x["date"] == target_date), None)
            if ui["task_col"] is not None:
                ui["task_col"].controls.clear()
                ui["task_col"].controls.extend(build_tasks(ui["day"]))
            page.update()

        def build_tasks(d_day):
            if not d_day or not d_day.get("custom_categories"):
                return [ft.Text("کاری ثبت نشده", color=colors["text_sub"], font_family="Vazir")]
            all_tasks = []
            for cat in d_day["custom_categories"]:
                for task in cat.get("tasks", []):
                    all_tasks.append((cat["id"], task))
            if not all_tasks:
                return [ft.Text("کاری ثبت نشده", color=colors["text_sub"], font_family="Vazir")]

            controls = []
            for cat_id, task in all_tasks[:10]:
                is_done = task.get("done", False)

                def make_handler(c_id, t_text):
                    def handler(e):
                        val = e.control.value
                        fresh_data = load_widget_data()
                        for day_item in fresh_data["days"]:
                            if day_item["date"] == target_date:
                                for c in day_item["custom_categories"]:
                                    if c["id"] == c_id:
                                        for t in c["tasks"]:
                                            if t["text"] == t_text:
                                                t["done"] = val
                        with open(data_file, "w", encoding="utf-8") as f:
                            json.dump(fresh_data, f, ensure_ascii=False, indent=2)
                        refresh()
                    return handler

                controls.append(ft.Container(
                    content=ft.Row([
                        ft.Checkbox(value=is_done, on_change=make_handler(cat_id, task["text"]),
                                    fill_color=ft.Colors.CYAN_300 if theme_id != 0 else ft.Colors.BLUE),
                        ft.Text(task["text"], expand=True, selectable=True,
                                style=ft.TextStyle(font_family="Vazir", size=14,
                                                   color=colors["text_sub"] if is_done else colors["text"],
                                                   decoration=ft.TextDecoration.LINE_THROUGH if is_done else None)),
                    ], spacing=4),
                    padding=ft.Padding.symmetric(vertical=2),
                ))
            return controls

        def count_pending():
            if not ui["day"]:
                return 0
            return sum(1 for cat in ui["day"].get("custom_categories", [])
                       for t in cat.get("tasks", []) if not t.get("done", False))

        def build_collapsed():
            pending = count_pending()
            arrow_btn = ft.Container(
                content=ft.Icon(ft.Icons.CHEVRON_LEFT, color="#FFFFFF", size=22),
                width=36, height=36, bgcolor="#74B9FF", border_radius=18,
                alignment=ft.Alignment.CENTER,
            )
            items = [ft.Container(height=18), arrow_btn]
            if pending > 0:
                items.append(ft.Container(height=12))
                items.append(ft.Container(
                    content=ft.Text(to_persian_digits(str(pending)), font_family="Vazir Bold",
                                    size=12, color="#FFFFFF"),
                    bgcolor="#FF5252", padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=10,
                ))
            return ft.Container(
                content=ft.Column(items, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=colors["widget_bg"], border_radius=16,
                border=ft.Border.all(1, colors["glass_border"]),
                on_click=toggle, tooltip="باز کردن ویجت", expand=True,
            )

        def build_expanded():
            task_col = ft.Column(build_tasks(ui["day"]), spacing=2, scroll=ft.ScrollMode.AUTO)
            ui["task_col"] = task_col
            return ft.Container(
                content=ft.Column([
                    ft.WindowDragArea(ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.DRAG_INDICATOR, color=colors["text_sub"], size=20),
                            ft.Text("روزچین", font_family="Vazir Bold", size=16, color=colors["text"], expand=True),
                            ft.IconButton(ft.Icons.CHEVRON_RIGHT, icon_size=18, icon_color=colors["text_sub"],
                                          on_click=toggle, tooltip="جمع کردن"),
                            ft.IconButton(ft.Icons.REFRESH, icon_size=16, icon_color=colors["text_sub"],
                                          on_click=refresh, tooltip="بروزرسانی"),
                            ft.IconButton(ft.Icons.ARROW_BACK, icon_size=18, icon_color=colors["text_sub"],
                                          on_click=go_back, tooltip="بازگشت به برنامه"),
                            ft.IconButton(ft.Icons.CLOSE, icon_size=18, icon_color=ft.Colors.RED_400,
                                          on_click=close_widget, tooltip="بستن"),
                        ]),
                        padding=ft.Padding.only(left=10, right=5, top=5, bottom=5),
                        bgcolor="#00000000",
                    )),
                    ft.Container(
                        content=ft.Text(format_date_long(target_date), font_family="Vazir",
                                        size=13, color=colors["text_sub"]),
                        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    ),
                    ft.Divider(height=1, color=colors["glass_border"]),
                    ft.Container(content=task_col, padding=ft.Padding.all(12), expand=True),
                ], spacing=0, expand=True),
                bgcolor=colors["widget_bg"], border_radius=16,
                border=ft.Border.all(1, colors["glass_border"]),
                padding=0, expand=True,
            )

        def render():
            sidebar.content = build_expanded() if ui["expanded"] else build_collapsed()
            page.update()

        render()

    ft.run(widget_main, assets_dir=ASSETS_DIR)


# ---------- Main App ----------
def main(page: ft.Page):
    page.title = "روزچین"
    page.rtl = True
    page.padding = ft.Padding.all(0)

    page.window.resizable = True
    page.window.maximizable = True
    page.window.min_width = 360
    page.window.min_height = 520
    page.window.width = 900
    page.window.height = 720
    page.window.icon = "logo.ico"

    page.fonts = {"Vazir": "Vazir-Medium.ttf", "Vazir Bold": "Vazir-Bold.ttf"}
    page.theme = ft.Theme(font_family="Vazir")
    page.dark_theme = ft.Theme(font_family="Vazir")

    data = load_data()
    state = {
        "view": "home", "current_date": None, "new_cat_type": "تحصیل", "theme": 2,
        "report_year": None, "report_month": None, "report_cat": None,
    }

    q_show_main = multiprocessing.Queue()
    root = ft.Container(expand=True)
    page.add(root)

    def apply_theme():
        c = get_theme_colors(state["theme"])
        page.bgcolor = c["bg"]
        page.theme_mode = ft.ThemeMode.LIGHT if state["theme"] == 0 else ft.ThemeMode.DARK
        page.update()

    def cycle_theme(e):
        state["theme"] = (state["theme"] + 1) % 3
        apply_theme()
        if state["view"] == "home":
            _render_home()
        elif state["view"] == "editor":
            _render_editor()
        elif state["view"] == "history":
            _render_history()
        elif state["view"] == "report":
            _render_report()

    apply_theme()

    async def listen_for_return():
        while True:
            try:
                msg = q_show_main.get_nowait()
                if msg == "show_main":
                    nonlocal data
                    data = load_data()
                    if state["view"] == "home":
                        _render_home()
                    elif state["view"] == "editor":
                        _render_editor()
                    elif state["view"] == "history":
                        _render_history()
                    elif state["view"] == "report":
                        _render_report()
                    page.window.visible = True
                    page.window.to_front()
                    page.update()
            except queue.Empty:
                pass
            await asyncio.sleep(0.5)

    page.run_task(listen_for_return)

    def background():
        c = get_theme_colors(state["theme"])
        if c["gradient"]:
            return ft.Container(expand=True, gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT, colors=c["gradient"]))
        return ft.Container(expand=True, bgcolor=c["bg"])

    def glass(content, padding=16, radius=18):
        c = get_theme_colors(state["theme"])
        return ft.Container(content=content, padding=ft.Padding.all(padding),
                            border_radius=radius, bgcolor=c["glass_bg"],
                            border=ft.Border.all(1, c["glass_border"]), expand=True)

    def make_button(text, icon, on_click, color):
        c = get_theme_colors(state["theme"])

        def on_hover(e):
            e.control.bgcolor = c["glass_border"] if e.data == "true" else c["glass_bg"]
            e.control.update()

        return ft.Container(
            content=ft.Row([
                ft.Icon(icon, color=color, size=28),
                ft.Text(text, font_family="Vazir Bold", size=19, color=c["text"], selectable=True),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=12),
            padding=ft.Padding.symmetric(horizontal=24, vertical=18),
            border_radius=20, bgcolor=c["glass_bg"],
            border=ft.Border.all(1, c["glass_border"]),
            on_click=on_click, on_hover=on_hover, expand=True,
        )

    def get_top_bar():
        c = get_theme_colors(state["theme"])
        return ft.Row([
            ft.IconButton(icon=ft.Icons.BRIGHTNESS_6, icon_color=c["icon"],
                          icon_size=28, tooltip="تغییر تم", on_click=cycle_theme),
        ], alignment=ft.MainAxisAlignment.END)

    def show_view(view_content):
        inner = ft.Container(content=view_content, expand=True)
        root.content = ft.Stack([
            background(),
            ft.Container(
                content=ft.Column([inner], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                  scroll=ft.ScrollMode.AUTO, expand=True),
                padding=ft.Padding.all(24), expand=True,
            ),
        ], expand=True)
        page.update()

    def launch_widget_for_date(target_date):
        page.window.visible = False
        p = multiprocessing.Process(
            target=show_floating_widget,
            args=(DATA_FILE, state["theme"], target_date, q_show_main),
            daemon=True,
        )
        p.start()

        if HAS_PYSTRAY:
            def on_tray_click(icon, item):
                if item.text == "نمایش برنامه اصلی":
                    page.window.visible = True
                    page.window.to_front()
                    page.update()
                    icon.stop()
                elif item.text == "خروج":
                    icon.stop()
                    os._exit(0)

            icon_path = os.path.join(ASSETS_DIR, "logo.ico")
            try:
                image = Image.open(icon_path)
            except Exception:
                image = Image.new('RGB', (64, 64), color='purple')

            menu = pystray.Menu(
                pystray.MenuItem("نمایش برنامه اصلی", on_tray_click, default=True),
                pystray.MenuItem("خروج", on_tray_click),
            )
            icon = pystray.Icon("roozchin", image, "روزچین", menu)
            threading.Thread(target=icon.run, daemon=True).start()

    # --- Home ---
    def _render_home():
        c = get_theme_colors(state["theme"])
        today = today_jalali()
        today_day = next((d for d in data["days"] if d["date"] == today), None)

        progress_text = ""
        if today_day:
            total = sum(len(cat["tasks"]) for cat in today_day.get("custom_categories", []))
            done = sum(1 for cat in today_day.get("custom_categories", []) for t in cat["tasks"] if t.get("done"))
            progress_text = to_persian_digits(f"امروز: {done} از {total} کار انجام شده")

        def new_day(e):
            t = today_jalali()
            day = next((d for d in data["days"] if d["date"] == t), None)
            if not day:
                day = {"date": t, "quote": "", "lesson": "",
                       "custom_categories": [], "created": datetime.now().isoformat()}
                data["days"].append(day)
                save_data(data)
            state["current_date"] = t
            show_editor()

        view = ft.Column([
            get_top_bar(),
            ft.Container(height=10),
            ft.Text("🌙", size=60, text_align=ft.TextAlign.CENTER, selectable=True),
            ft.Text("روزچین | برنامه ریز شخصی", font_family="Vazir Bold",
                    size=36, color=c["text"], text_align=ft.TextAlign.CENTER, selectable=True),
            ft.Text(format_date_long(today), font_family="Vazir",
                    size=18, color=c["text_sub"], text_align=ft.TextAlign.CENTER, selectable=True),
            ft.Container(height=10),
            ft.Text(progress_text, font_family="Vazir", size=16, color="#74B9FF",
                    text_align=ft.TextAlign.CENTER, selectable=True) if progress_text else ft.Container(),
            ft.Container(height=20),
            make_button("افزودن روز جدید / ویرایش امروز", ft.Icons.ADD_CIRCLE_OUTLINE, new_day, "#A29BFE"),
            ft.Container(height=14),
            make_button("بررسی روزهای قبل", ft.Icons.HISTORY, show_history, "#74B9FF"),
            ft.Container(height=14),
            make_button("گزارش عملکرد", ft.Icons.BAR_CHART, show_report, "#FDCB6E"),
            ft.Container(height=30),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10, expand=True)

        show_view(view)

    def show_home(e=None):
        state["view"] = "home"
        state["current_date"] = None
        _render_home()

    # --- Editor ---
    def _render_editor():
        c = get_theme_colors(state["theme"])
        day = next((d for d in data["days"] if d["date"] == state["current_date"]), None)
        if not day:
            show_home()
            return

        def save_quote(val):
            day["quote"] = val
            save_data(data)

        def save_lesson(val):
            day["lesson"] = val
            save_data(data)

        quote_field = ft.TextField(
            value=day.get("quote", ""), hint_text="جمله‌ی امروزت چیه؟",
            multiline=True, min_lines=2, max_lines=4,
            text_style=ft.TextStyle(font_family="Vazir", size=17, color=c["text"]),
            hint_style=ft.TextStyle(font_family="Vazir", color=c["text_sub"]),
            border=ft.NoInputBorder(), bgcolor="transparent",
            on_change=lambda e: save_quote(e.control.value),
        )
        lesson_field = ft.TextField(
            value=day.get("lesson", ""), hint_text="درس امروزت چی بود؟",
            multiline=True, min_lines=3, max_lines=6,
            text_style=ft.TextStyle(font_family="Vazir", size=17, color=c["text"]),
            hint_style=ft.TextStyle(font_family="Vazir", color=c["text_sub"]),
            border=ft.NoInputBorder(), bgcolor="transparent",
            on_change=lambda e: save_lesson(e.control.value),
        )

        new_cat_name = ft.TextField(
            hint_text="نام دسته بندی (مثلا تکالیف عربی)...",
            text_style=ft.TextStyle(font_family="Vazir", size=16, color=c["text"]),
            hint_style=ft.TextStyle(font_family="Vazir", color=c["text_sub"]),
            border=ft.NoInputBorder(), bgcolor=c["glass_border"], border_radius=10, expand=True,
        )

        type_icons_row = ft.Row(spacing=10, wrap=True)

        def select_type(t):
            state["new_cat_type"] = t
            render_new_cat_icons()

        def render_new_cat_icons():
            type_icons_row.controls.clear()
            for t in CATEGORIES:
                is_sel = state["new_cat_type"] == t
                type_icons_row.controls.append(ft.Container(
                    content=ft.Icon(CATEGORY_ICONS[t],
                                    color=CATEGORY_COLORS[t] if is_sel else c["text_sub"], size=24),
                    padding=10, border_radius=10,
                    bgcolor=f"#22{CATEGORY_COLORS[t][1:]}" if is_sel else c["glass_border"],
                    border=ft.Border.all(1, CATEGORY_COLORS[t] if is_sel else "transparent"),
                    on_click=lambda e, _t=t: select_type(_t),
                ))
            page.update()

        def add_new_cat(e):
            name = new_cat_name.value.strip()
            if not name:
                return
            day["custom_categories"].append({
                "id": str(datetime.now().timestamp()), "name": name,
                "type": state["new_cat_type"], "tasks": [], "expanded": True,
            })
            save_data(data)
            new_cat_name.value = ""
            render_categories()
            page.update()

        add_cat_box = glass(ft.Column([
            ft.Text("افزودن دسته بندی", font_family="Vazir Bold", size=16,
                    color=c["text_sub"], selectable=True),
            ft.Row([new_cat_name, ft.IconButton(ft.Icons.ADD_CIRCLE, icon_color="#74B9FF",
                                                icon_size=32, on_click=add_new_cat)]),
            ft.Text("انتخاب آیکون برای دسته:", font_family="Vazir", size=14,
                    color=c["text_sub"], selectable=True),
            type_icons_row,
        ], spacing=8), padding=16)

        categories_column = ft.Column(spacing=12)

        def render_categories():
            categories_column.controls.clear()
            for cat in day["custom_categories"]:
                categories_column.controls.append(render_category(cat))
            page.update()

        def render_category(cat):
            tasks = cat["tasks"]
            is_expanded = cat.get("expanded", True)
            color = CATEGORY_COLORS.get(cat["type"], "#74B9FF")
            icon = CATEGORY_ICONS.get(cat["type"], ft.Icons.CATEGORY)

            def toggle(e):
                cat["expanded"] = not cat["expanded"]
                save_data(data)
                render_categories()

            def delete_cat(e):
                day["custom_categories"] = [ci for ci in day["custom_categories"] if ci["id"] != cat["id"]]
                save_data(data)
                render_categories()

            header = ft.Container(content=ft.Row([
                ft.Container(width=4, height=36, bgcolor=color, border_radius=2),
                ft.Icon(icon, color=color, size=24),
                ft.Text(cat["name"], font_family="Vazir Bold", size=18,
                        color=c["text"], expand=True, selectable=True),
                ft.Container(content=ft.Text(to_persian_digits(str(len(tasks))),
                                             font_family="Vazir Bold", size=14,
                                             color=color, selectable=True),
                             padding=ft.Padding.symmetric(horizontal=10, vertical=2),
                             border_radius=10, bgcolor=f"#22{color[1:]}"),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="#CC8888",
                              icon_size=22, on_click=delete_cat),
                ft.Icon(ft.Icons.EXPAND_LESS if is_expanded else ft.Icons.EXPAND_MORE,
                        color=c["text_sub"], size=24),
            ], spacing=10), on_click=toggle)

            contents = [header]

            if is_expanded:
                task_list = ft.Column(spacing=6)
                for i, task in enumerate(tasks):
                    def make_handlers(idx):
                        def toggle_task(e):
                            cat["tasks"][idx]["done"] = not cat["tasks"][idx].get("done", False)
                            save_data(data)
                            render_categories()

                        def del_task(e):
                            cat["tasks"].pop(idx)
                            save_data(data)
                            render_categories()
                        return toggle_task, del_task

                    tt, dt = make_handlers(i)
                    task_list.controls.append(ft.Container(
                        content=ft.Row([
                            ft.Checkbox(value=task.get("done", False), on_change=tt),
                            ft.Text(task["text"], expand=True, selectable=True,
                                    style=ft.TextStyle(font_family="Vazir", size=16, color=c["text"],
                                                       decoration=ft.TextDecoration.LINE_THROUGH
                                                       if task.get("done") else None)),
                            ft.IconButton(ft.Icons.CLOSE, icon_size=18,
                                          icon_color="#CC8888", on_click=dt),
                        ]),
                        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                        border_radius=10, bgcolor=c["glass_border"],
                    ))

                if not tasks:
                    task_list.controls.append(ft.Text("هنوز کاری اضافه نکردی", font_family="Vazir",
                                                      size=14, color=c["text_sub"],
                                                      text_align=ft.TextAlign.CENTER, selectable=True))

                def make_add_handler(category):
                    def add_task(e):
                        val = e.control.value.strip()
                        if not val:
                            return
                        category["tasks"].append({"text": val, "done": False})
                        save_data(data)
                        e.control.value = ""
                        render_categories()
                    return add_task

                add_input = ft.TextField(
                    hint_text="کار جدید برای این دسته...",
                    text_style=ft.TextStyle(font_family="Vazir", size=15, color=c["text"]),
                    hint_style=ft.TextStyle(font_family="Vazir", color=c["text_sub"]),
                    border=ft.NoInputBorder(), bgcolor=c["glass_border"],
                    border_radius=10, on_submit=make_add_handler(cat),
                )
                contents.extend([ft.Container(height=10), task_list,
                                 ft.Container(height=8), add_input])

            return ft.Container(
                content=ft.Column(contents, spacing=0),
                padding=ft.Padding.all(14), border_radius=16,
                bgcolor=c["glass_bg"], border=ft.Border.all(1, c["glass_border"]), expand=True,
            )

        render_new_cat_icons()
        render_categories()

        view = ft.Column([
            ft.Row([
                ft.IconButton(ft.Icons.ARROW_BACK, on_click=show_home,
                              icon_color=c["icon"], tooltip="بازگشت", icon_size=28),
                ft.Text(format_date_long(day["date"]), font_family="Vazir Bold",
                        size=20, color=c["text"], expand=True, selectable=True),
                ft.IconButton(ft.Icons.WIDGETS, icon_color="#00B894", icon_size=28,
                              tooltip="نمایش به صورت ویجت دسکتاپ",
                              on_click=lambda e: launch_widget_for_date(day["date"])),
                get_top_bar(),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            glass(ft.Column([
                ft.Text("📅", size=32, text_align=ft.TextAlign.CENTER, selectable=True),
                ft.Text(format_date_long(day["date"]), font_family="Vazir Bold",
                        size=22, color=c["text"], text_align=ft.TextAlign.CENTER, selectable=True),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4), padding=20, radius=20),
            glass(ft.Column([
                ft.Text("💭 جمله امروز", font_family="Vazir Bold", size=16,
                        color=c["text_sub"], selectable=True),
                quote_field,
            ], spacing=4), padding=16),
            add_cat_box,
            categories_column,
            glass(ft.Column([
                ft.Text("📚 درس امروز", font_family="Vazir Bold", size=16,
                        color=c["text_sub"], selectable=True),
                lesson_field,
            ], spacing=4), padding=16),
        ], spacing=12, expand=True)

        show_view(view)

    def show_editor():
        state["view"] = "editor"
        _render_editor()

    # --- History ---
    def _render_history():
        c = get_theme_colors(state["theme"])
        sorted_days = sorted(data["days"], key=lambda d: d["date"], reverse=True)

        if not sorted_days:
            items = [ft.Container(
                content=ft.Text("هنوز روزی ثبت نکردی 💤", font_family="Vazir",
                                size=16, color=c["text_sub"],
                                text_align=ft.TextAlign.CENTER, selectable=True),
                padding=60, alignment=ft.Alignment.CENTER,
            )]
        else:
            items = []
            for d in sorted_days:
                def make_open(date):
                    def open_day(e):
                        state["current_date"] = date
                        show_editor()
                    return open_day

                total = sum(len(cat["tasks"]) for cat in d.get("custom_categories", []))
                done = sum(1 for cat in d.get("custom_categories", []) for t in cat["tasks"] if t.get("done"))
                quote = d.get("quote", "").strip() or "—"

                items.append(ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Column([
                                ft.Text(format_date_long(d["date"]), font_family="Vazir Bold",
                                        size=16, color=c["text"], selectable=True),
                                ft.Text(quote[:60] + ("..." if len(quote) > 60 else ""),
                                        font_family="Vazir", size=14, color=c["text_sub"],
                                        selectable=True),
                            ], spacing=4, expand=True),
                            ft.IconButton(ft.Icons.WIDGETS, icon_color="#00B894", icon_size=22,
                                          tooltip="ویجت این روز",
                                          on_click=lambda e, _d=d["date"]: launch_widget_for_date(_d)),
                            ft.Icon(ft.Icons.CHEVRON_LEFT, color=c["text_sub"], size=24),
                        ]),
                        ft.Container(height=8),
                        ft.Row([
                            ft.ProgressBar(value=(done / total) if total else 0, expand=True,
                                           color="#74B9FF", bgcolor=c["glass_border"], height=8),
                            ft.Text(to_persian_digits(f"{done}/{total}"), font_family="Vazir Bold",
                                    size=13, color="#74B9FF", selectable=True),
                        ], spacing=10),
                    ], spacing=4),
                    padding=ft.Padding.all(16), border_radius=16,
                    bgcolor=c["glass_bg"], border=ft.Border.all(1, c["glass_border"]),
                    on_click=make_open(d["date"]), expand=True,
                ))

        view = ft.Column([
            ft.Row([
                ft.IconButton(ft.Icons.ARROW_BACK, on_click=show_home,
                              icon_color=c["icon"], tooltip="بازگشت", icon_size=28),
                ft.Text("📚 روزهای قبل", font_family="Vazir Bold",
                        size=22, color=c["text"], expand=True, selectable=True),
                get_top_bar(),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Column(items, spacing=12),
        ], spacing=12, expand=True)

        show_view(view)

    def show_history(e=None):
        state["view"] = "history"
        _render_history()

    # --- Monthly Report ---
    def _render_report():
        c = get_theme_colors(state["theme"])

        if state.get("report_year") is None:
            if data["days"]:
                latest = max(data["days"], key=lambda d: d["date"])
                parts = latest["date"].split("/")
                state["report_year"] = int(parts[0])
                state["report_month"] = int(parts[1])
            else:
                tp = today_jalali().split("/")
                state["report_year"] = int(tp[0])
                state["report_month"] = int(tp[1])

        year = state["report_year"]
        month = state["report_month"]

        def prev_month(e):
            m, y = state["report_month"] - 1, state["report_year"]
            if m < 1:
                m = 12
                y -= 1
            state["report_month"], state["report_year"] = m, y
            _render_report()

        def next_month(e):
            m, y = state["report_month"] + 1, state["report_year"]
            if m > 12:
                m = 1
                y += 1
            state["report_month"], state["report_year"] = m, y
            _render_report()

        def set_cat_filter(name):
            state["report_cat"] = name
            _render_report()

        month_prefix = f"{year}/{month:02d}/"
        month_days = [d for d in data["days"] if d["date"].startswith(month_prefix)]

        available_cats = []
        for d in month_days:
            for cat in d.get("custom_categories", []):
                if cat["name"] not in available_cats:
                    available_cats.append(cat["name"])
        if state["report_cat"] is not None and state["report_cat"] not in available_cats:
            available_cats.append(state["report_cat"])

        cat_filter = state["report_cat"]

        total_tasks = 0
        completed_tasks = 0
        daily = {}
        cat_stats = {}

        if month <= 6:
            last_day = 31
        elif month <= 11:
            last_day = 30
        else:
            last_day = 30

        for day_num in range(1, last_day + 1):
            daily[day_num] = [0, 0]

        for d in month_days:
            try:
                day_num = int(d["date"].split("/")[2])
            except Exception:
                continue
            for cat in d.get("custom_categories", []):
                if cat_filter is not None and cat["name"] != cat_filter:
                    continue
                name = cat["name"]
                if name not in cat_stats:
                    cat_stats[name] = {
                        "total": 0, "done": 0,
                        "color": CATEGORY_COLORS.get(cat["type"], "#74B9FF"),
                        "icon": CATEGORY_ICONS.get(cat["type"], ft.Icons.CATEGORY),
                    }
                for t in cat.get("tasks", []):
                    total_tasks += 1
                    cat_stats[name]["total"] += 1
                    if day_num in daily:
                        daily[day_num][0] += 1
                    if t.get("done"):
                        completed_tasks += 1
                        cat_stats[name]["done"] += 1
                        if day_num in daily:
                            daily[day_num][1] += 1

        percentage = (completed_tasks / total_tasks * 100) if total_tasks else 0
        active_days = sum(1 for dn in daily if daily[dn][0] > 0)

        best_days = sorted(
            [(dn, v) for dn, v in daily.items() if v[0] > 0],
            key=lambda x: (x[1][1], x[1][0]),
            reverse=True,
        )[:3]

        def stat_card(icon, label, value, color):
            return ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Icon(icon, color=color, size=22),
                        width=44, height=44, bgcolor=f"#22{color[1:]}",
                        border_radius=22, alignment=ft.Alignment.CENTER,
                    ),
                    ft.Text(value, font_family="Vazir Bold", size=22,
                            color=c["text"], text_align=ft.TextAlign.CENTER),
                    ft.Text(label, font_family="Vazir", size=11,
                            color=c["text_sub"], text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                padding=ft.Padding.symmetric(horizontal=12, vertical=14),
                border_radius=16, bgcolor=c["glass_bg"],
                border=ft.Border.all(1, c["glass_border"]), expand=True,
            )

        def cat_chip(label, active, color, on_click):
            return ft.Container(
                content=ft.Text(
                    label, size=13,
                    font_family="Vazir Bold" if active else "Vazir",
                    color="#FFFFFF" if active else c["text_sub"],
                ),
                padding=ft.Padding.symmetric(horizontal=14, vertical=6),
                bgcolor=color if active else c["glass_bg"],
                border=ft.Border.all(1, color if active else c["glass_border"]),
                border_radius=20, on_click=on_click,
            )

        def bar_color(pct):
            if pct >= 0.75:
                return "#00B894"
            elif pct >= 0.40:
                return "#FDCB6E"
            elif pct > 0:
                return "#FF6B9D"
            return c["glass_border"]

        bars = []
        for day_num in range(1, last_day + 1):
            t_total, t_done = daily[day_num]
            if t_total > 0:
                pct = t_done / t_total
                color = bar_color(pct)
                h = max(6, int(pct * 100))
            else:
                color = c["glass_border"]
                h = 4

            bars.append(ft.Column([
                ft.Container(
                    height=110, width=18,
                    alignment=ft.Alignment.BOTTOM_CENTER,
                    content=ft.Container(
                        width=14, height=h,
                        bgcolor=color, border_radius=4,
                    ),
                ),
                ft.Text(to_persian_digits(str(day_num)), size=9,
                        color=c["text_sub"], font_family="Vazir"),
            ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER))

        cat_rows = []
        for name, st in cat_stats.items():
            pct = st["done"] / st["total"] if st["total"] else 0
            cat_rows.append(ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(st["icon"], color=st["color"], size=18),
                        ft.Text(name, font_family="Vazir Bold", size=14,
                                color=c["text"], expand=True),
                        ft.Text(to_persian_digits(f"{st['done']}/{st['total']}"),
                                font_family="Vazir", size=13, color=st["color"]),
                    ], spacing=8),
                    ft.ProgressBar(value=pct, color=st["color"],
                                   bgcolor=c["glass_border"], height=6, border_radius=3),
                ], spacing=6),
                padding=ft.Padding.symmetric(vertical=6),
            ))

        best_items = []
        for dn, (tt, td) in best_days:
            best_items.append(ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Text(to_persian_digits(str(dn)),
                                        font_family="Vazir Bold", size=18, color="#FFFFFF"),
                        width=44, height=44, bgcolor="#74B9FF",
                        border_radius=22, alignment=ft.Alignment.CENTER,
                    ),
                    ft.Column([
                        ft.Text(f"{JALALI_MONTHS[month - 1]} {to_persian_digits(str(dn))}",
                                font_family="Vazir Bold", size=14, color=c["text"]),
                        ft.Text(to_persian_digits(f"{td} از {tt} کار انجام شده"),
                                font_family="Vazir", size=12, color=c["text_sub"]),
                    ], spacing=2, expand=True),
                ], spacing=12),
                padding=ft.Padding.symmetric(vertical=6),
            ))

        month_name_fa = JALALI_MONTHS[month - 1] if 1 <= month <= 12 else str(month)

        view = ft.Column([
            ft.Row([
                ft.IconButton(ft.Icons.ARROW_BACK, on_click=show_home,
                              icon_color=c["icon"], tooltip="بازگشت", icon_size=28),
                ft.Text("📊 گزارش عملکرد", font_family="Vazir Bold",
                        size=22, color=c["text"], expand=True, selectable=True),
                get_top_bar(),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

            ft.Container(
                content=ft.Row([
                    ft.IconButton(ft.Icons.CHEVRON_RIGHT, on_click=prev_month,
                                  icon_color=c["text"], icon_size=28, tooltip="ماه قبل"),
                    ft.Column([
                        ft.Text(month_name_fa, font_family="Vazir Bold", size=20,
                                color=c["text"], text_align=ft.TextAlign.CENTER),
                        ft.Text(to_persian_digits(str(year)), font_family="Vazir",
                                size=13, color=c["text_sub"], text_align=ft.TextAlign.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True, spacing=0),
                    ft.IconButton(ft.Icons.CHEVRON_LEFT, on_click=next_month,
                                  icon_color=c["text"], icon_size=28, tooltip="ماه بعد"),
                ]),
                padding=ft.Padding.symmetric(vertical=10, horizontal=8),
                bgcolor=c["glass_bg"], border_radius=14,
                border=ft.Border.all(1, c["glass_border"]),
            ),

            ft.Row([
                stat_card(ft.Icons.LIST_ALT, "کل کارها",
                          to_persian_digits(str(total_tasks)), "#74B9FF"),
                stat_card(ft.Icons.CHECK_CIRCLE, "انجام شده",
                          to_persian_digits(str(completed_tasks)), "#00B894"),
            ], spacing=10),
            ft.Row([
                stat_card(ft.Icons.PERCENT, "درصد موفقیت",
                          to_persian_digits(f"{int(round(percentage))}") + "٪", "#A29BFE"),
                stat_card(ft.Icons.CALENDAR_MONTH, "روزهای فعال",
                          to_persian_digits(str(active_days)), "#FDCB6E"),
            ], spacing=10),

            ft.Container(
                content=ft.Column([
                    ft.Text("🎯 فیلتر دسته‌بندی", font_family="Vazir Bold", size=14,
                            color=c["text_sub"], selectable=True),
                    ft.Row([
                        cat_chip("همه", cat_filter is None, c["text"],
                                 lambda e: set_cat_filter(None)),
                        *[cat_chip(
                            cat_name,
                            cat_filter == cat_name,
                            CATEGORY_COLORS.get(
                                next((cc["type"] for dd in month_days
                                      for cc in dd.get("custom_categories", [])
                                      if cc["name"] == cat_name), "تحصیل"),
                                "#74B9FF"),
                            (lambda e, n=cat_name: set_cat_filter(n)),
                        ) for cat_name in available_cats],
                    ], spacing=8, wrap=True, run_spacing=8),
                ], spacing=10),
                padding=ft.Padding.all(14),
                bgcolor=c["glass_bg"], border_radius=14,
                border=ft.Border.all(1, c["glass_border"]),
            ),

            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text("📈 عملکرد روزانه", font_family="Vazir Bold",
                                size=16, color=c["text_sub"], expand=True, selectable=True),
                        ft.Row([
                            ft.Container(width=8, height=8, bgcolor="#00B894", border_radius=4),
                            ft.Text("≥۷۵٪", font_family="Vazir", size=10, color=c["text_sub"]),
                            ft.Container(width=8, height=8, bgcolor="#FDCB6E", border_radius=4),
                            ft.Text("۴۰-۷۵٪", font_family="Vazir", size=10, color=c["text_sub"]),
                            ft.Container(width=8, height=8, bgcolor="#FF6B9D", border_radius=4),
                            ft.Text("<۴۰٪", font_family="Vazir", size=10, color=c["text_sub"]),
                        ], spacing=6),
                    ]),
                    ft.Container(
                        content=ft.Row(bars, spacing=3, wrap=True, run_spacing=6,
                                       alignment=ft.MainAxisAlignment.CENTER),
                        padding=ft.Padding.only(top=10),
                    ) if any(v[0] > 0 for v in daily.values())
                    else ft.Container(
                        content=ft.Text("داده‌ای برای این ماه ثبت نشده 💤",
                                        font_family="Vazir", size=14, color=c["text_sub"],
                                        text_align=ft.TextAlign.CENTER),
                        padding=40, alignment=ft.Alignment.CENTER,
                    ),
                ], spacing=8),
                padding=ft.Padding.all(16),
                bgcolor=c["glass_bg"], border_radius=16,
                border=ft.Border.all(1, c["glass_border"]),
            ),

            ft.Container(
                content=ft.Column([
                    ft.Text("🏷️ تفکیک دسته‌بندی", font_family="Vazir Bold",
                            size=16, color=c["text_sub"], selectable=True),
                    *(cat_rows if cat_rows else [
                        ft.Text("دسته‌ای ثبت نشده", font_family="Vazir",
                                size=13, color=c["text_sub"],
                                text_align=ft.TextAlign.CENTER),
                    ]),
                ], spacing=8),
                padding=ft.Padding.all(16),
                bgcolor=c["glass_bg"], border_radius=16,
                border=ft.Border.all(1, c["glass_border"]),
            ) if cat_rows else ft.Container(),

            ft.Container(
                content=ft.Column([
                    ft.Text("🏆 بهترین روزها", font_family="Vazir Bold",
                            size=16, color=c["text_sub"], selectable=True),
                    *best_items,
                ], spacing=6),
                padding=ft.Padding.all(16),
                bgcolor=c["glass_bg"], border_radius=16,
                border=ft.Border.all(1, c["glass_border"]),
            ) if best_items else ft.Container(),

            ft.Container(height=20),
        ], spacing=12, expand=True)

        show_view(view)

    def show_report(e=None):
        state["view"] = "report"
        _render_report()

    # --- Init: splash then home ---
    async def play_splash():
        win_w = page.window.width or 900
        win_h = page.window.height or 720
        base = min(win_w, win_h)

        logo_size = max(80, min(170, int(base * 0.24)))
        name_size = max(30, min(58, int(win_w * 0.065)))
        sub_size = max(13, min(20, int(win_w * 0.022)))

        # --- لوگو: fade آرام ---
        logo_wrapper = ft.Container(
            content=ft.Image(src="logo.ico", width=logo_size, height=logo_size),
            opacity=0,
            animate_opacity=ft.Animation(1400, ft.AnimationCurve.EASE_IN_OUT),
            alignment=ft.Alignment.CENTER,
        )

        # --- اسم: fade ---
        name_text = ft.Text(
            "روزچین",
            size=name_size,
            font_family="Vazir Bold",
            color="#FFFFFF",
            text_align=ft.TextAlign.CENTER,
            opacity=0,
            animate_opacity=ft.Animation(700, ft.AnimationCurve.EASE_OUT),
        )

        # --- زیرنویس: fade ---
        subtitle = ft.Text(
            "برنامه‌ریز شخصی روزانه",
            size=sub_size,
            font_family="Vazir",
            color="#AAAADD",
            text_align=ft.TextAlign.CENTER,
            opacity=0,
            animate_opacity=ft.Animation(700, ft.AnimationCurve.EASE_OUT),
        )

        # --- سه نقطه لودینگ ---
        def make_dot():
            return ft.Container(
                width=10, height=10, bgcolor="#74B9FF", border_radius=5,
                opacity=0.3,
                animate_opacity=ft.Animation(250, ft.AnimationCurve.EASE_IN_OUT),
            )

        dot1, dot2, dot3 = make_dot(), make_dot(), make_dot()
        dots_row = ft.Row(
            [dot1, dot2, dot3],
            spacing=10,
            alignment=ft.MainAxisAlignment.CENTER,
            opacity=0,
            animate_opacity=ft.Animation(400, ft.AnimationCurve.EASE_IN),
        )

        content_column = ft.Column(
            [
                logo_wrapper,
                ft.Container(height=int(base * 0.03)),
                name_text,
                ft.Container(height=int(base * 0.015)),
                subtitle,
                ft.Container(height=int(base * 0.04)),
                dots_row,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )

        splash_root = ft.Container(
            content=content_column,
            expand=True,
            alignment=ft.Alignment.CENTER,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=["#0F0C29", "#302B63", "#24243E"],
            ),
        )

        root.content = splash_root
        page.update()

        # ۱) لوگو fade-in
        await asyncio.sleep(0.2)
        logo_wrapper.opacity = 1
        page.update()
        await asyncio.sleep(1.4)

        # ۲) اسم fade-in
        name_text.opacity = 1
        page.update()
        await asyncio.sleep(0.8)

        # ۳) زیرنویس fade-in
        subtitle.opacity = 1
        page.update()
        await asyncio.sleep(0.6)

        # ۴) سه نقطه ظاهر می‌شن و حرکت می‌کنن
        dots_row.opacity = 1
        page.update()

        dots = [dot1, dot2, dot3]
        loading_time = 2.0
        elapsed = 0.0
        step = 0.16
        i = 0
        while elapsed < loading_time:
            for j, d in enumerate(dots):
                d.opacity = 1 if j == (i % 3) else 0.3
            page.update()
            await asyncio.sleep(step)
            elapsed += step
            i += 1

        # همه سه نقطه روشن، یه لحظه
        for d in dots:
            d.opacity = 1
        page.update()
        await asyncio.sleep(0.2)

        # ۵) محو شدن کل splash
        splash_root.animate_opacity = ft.Animation(700, ft.AnimationCurve.EASE_IN)
        splash_root.opacity = 0
        page.update()
        await asyncio.sleep(0.75)

        # ۶) رفتن به منو
        show_home()

    page.run_task(play_splash)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    ft.run(main, assets_dir=ASSETS_DIR)