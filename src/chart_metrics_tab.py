# src/chart_metrics_tab.py
# Вкладка "График по периодам" (day/week/month).
# Легаси-метрики (role_metrics / sub_role_metrics) не используются.
#
# Настройки фильтра (скрытые роли, показ attention/satisfaction) общие
# с «График метрик» (chart_tab.py) — хранятся в prefs под ключами
# chart_hidden_roles / chart_show_att / chart_show_sat.
#
# Двойной клик по фигуре открывает окно «Метрика: {name}»:
#   - шапка (роль, подроль, режим, период, satisfaction, attention);
#   - две таблицы индикаторов: слева — Attention, справа — Satisfaction;
#   - колонки «Тип источника» + «Значение» (имя типа / имя обязанности / текст вопроса);
#   - под каждой — своя формула Σ(score × weight) / Σweight.
# Геометрия окна сохраняется в prefs (chart_info_geometry).

import math
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from tksheet import Sheet

from .chart_repo import ChartRepository
from .roles_repo import RolesRepository
from .preferences_repo import PreferencesRepository
from .indicator_repo import IndicatorRepository
from .activity_types_repo import ActivityTypesRepository
from .regular_duties_repo import RegularDutiesRepository
from .questions_repo import QuestionsRepository
from .score_calculator import ScoreCalculator

from .ui_utils import format_period_label


