# src/chart_tab.py
# Вкладка с визуализацией метрик (график с прямоугольниками).
#
# Настройки фильтра (скрытые роли, показ attention/satisfaction) общие
# с «График по периодам» (chart_metrics_tab.py) — хранятся в prefs под ключами
# chart_hidden_roles / chart_show_att / chart_show_sat.

import math
import tkinter as tk
from tkinter import messagebox
from .chart_repo import ChartRepository
from .roles_repo import RolesRepository
from .preferences_repo import PreferencesRepository


class ChartTab(tk.Frame):
    # Вкладка для визуализации метрик ролей.
    def __init__(self, parent, metrics_repo: ChartRepository, roles_repo: RolesRepository,
                 prefs_repo: PreferencesRepository):
        super().__init__(parent)
        self.metrics_repo = metrics_repo
        self.roles_repo = roles_repo
        self.prefs_repo = prefs_repo
        self.data = []
        self.hidden_roles = set()

        self.show_att = True
        self.show_sat = True

        # --- Панель кнопок ---
        frame_top = tk.Frame(self)
        frame_top.pack(fill="x", padx=10, pady=5)

        self.btn_refresh = tk.Button(frame_top, text="Обновить", command=self.refresh_data)
        self.btn_refresh.pack(side="left", padx=5)

        self.btn_filter = tk.Button(frame_top, text="Фильтр", command=self.open_filter_dialog)
        self.btn_filter.pack(side="left", padx=5)

        self.btn_reset = tk.Button(frame_top, text="Сбросить прогресс", command=self.reset_progress, fg="red")
        self.btn_reset.pack(side="left", padx=5)

        lbl_hint = tk.Label(frame_top, text="(Двойной клик по фигуре для изменения параметров)", fg="gray")
        lbl_hint.pack(side="right", padx=5)

        # --- Canvas для рисования ---
        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)

        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)

        self.drawn_items = []

        self._load_state()
        self.refresh_data()

    # ------------------------------------------------------------------
    # Состояние фильтра (общее с chart_metrics_tab)
    # ------------------------------------------------------------------
    def _load_state(self):
        hidden = self.prefs_repo.get("chart_hidden_roles")
        if isinstance(hidden, list):
            self.hidden_roles = set(int(x) for x in hidden if x is not None)
        else:
            self.hidden_roles = set()

        show_att = self.prefs_repo.get("chart_show_att")
        self.show_att = True if show_att is None else bool(show_att)
        show_sat = self.prefs_repo.get("chart_show_sat")
        self.show_sat = True if show_sat is None else bool(show_sat)

    def _save_filter_state(self):
        self.prefs_repo.set("chart_hidden_roles", sorted(self.hidden_roles))
        self.prefs_repo.set("chart_show_att", self.show_att)
        self.prefs_repo.set("chart_show_sat", self.show_sat)

    # ------------------------------------------------------------------
    # Данные и отрисовка
    # ------------------------------------------------------------------
    def refresh_data(self):
        self.data = self.metrics_repo.get_all_metrics()
        self._draw_canvas()

    def reset_progress(self):
        if messagebox.askyesno("Сброс", "Вы уверены, что хотите сбросить ВСЕ метрики в ноль?"):
            self.metrics_repo.reset_metrics()
            self.refresh_data()

    def _on_resize(self, event):
        self._draw_canvas()

    def _is_overlap(self, box1, box2):
        return not (box1[2] <= box2[0] or box1[0] >= box2[2] or box1[3] <= box2[1] or box1[1] >= box2[3])

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
        """Каскадное размещение метрик в краевой зоне (bottom/top/left/right).

        Идеальная позиция — та же формула, что и для center:
            ideal_x = margin_x + (sat/100) * work_w
            ideal_y = (h - margin_y) - (att/100) * work_h
        Для краевой зоны одна из координат уже «прижата» к границе
        (att=0 → ideal_y = h - margin_y; att=100 → margin_y;
         sat=0 → ideal_x = margin_x;   sat=100 → w - margin_x).

        Каскад при коллизии:
          1) первый слот — на границе (row0);
          2) второй слот — перпендикулярно границе внутрь полотна (row1);
          3) если оба заняты — поиск ближайшего свободного места
             вдоль границы: расстояния 1,2,3…, знаки +,- (сначала вправо,
             потом влево), на каждом шаге проверяются оба слота (row0, row1).
        """
        if not items:
            return

        gap = 4  # зазор между прямоугольниками

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

        # --- Рисуем сетку ---
        self.canvas.create_rectangle(margin_x, margin_y, w - margin_x, h - margin_y, outline="#aaaaaa", dash=(4, 4))
        self.canvas.create_line(margin_x, 0, margin_x, h, fill="#aaaaaa", dash=(4, 4))
        self.canvas.create_line(w - margin_x, 0, w - margin_x, h, fill="#aaaaaa", dash=(4, 4))
        self.canvas.create_line(0, margin_y, w, margin_y, fill="#aaaaaa", dash=(4, 4))
        self.canvas.create_line(0, h - margin_y, w, h - margin_y, fill="#aaaaaa", dash=(4, 4))

        self.canvas.create_text(margin_x - 5, h - margin_y + 5, text="0,0", anchor="ne", fill="#888888")
        self.canvas.create_text(w - margin_x + 5, margin_y - 5, text="100,100", anchor="sw", fill="#888888")

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

                overlap = False
                for pb in placed_boxes:
                    if self._is_overlap(test_box, pb):
                        overlap = True
                        break

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
                self._draw_rectangle(item["draw_x"], item["draw_y"], item["color"], item["type"], item["id"],
                                     item["attention"], item["satisfaction"], item["name"])

    def _draw_rectangle(self, x, y, color, entity_type, entity_id, att, sat, name):
        tag = f"id_{entity_id}"

        item = next((i for i in self.data if i["id"] == entity_id and i["type"] == entity_type), None)
        w = item["box_w"]
        h = item["box_h"]

        x1, y1 = x - w / 2, y - h / 2
        x2, y2 = x + w / 2, y + h / 2

        self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="black", tags=tag)

        if self.show_att:
            self.canvas.create_text(x, y1 + 2, text=f"{int(att)}", font=("Arial", 8), fill="#333", anchor="n", tags=tag)

        if self.show_sat:
            self.canvas.create_text(x2 - 2, y, text=f"{int(sat)}", font=("Arial", 8), fill="#333", anchor="e", tags=tag)

        display_name = f"{entity_id}.\u00A0{name}" if entity_type == "role" else name

        text_w = w - 6
        self.canvas.create_text(x, y, text=display_name, font=("Arial", 8, "bold"), fill="#111", width=text_w,
                                justify="center", anchor="center", tags=tag)

        self.drawn_items.append((x, y, entity_type, entity_id, w, h))

    def _on_double_click(self, event):
        closest_item = None
        min_dist = 60

        for item in self.drawn_items:
            x, y, etype, eid, w, h = item
            if abs(event.x - x) < w / 2 + 5 and abs(event.y - y) < h / 2 + 5:
                closest_item = item
                break

        if closest_item:
            self._open_edit_dialog(closest_item[3], closest_item[2], event.x_root, event.y_root)

    def _open_edit_dialog(self, entity_id, entity_type, mouse_x, mouse_y):
        current_data = next((item for item in self.data if item["id"] == entity_id and item["type"] == entity_type),
                            None)
        if not current_data:
            return

        dialog = tk.Toplevel(self)
        dialog.transient(self.winfo_toplevel())
        dialog.title(f"Настройка: {current_data['name']}")

        pos_x = int(mouse_x - 150)
        pos_y = int(mouse_y - 300)
        dialog.geometry(f"300x280+{max(0, pos_x)}+{max(0, pos_y)}")
        dialog.grab_set()

        tk.Label(dialog, text=current_data["name"], font=("Arial", 12, "bold"), wraplength=280).pack(pady=10)

        frame_att = tk.Frame(dialog)
        frame_att.pack(fill="x", padx=20, pady=5)
        tk.Label(frame_att, text="Внимание:").pack(side="left")
        var_att = tk.IntVar(value=int(current_data["attention"]))
        entry_att = tk.Entry(frame_att, width=5, textvariable=var_att)
        entry_att.pack(side="right")

        def on_att_scale(val):
            var_att.set(int(val))

        scale_att = tk.Scale(dialog, from_=0, to=100, orient="horizontal", variable=var_att, command=on_att_scale,
                             showvalue=0)
        scale_att.pack(fill="x", padx=20)

        frame_sat = tk.Frame(dialog)
        frame_sat.pack(fill="x", padx=20, pady=5)
        tk.Label(frame_sat, text="Довольство:").pack(side="left")
        var_sat = tk.IntVar(value=int(current_data["satisfaction"]))
        entry_sat = tk.Entry(frame_sat, width=5, textvariable=var_sat)
        entry_sat.pack(side="right")

        def on_sat_scale(val):
            var_sat.set(int(val))

        scale_sat = tk.Scale(dialog, from_=0, to=100, orient="horizontal", variable=var_sat, command=on_sat_scale,
                             showvalue=0)
        scale_sat.pack(fill="x", padx=20)

        def validate_input(entry_widget, var, scale_widget):
            try:
                val = int(entry_widget.get())
                if 0 <= val <= 100:
                    var.set(val)
                    scale_widget.set(val)
                else:
                    raise ValueError
            except ValueError:
                entry_widget.delete(0, tk.END)
                entry_widget.insert(0, var.get())

        entry_att.bind("<Return>", lambda e: validate_input(entry_att, var_att, scale_att))
        entry_att.bind("<FocusOut>", lambda e: validate_input(entry_att, var_att, scale_att))
        entry_sat.bind("<Return>", lambda e: validate_input(entry_sat, var_sat, scale_sat))
        entry_sat.bind("<FocusOut>", lambda e: validate_input(entry_sat, var_sat, scale_sat))

        def save():
            self.metrics_repo.update_metric(entity_id, entity_type, float(var_att.get()), float(var_sat.get()))
            dialog.destroy()
            self.refresh_data()

        tk.Button(dialog, text="Сохранить", command=save).pack(pady=15)

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

        tk.Label(dialog, text="Отображать роли (ID. Name):", font=("Arial", 10, "bold")).pack(pady=5)

        # Кнопки массового выбора
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

        tk.Label(dialog, text="Настройки текста:", font=("Arial", 10, "bold")).pack(pady=(10, 5))

        self.show_att_var = tk.BooleanVar(value=self.show_att)
        tk.Checkbutton(dialog, text="Показывать внимание сверху", variable=self.show_att_var).pack(anchor="w", padx=20)

        self.show_sat_var = tk.BooleanVar(value=self.show_sat)
        tk.Checkbutton(dialog, text="Показывать довольство справа", variable=self.show_sat_var).pack(anchor="w",
                                                                                                     padx=20)

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