class ChartMetricsTab(tk.Frame):
    MODE_DAY = "day"
    MODE_WEEK = "week"
    MODE_MONTH = "month"
    VALID_MODES = (MODE_DAY, MODE_WEEK, MODE_MONTH)

    def __init__(self, parent, chart_repo: ChartRepository,
                 roles_repo: RolesRepository,
                 prefs_repo: PreferencesRepository,
                 indicator_repo: IndicatorRepository,
                 types_repo: ActivityTypesRepository,
                 duties_repo: RegularDutiesRepository):
        super().__init__(parent)
        self.chart_repo = chart_repo
        self.roles_repo = roles_repo
        self.prefs_repo = prefs_repo
        self.indicator_repo = indicator_repo
        self.types_repo = types_repo
        self.duties_repo = duties_repo
        self.questions_repo = QuestionsRepository(indicator_repo.db)

        self.data = []
        self.hidden_roles = set()
        self.show_att = True
        self.show_sat = True

        self.current_mode = None
        self.current_period_id = None
        self.current_period_value = None
        self._current_periods = []
        self._suppress_events = False

        self._build_ui()
        self._restore_state()

    # ------------------------------------------------------------
    # UI
    # ------------------------------------------------------------
    def _build_ui(self):
        frame_top = tk.Frame(self)
        frame_top.pack(fill="x", padx=10, pady=5)

        tk.Label(frame_top, text="Режим:").pack(side="left")
        self.mode_var = tk.StringVar(value=self.MODE_DAY)
        tk.Radiobutton(frame_top, text="День", variable=self.mode_var, value=self.MODE_DAY,
                       command=self._on_mode_changed).pack(side="left", padx=2)
        tk.Radiobutton(frame_top, text="Неделя", variable=self.mode_var, value=self.MODE_WEEK,
                       command=self._on_mode_changed).pack(side="left", padx=2)
        tk.Radiobutton(frame_top, text="Месяц", variable=self.mode_var, value=self.MODE_MONTH,
                       command=self._on_mode_changed).pack(side="left", padx=2)

        tk.Label(frame_top, text="Период:").pack(side="left", padx=(15, 0))
        self.cb_period = ttk.Combobox(frame_top, state="readonly", width=45)
        self.cb_period.pack(side="left", padx=5)
        self.cb_period.bind("<<ComboboxSelected>>", self._on_period_changed)

        self.btn_refresh = tk.Button(frame_top, text="Обновить", command=self.refresh_data)
        self.btn_refresh.pack(side="left", padx=5)

        self.btn_filter = tk.Button(frame_top, text="Фильтр", command=self.open_filter_dialog)
        self.btn_filter.pack(side="left", padx=5)

        lbl_hint = tk.Label(frame_top,
                            text="(Двойной клик по фигуре — информация)",
                            fg="gray")
        lbl_hint.pack(side="right", padx=5)

        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)

        self.drawn_items = []

    # ------------------------------------------------------------
    # Сохранение / восстановление состояния
    # ------------------------------------------------------------
    def _restore_state(self):
        saved_mode = self.prefs_repo.get("chart_mode")
        if saved_mode not in self.VALID_MODES:
            saved_mode = self.MODE_DAY
        self.current_mode = saved_mode
        self.mode_var.set(saved_mode)

        hidden = self.prefs_repo.get("chart_hidden_roles")
        if isinstance(hidden, list):
            self.hidden_roles = set(int(x) for x in hidden if x is not None)
        else:
            self.hidden_roles = set()

        show_att = self.prefs_repo.get("chart_show_att")
        self.show_att = True if show_att is None else bool(show_att)
        show_sat = self.prefs_repo.get("chart_show_sat")
        self.show_sat = True if show_sat is None else bool(show_sat)

        self._refresh_periods()

    def _save_filter_state(self):
        self.prefs_repo.set("chart_hidden_roles", sorted(self.hidden_roles))
        self.prefs_repo.set("chart_show_att", self.show_att)
        self.prefs_repo.set("chart_show_sat", self.show_sat)

    def _get_saved_period(self, mode: str):
        saved = self.prefs_repo.get("chart_periods")
        if isinstance(saved, dict):
            return saved.get(mode)
        return None

    def _save_period(self, mode: str, period_value: str):
        saved = self.prefs_repo.get("chart_periods")
        if not isinstance(saved, dict):
            saved = {}
        saved = dict(saved)
        saved[mode] = period_value
        self.prefs_repo.set("chart_periods", saved)

    # ------------------------------------------------------------
    # Загрузка данных
    # ------------------------------------------------------------
    def _refresh_periods(self):
        self._suppress_events = True
        try:
            mode = self.current_mode
            periods = self.chart_repo.get_available_periods(mode)
            self._current_periods = periods

            labels = [format_period_label(mode, p) for p in periods]
            self.cb_period['values'] = labels

            if not periods:
                self.cb_period.set("")
                self.current_period_id = None
                self.current_period_value = None
                self.data = []
                self._draw_canvas()
                return

            saved_value = self._get_saved_period(mode)
            selected_idx = 0
            if saved_value:
                for i, p in enumerate(periods):
                    if p[1] == saved_value:
                        selected_idx = i
                        break

            self.cb_period.current(selected_idx)
            self.current_period_id = periods[selected_idx][0]
            self.current_period_value = periods[selected_idx][1]
            self._load_data()
        finally:
            self._suppress_events = False

    def _load_data(self):
        if self.current_period_id is None:
            self.data = []
        else:
            self.data = self.chart_repo.get_metrics_for_period(
                self.current_mode, self.current_period_id
            )
        self._draw_canvas()

    # ------------------------------------------------------------
    # Обработчики
    # ------------------------------------------------------------
    def _on_mode_changed(self):
        if self._suppress_events:
            return
        new_mode = self.mode_var.get()
        if new_mode == self.current_mode or new_mode not in self.VALID_MODES:
            return
        self.current_mode = new_mode
        self.prefs_repo.set("chart_mode", new_mode)
        self._refresh_periods()

    def _on_period_changed(self, event=None):
        if self._suppress_events:
            return
        idx = self.cb_period.current()
        if idx < 0 or idx >= len(self._current_periods):
            return
        period = self._current_periods[idx]
        self.current_period_id = period[0]
        self.current_period_value = period[1]
        self._save_period(self.current_mode, self.current_period_value)
        self._load_data()

    def refresh_data(self):
        mode = self.mode_var.get()
        if mode not in self.VALID_MODES:
            mode = self.current_mode or self.MODE_DAY
        self.current_mode = mode
        self._refresh_periods()

    def _on_resize(self, event):
        self._draw_canvas()

    # ------------------------------------------------------------
    # Отрисовка
    # ------------------------------------------------------------
    def _is_overlap(self, box1, box2):
        return not (
            box1[2] <= box2[0] or box1[0] >= box2[2]
            or box1[3] <= box2[1] or box1[1] >= box2[3]
        )

    def _distribute_in_corner(self, items, corner, w, h, margin_x, margin_y, placed_boxes):
        cols = 3
        cell_w = margin_x / 3
        cell_h = margin_y / 2

        for i, item in enumerate(items):
            c = i % cols
            r = i // cols

            if corner == "bottom_left":
                cx = cell_w * 0.5 + c * cell_w
                cy = h - cell_h * 0.5 - r * cell_h
            elif corner == "top_right":
                cx = w - cell_w * 0.5 - c * cell_w
                cy = cell_h * 0.5 + r * cell_h
            else:
                continue

            item["draw_x"] = cx
            item["draw_y"] = cy

            placed_boxes.append((
                cx - item["box_w"] / 2,
                cy - item["box_h"] / 2,
                cx + item["box_w"] / 2,
                cy + item["box_h"] / 2
            ))

    def _distribute_in_rect(self, items, x1, y1, x2, y2, placed_boxes):
        if not items:
            return
        count = len(items)
        pad_x, pad_y = 40, 50
        x1, y1, x2, y2 = x1 + pad_x, y1 + pad_y, x2 - pad_x, y2 - pad_y

        cols = math.ceil(math.sqrt(count))
        rows = math.ceil(count / cols)

        step_x = (x2 - x1) / max(1, cols - 1) if cols > 1 else 0
        step_y = (y2 - y1) / max(1, rows - 1) if rows > 1 else 0

        for i, item in enumerate(items):
            if count == 1:
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            else:
                c = i % cols
                r = i // cols
                cx = x1 + c * step_x
                cy = y1 + r * step_y

                items_in_last_row = count % cols
                if r == rows - 1 and items_in_last_row > 0 and cols > 1:
                    offset = (cols - items_in_last_row) * step_x / 2
                    cx = x1 + offset + c * step_x

            item["draw_x"] = cx
            item["draw_y"] = cy

            placed_boxes.append((
                cx - item["box_w"] / 2,
                cy - item["box_h"] / 2,
                cx + item["box_w"] / 2,
                cy + item["box_h"] / 2
            ))

    def _place_on_edge_zone(self, items, edge, margin_x, margin_y, work_w, work_h, w, h, placed_boxes):
        """Каскадное размещение метрик в краевой зоне (bottom/top/left/right)."""
        if not items:
            return

        gap = 4

        for item in items:
            att = float(item["attention"])
            sat = float(item["satisfaction"])
            bw, bh = item["box_w"], item["box_h"]

            ideal_x = margin_x + (sat / 100.0) * work_w
            ideal_y = (h - margin_y) - (att / 100.0) * work_h

            if edge == "bottom":
                offsets = [0, -(bh + gap)]
                perp, along = "y", "x"
                step = bw + gap
            elif edge == "top":
                offsets = [0, (bh + gap)]
                perp, along = "y", "x"
                step = bw + gap
            elif edge == "left":
                offsets = [0, (bw + gap)]
                perp, along = "x", "y"
                step = bh + gap
            else:  # right
                offsets = [0, -(bw + gap)]
                perp, along = "x", "y"
                step = bh + gap

            def in_bounds(cx, cy):
                return (cx - bw / 2 >= 0 and cx + bw / 2 <= w
                        and cy - bh / 2 >= 0 and cy + bh / 2 <= h)

            def is_free(cx, cy):
                box = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
                return not any(self._is_overlap(box, pb) for pb in placed_boxes)

            def place(cx, cy):
                item["draw_x"] = cx
                item["draw_y"] = cy
                placed_boxes.append((
                    cx - bw / 2, cy - bh / 2,
                    cx + bw / 2, cy + bh / 2
                ))

            placed = False
            for off in offsets:
                if perp == "y":
                    cx, cy = ideal_x, ideal_y + off
                else:
                    cx, cy = ideal_x + off, ideal_y
                if in_bounds(cx, cy) and is_free(cx, cy):
                    place(cx, cy)
                    placed = True
                    break
            if placed:
                continue

            for i in range(1, 100):
                for off in offsets:
                    for sign in (+1, -1):
                        if along == "x":
                            cx = ideal_x + sign * i * step
                            cy = ideal_y + off
                        else:
                            cx = ideal_x + off
                            cy = ideal_y + sign * i * step
                        if in_bounds(cx, cy) and is_free(cx, cy):
                            place(cx, cy)
                            placed = True
                            break
                    if placed:
                        break
                if placed:
                    break

            if not placed:
                place(ideal_x, ideal_y)

    def _draw_canvas(self):
        self.canvas.delete("all")
        self.drawn_items.clear()

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()

        if w < 100 or h < 100:
            return

        margin_x = w * 0.15
        margin_y = h * 0.15
        work_w = w * 0.7
        work_h = h * 0.7

        base_w = margin_x / 3
        base_h = margin_y / 2

        self.canvas.create_rectangle(margin_x, margin_y, w - margin_x, h - margin_y,
                                     outline="#aaaaaa", dash=(4, 4))
        self.canvas.create_line(margin_x, 0, margin_x, h, fill="#aaaaaa", dash=(4, 4))
        self.canvas.create_line(w - margin_x, 0, w - margin_x, h, fill="#aaaaaa", dash=(4, 4))
        self.canvas.create_line(0, margin_y, w, margin_y, fill="#aaaaaa", dash=(4, 4))
        self.canvas.create_line(0, h - margin_y, w, h - margin_y, fill="#aaaaaa", dash=(4, 4))

        self.canvas.create_text(margin_x - 5, h - margin_y + 5,
                                text="0,0", anchor="ne", fill="#888888")
        self.canvas.create_text(w - margin_x + 5, margin_y - 5,
                                text="100,100", anchor="sw", fill="#888888")

        sorted_data = sorted(self.data, key=lambda x: 0 if x["type"] == "role" else 1)

        for item in sorted_data:
            if item["type"] == "role":
                item["box_w"] = base_w
                item["box_h"] = base_h
            else:
                item["box_w"] = base_w * 0.75
                item["box_h"] = base_h * 0.75

        zones = {
            "c00": [], "c0100": [], "c100": [], "c1000": [],
            "left": [], "right": [], "top": [], "bottom": [], "center": []
        }

        for item in sorted_data:
            if item["type"] == "role" and item["id"] in self.hidden_roles:
                continue
            if item["type"] == "sub_role" and item["parent_id"] in self.hidden_roles:
                continue

            att = float(item["attention"])
            sat = float(item["satisfaction"])

            if att == 0 and sat == 0:
                zones["c00"].append(item)
            elif att == 100 and sat == 0:
                zones["c0100"].append(item)
            elif att == 100 and sat == 100:
                zones["c100"].append(item)
            elif att == 0 and sat == 100:
                zones["c1000"].append(item)
            elif att == 0:
                zones["bottom"].append(item)
            elif att == 100:
                zones["top"].append(item)
            elif sat == 0:
                zones["left"].append(item)
            elif sat == 100:
                zones["right"].append(item)
            else:
                zones["center"].append(item)

        placed_boxes = []

        self._distribute_in_corner(zones["c00"], "bottom_left", w, h, margin_x, margin_y, placed_boxes)
        self._distribute_in_corner(zones["c100"], "top_right", w, h, margin_x, margin_y, placed_boxes)

        self._distribute_in_rect(zones["c0100"], 0, 0, margin_x, margin_y, placed_boxes)
        self._distribute_in_rect(zones["c1000"], w - margin_x, h - margin_y, w, h, placed_boxes)

        self._place_on_edge_zone(
            zones["bottom"], "bottom", margin_x, margin_y, work_w, work_h, w, h, placed_boxes
        )
        self._place_on_edge_zone(
            zones["top"], "top", margin_x, margin_y, work_w, work_h, w, h, placed_boxes
        )
        self._place_on_edge_zone(
            zones["left"], "left", margin_x, margin_y, work_w, work_h, w, h, placed_boxes
        )
        self._place_on_edge_zone(
            zones["right"], "right", margin_x, margin_y, work_w, work_h, w, h, placed_boxes
        )

        for item in zones["center"]:
            att = float(item["attention"])
            sat = float(item["satisfaction"])

            start_x = margin_x + (sat / 100.0) * work_w
            start_y = (h - margin_y) - (att / 100.0) * work_h

            current_x, current_y = start_x, start_y
            angle = 0
            radius = 0

            while True:
                test_box = (
                    current_x - item["box_w"] / 2,
                    current_y - item["box_h"] / 2,
                    current_x + item["box_w"] / 2,
                    current_y + item["box_h"] / 2
                )

                overlap = any(self._is_overlap(test_box, pb) for pb in placed_boxes)

                if not overlap:
                    placed_boxes.append(test_box)
                    item["draw_x"] = current_x
                    item["draw_y"] = current_y
                    break

                angle += 0.5
                radius += 2
                current_x = start_x + radius * math.cos(angle)
                current_y = start_y + radius * math.sin(angle)

        for zone_items in zones.values():
            for item in zone_items:
                self._draw_rectangle(
                    item["draw_x"], item["draw_y"], item["box_w"], item["box_h"],
                    item["color"], item["type"], item["id"],
                    item["attention"], item["satisfaction"], item["name"]
                )

    def _draw_rectangle(self, x, y, w, h, color, entity_type, entity_id, att, sat, name):
        tag = f"id_{entity_type}_{entity_id}"

        x1, y1 = x - w / 2, y - h / 2
        x2, y2 = x + w / 2, y + h / 2

        self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="black", tags=tag)

        if self.show_att:
            self.canvas.create_text(x, y1 + 2, text=f"{int(att)}",
                                    font=("Arial", 8), fill="#333", anchor="n", tags=tag)
        if self.show_sat:
            self.canvas.create_text(x2 - 2, y, text=f"{int(sat)}",
                                    font=("Arial", 8), fill="#333", anchor="e", tags=tag)

        display_name = f"{entity_id}.\u00A0{name}" if entity_type == "role" else name
        text_w = max(20, w - 6)
        self.canvas.create_text(x, y, text=display_name,
                                font=("Arial", 8, "bold"), fill="#111",
                                width=text_w, justify="center", anchor="center", tags=tag)

        self.drawn_items.append((x, y, w, h, entity_type, entity_id))

    # ------------------------------------------------------------
    # Двойной клик — окно «Метрика: {name}»
    # ------------------------------------------------------------
    def _on_double_click(self, event):
        for x, y, w, h, etype, eid in self.drawn_items:
            if abs(event.x - x) < w / 2 + 5 and abs(event.y - y) < h / 2 + 5:
                self._open_info_dialog(eid, etype, event.x_root, event.y_root)
                return

    def _format_fact(self, indicator: dict, actual_value_str: str) -> str:
        """Формат «Факт» (слитно значение + единица).

        - calc_duration и value >= 60 мин → «X ч., Y мин.» (или «X ч.» при Y=0).
        - calc_duration и value < 60 мин → «Y мин.».
        - иначе: значение + ' ' + unit (если unit задан).
        - пусто / None → «—».
        """
        if actual_value_str is None or str(actual_value_str).strip() == "":
            return "—"

        value_type = indicator.get("value_type", "")
        calc_method = indicator.get("calc_method", "")
        unit = indicator.get("unit") or ""

        if calc_method == "calc_duration" and value_type == "number":
            try:
                minutes = float(actual_value_str)
            except (ValueError, TypeError):
                return f"{actual_value_str} {unit}".strip()

            if minutes >= 60:
                h = int(minutes // 60)
                m = int(round(minutes % 60))
                if m >= 60:
                    h += 1
                    m = 0
                if m == 0:
                    return f"{h} ч."
                return f"{h} ч., {m} мин."
            else:
                return f"{int(round(minutes))} мин."

        if unit:
            return f"{actual_value_str} {unit}"
        return str(actual_value_str)

    def _open_info_dialog(self, entity_id, entity_type, mouse_x, mouse_y):
        current_data = next(
            (item for item in self.data
             if item["id"] == entity_id and item["type"] == entity_type),
            None
        )
        if not current_data:
            return

        metric_id = current_data.get("metric_id")

        dialog = tk.Toplevel(self)
        dialog.transient(self.winfo_toplevel())
        dialog.title(f"Метрика: {current_data['name']}")

        # Восстановление геометрии (или дефолт по центру)
        saved_geom = self.prefs_repo.get("chart_info_geometry")
        if isinstance(saved_geom, str) and saved_geom.strip():
            try:
                dialog.geometry(saved_geom)
            except tk.TclError:
                dialog.geometry("1200x700")
        else:
            dialog.update_idletasks()
            sw = dialog.winfo_screenwidth()
            sh = dialog.winfo_screenheight()
            w, h = 1200, 700
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            dialog.geometry(f"{w}x{h}+{x}+{y}")

        dialog.minsize(800, 550)
        dialog.grab_set()

        # ------- Шапка: роль, подроль, режим, период, satisfaction, attention -------
        frame_header = tk.Frame(dialog)
        frame_header.pack(fill="x", padx=15, pady=(15, 5))

        role_name = ""
        subrole_name = ""
        if entity_type == "sub_role":
            subrole_name = current_data["name"]
            if current_data.get("parent_id"):
                for r in self.roles_repo.get_all():
                    if r[0] == current_data["parent_id"]:
                        role_name = r[1]
                        break
        else:
            role_name = current_data["name"]

        info_lines = [
            ("Роль:", role_name or "—"),
            ("Подроль:", subrole_name or "—"),
            ("Режим:", self.current_mode),
            ("Период:", self.current_period_value or "—"),
            ("Satisfaction:", f"{current_data['satisfaction']:.1f}%"),
            ("Attention:", f"{current_data['attention']:.1f}%"),
        ]

        for label, value in info_lines:
            row = tk.Frame(frame_header)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=label, font=("Arial", 9, "bold"),
                     width=14, anchor="w").pack(side="left")
            tk.Label(row, text=value, anchor="w").pack(side="left", fill="x", expand=True)

        # ------- Данные: индикаторы по осям -------
        all_indicators = self.indicator_repo.get_all()
        metric_indicators = [ind for ind in all_indicators if ind["metric_id"] == metric_id] \
            if metric_id else []

        values = {}
        if self.current_period_id is not None:
            values = self.indicator_repo.get_values_for_period(self.current_period_id)

        types_map = {t[0]: t[1] for t in self.types_repo.get_all()}
        duties_map = {d[0]: d[1] for d in self.duties_repo.get_all()}
        questions_map = {q[0]: q[1] for q in self.questions_repo.get_all()}

        def _make_row(ind):
            actual_value = values.get(ind["id"], "")
            score = ScoreCalculator.calculate_score(ind, actual_value)

            weight = ind["weight"] if ind["weight"] is not None else 50

            # Разделяем источник на «Тип источника» и «Значение»
            if ind["activity_type_id"]:
                src_kind = "Активность"
                src_value = types_map.get(ind["activity_type_id"], "?")
            elif ind["regular_duty_id"]:
                src_kind = "Обязанность"
                src_value = duties_map.get(ind["regular_duty_id"], "?")
            elif ind.get("question_id"):
                src_kind = "Вопрос"
                src_value = questions_map.get(ind["question_id"], f"#{ind['question_id']}")
            else:
                src_kind = "?"
                src_value = "?"

            fact_str = self._format_fact(ind, actual_value)

            if ind["goal_type"] == "binary":
                target = "—"
            else:
                target = ind["target_value"] if ind["target_value"] else "—"

            goal_type = ind["goal_type"]
            method = ind["calc_method"]

            if ind["goal_type"] == "binary":
                step_pen = "—"
            else:
                step = ind["goal_step"] if ind["goal_step"] is not None else 0
                pen = ind["goal_penalty"] if ind["goal_penalty"] is not None else 0
                step_pen = f"{step:g} / {pen:g}%"

            return [
                ind["name"], src_kind, src_value, fact_str, target, goal_type,
                method, step_pen, weight, f"{score:.1f}",
            ], score, weight

        sat_inds = [i for i in metric_indicators if i.get("affects") == "satisfaction"]
        att_inds = [i for i in metric_indicators if i.get("affects") == "attention"]

        def _build_axis_block(parent, title, inds):
            block = tk.LabelFrame(parent, text=title, padx=5, pady=5)

            rows = []
            sum_score_weight = 0.0
            sum_weight = 0.0
            formula_parts = []

            for ind in inds:
                row, score, weight = _make_row(ind)
                rows.append(row)
                sum_score_weight += score * weight
                sum_weight += weight
                formula_parts.append(f"({score:.1f} × {weight})")

            sheet = Sheet(
                block,
                headers=["Имя", "Тип источника", "Значение", "Факт", "Цель",
                         "Тип цели", "Метод", "Шаг / Штраф", "Вес", "Score %"],
                show_row_index=False,
                show_top_left=False,
                show_x_scrollbar=True,
                show_y_scrollbar=True,
                table_grid_fg="#000000",
                outline_thickness=1,
                header_bg="#f0f0f0",
                header_fg="#000000",
                font=("Arial", 9, "normal"),
                header_font=("Arial", 9, "bold"),
                row_height=25,
                auto_resize_row_heights=True,
            )
            sheet.pack(fill="both", expand=True)
            sheet.enable_bindings("all")
            sheet.readonly_columns(columns=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
            sheet.set_sheet_data(rows, reset_col_positions=False)
            sheet.set_column_widths([130, 80, 150, 90, 60, 70, 100, 90, 45, 60])

            frame_formula = tk.Frame(block)
            frame_formula.pack(fill="x", pady=(5, 0))

            if sum_weight > 0:
                result = sum_score_weight / sum_weight
                formula_text = (
                    f"Σ(score × weight) / Σweight = "
                    f"{' + '.join(formula_parts)} / {sum_weight:g} = {result:.1f}%"
                )
            elif not inds:
                formula_text = "Нет индикаторов для этой оси"
            else:
                formula_text = "Σweight = 0 (все веса нулевые)"

            tk.Label(
                frame_formula, text=formula_text,
                font=("Consolas", 8), anchor="w", justify="left",
                wraplength=550,
            ).pack(fill="x")

            return block

        # ------- Две таблицы: Attention слева, Satisfaction справа -------
        frame_tables = tk.PanedWindow(dialog, orient="horizontal", sashwidth=6,
                                       sashrelief="raised")
        frame_tables.pack(fill="both", expand=True, padx=15, pady=(5, 5))

        left_block = _build_axis_block(frame_tables, "Attention (вложение усилий)", att_inds)
        right_block = _build_axis_block(frame_tables, "Satisfaction (удовлетворённость)", sat_inds)

        frame_tables.add(left_block, stretch="always")
        frame_tables.add(right_block, stretch="always")

        # ------- Кнопка Закрыть -------
        frame_btns = tk.Frame(dialog)
        frame_btns.pack(fill="x", pady=(0, 10))
        tk.Button(frame_btns, text="Закрыть",
                  command=lambda: self._close_info_dialog(dialog), width=15).pack()

        dialog.protocol("WM_DELETE_WINDOW", lambda: self._close_info_dialog(dialog))
        dialog.bind("<Escape>", lambda e: self._close_info_dialog(dialog))

    def _close_info_dialog(self, dialog):
        try:
            self.prefs_repo.set("chart_info_geometry", dialog.geometry())
        except Exception:
            pass
        dialog.destroy()

    # ------------------------------------------------------------
    # Фильтр ролей
    # ------------------------------------------------------------
    def open_filter_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.transient(self.winfo_toplevel())
        dialog.title("Фильтр ролей")

        root = self.winfo_toplevel()
        root.update_idletasks()
        rx = root.winfo_rootx()
        ry = root.winfo_rooty()
        rw = root.winfo_width()

        pos_x = rx + (rw - 500) // 2
        pos_y = ry + 50
        dialog.geometry(f"500x550+{pos_x}+{pos_y}")
        dialog.grab_set()

        tk.Label(dialog, text="Отображать роли (ID. Name):",
                 font=("Arial", 10, "bold")).pack(pady=5)

        frame_mass = tk.Frame(dialog)
        frame_mass.pack(fill="x", padx=20, pady=2)

        self.filter_vars = {}

        def select_all():
            for v in self.filter_vars.values():
                v.set(True)

        def clear_all():
            for v in self.filter_vars.values():
                v.set(False)

        tk.Button(frame_mass, text="Выбрать всё", command=select_all).pack(side="left")
        tk.Button(frame_mass, text="Очистить выбор", command=clear_all).pack(side="left", padx=5)

        roles = sorted(self.roles_repo.get_all(), key=lambda r: r[0])

        frame_roles = tk.Frame(dialog)
        frame_roles.pack(fill="x", padx=20, pady=2)

        for role in roles:
            role_id, name = role[0], role[1]
            display_name = f"{role_id}.\u00A0{name}"
            var = tk.BooleanVar(value=(role_id not in self.hidden_roles))
            chk = tk.Checkbutton(frame_roles, text=display_name, variable=var)
            chk.pack(anchor="w")
            self.filter_vars[role_id] = var

        tk.Label(dialog, text="Настройки текста:",
                 font=("Arial", 10, "bold")).pack(pady=(10, 5))

        self.show_att_var = tk.BooleanVar(value=self.show_att)
        tk.Checkbutton(dialog, text="Показывать attention сверху",
                       variable=self.show_att_var).pack(anchor="w", padx=20)

        self.show_sat_var = tk.BooleanVar(value=self.show_sat)
        tk.Checkbutton(dialog, text="Показывать satisfaction справа",
                       variable=self.show_sat_var).pack(anchor="w", padx=20)

        def apply_filter():
            self.hidden_roles.clear()
            for role_id, var in self.filter_vars.items():
                if not var.get():
                    self.hidden_roles.add(role_id)
            self.show_att = self.show_att_var.get()
            self.show_sat = self.show_sat_var.get()
            self._save_filter_state()
            dialog.destroy()
            self._draw_canvas()

        tk.Button(dialog, text="Применить", command=apply_filter).pack(pady=15)