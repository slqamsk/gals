# src/indicator_config_tab.py
# Вкладка для настройки индикаторов (правил расчета).
#
# Индикатор опирается РОВНО на одно из трёх:
#   - тип активности (calc_duration / calc_start_time / calc_count)
#   - регулярная обязанность (calc_duty_done / calc_duty_mark)
#   - вопрос (calc_question_last)
#
# Обязательное поле "Влияет на" (affects): 'satisfaction' | 'attention'.
#
# Два layout'а (переключатель в верхней панели):
#   - v_split: дерево | [таблица (сверху) / форма (снизу)]
#   - h_split: дерево | таблица | форма (все три слева-направо)
#
# Все разделители — PanedWindow с sashwidth=8, перетаскиваются.
# Позиции сохраняются в prefs.

import tkinter as tk
from tkinter import ttk, messagebox
from tksheet import Sheet

from .metrics_repo import MetricsRepository
from .activity_types_repo import ActivityTypesRepository
from .regular_duties_repo import RegularDutiesRepository
from .indicator_repo import IndicatorRepository
from .questions_repo import QuestionsRepository
from .roles_repo import RolesRepository
from .sub_roles_repo import SubRolesRepository
from .preferences_repo import PreferencesRepository
from .constants import GoalType, ValueType, CalcMethod, AffectAxis


class IndicatorConfigTab(tk.Frame):
    def __init__(self, parent, indicator_repo: IndicatorRepository,
                 metrics_repo: MetricsRepository,
                 types_repo: ActivityTypesRepository,
                 duties_repo: RegularDutiesRepository,
                 roles_repo: RolesRepository,
                 sub_roles_repo: SubRolesRepository,
                 prefs_repo: PreferencesRepository):
        super().__init__(parent)
        self.indicator_repo = indicator_repo
        self.metrics_repo = metrics_repo
        self.types_repo = types_repo
        self.duties_repo = duties_repo
        self.roles_repo = roles_repo
        self.sub_roles_repo = sub_roles_repo
        self.prefs_repo = prefs_repo
        self.questions_repo = QuestionsRepository(indicator_repo.db)

        self.current_indicator_id = None
        self.current_role_id = None
        self.current_sub_role_id = None

        self.all_metrics = []
        self.roles_dict = {}
        self.sub_roles_dict = {}
        self.metrics_map = {}
        self.types_map = {}
        self.types_id_to_name = {}
        self.duties_map = {}
        self.duties_id_to_name = {}
        self.all_duties_info = {}
        self.questions_map = {}
        self.questions_id_to_name = {}

        # State variables
        saved_aff = prefs_repo.get("indicator_config_affects_filter") or "all"
        if saved_aff not in ("all", "satisfaction", "attention"):
            saved_aff = "all"
        self.var_affects_filter = tk.StringVar(value=saved_aff)

        saved_mt = prefs_repo.get("indicator_config_metric_type_filter") or "all"
        if saved_mt not in ("all", "day", "week", "month"):
            saved_mt = "all"
        self.var_metric_type_filter = tk.StringVar(value=saved_mt)

        saved_layout = prefs_repo.get("indicator_config_layout") or "v_split"
        if saved_layout not in ("v_split", "h_split"):
            saved_layout = "v_split"
        self.var_layout = tk.StringVar(value=saved_layout)

        self.paned = None
        self.vpaned = None

        self._build_ui()
        self.refresh_data()

    # ------------------------------------------------------------------
    # Верхняя панель + переключение layout
    # ------------------------------------------------------------------
    def _build_ui(self):
        topbar = tk.Frame(self)
        topbar.pack(fill="x", padx=10, pady=(10, 0))
        tk.Label(topbar, text="Расположение:",
                 font=("Arial", 10, "bold")).pack(side="left")
        tk.Radiobutton(topbar, text="Слева-справа (3 панели)",
                       variable=self.var_layout, value="h_split",
                       command=self._on_layout_changed).pack(side="left", padx=5)
        tk.Radiobutton(topbar, text="Сверху-снизу (текущее)",
                       variable=self.var_layout, value="v_split",
                       command=self._on_layout_changed).pack(side="left", padx=5)

        self._apply_layout()

    def _on_layout_changed(self):
        saved_id = self.current_indicator_id
        self._apply_layout()
        self.refresh_data()
        if saved_id is not None:
            indicators = self.indicator_repo.get_all()
            if any(i['id'] == saved_id for i in indicators):
                self._load_indicator_into_form(saved_id)

    def _apply_layout(self):
        self.prefs_repo.set("indicator_config_layout", self.var_layout.get())

        try:
            self.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass

        if self.paned is not None:
            try:
                self.paned.destroy()
            except tk.TclError:
                pass

        self.paned = tk.PanedWindow(self, orient="horizontal",
                                    sashwidth=8, sashrelief="raised")
        self.paned.pack(fill="both", expand=True, padx=10, pady=10)

        layout = self.var_layout.get()

        if layout == "h_split":
            self.paned.add(self._build_tree_pane(), stretch="never", width=280)
            self.paned.add(self._build_list_pane(), stretch="always", width=500)
            self.paned.add(self._build_form_pane(), stretch="always", width=400)
            self.paned.bind("<ButtonRelease-1>", self._save_sash_3p)
            self.after(50, self._restore_sash_3p)
        else:
            self.paned.add(self._build_tree_pane(), stretch="never", width=280)
            right = tk.Frame(self.paned)
            self.paned.add(right, stretch="always")
            self.vpaned = tk.PanedWindow(right, orient="vertical",
                                         sashwidth=8, sashrelief="raised")
            self.vpaned.pack(fill="both", expand=True)
            self.vpaned.add(self._build_list_pane(), stretch="always", height=350)
            self.vpaned.add(self._build_form_pane(), stretch="always", height=400)
            self.paned.bind("<ButtonRelease-1>", self._save_sash_h)
            self.vpaned.bind("<ButtonRelease-1>", self._save_sash_v)
            self.after(50, self._restore_sash_h)
            self.after(50, self._restore_sash_v)

    # ------------------------------------------------------------------
    # Sash save/restore
    # ------------------------------------------------------------------
    def _save_sash_h(self, event=None):
        try:
            x, _ = self.paned.sash_coord(0)
            self.prefs_repo.set("indicator_config_sash_h", x)
        except Exception:
            pass

    def _restore_sash_h(self):
        pos = self.prefs_repo.get("indicator_config_sash_h")
        if isinstance(pos, int) and self.paned is not None:
            try:
                self.paned.sash_place(0, pos, 0)
            except tk.TclError:
                pass

    def _save_sash_v(self, event=None):
        try:
            _, y = self.vpaned.sash_coord(0)
            self.prefs_repo.set("indicator_config_sash_v", y)
        except Exception:
            pass

    def _restore_sash_v(self):
        pos = self.prefs_repo.get("indicator_config_sash_v")
        if isinstance(pos, int) and self.vpaned is not None:
            try:
                self.vpaned.sash_place(0, 0, pos)
            except tk.TclError:
                pass

    def _save_sash_3p(self, event=None):
        try:
            p = []
            for i in range(2):
                x, _ = self.paned.sash_coord(i)
                p.append(x)
            self.prefs_repo.set("indicator_config_sash_3p", p)
        except Exception:
            pass

    def _restore_sash_3p(self):
        p = self.prefs_repo.get("indicator_config_sash_3p")
        if not isinstance(p, list) or len(p) != 2:
            p = [280, 780]
        if self.paned is not None:
            try:
                self.paned.sash_place(0, int(p[0]), 0)
                self.paned.sash_place(1, int(p[1]), 0)
            except (tk.TclError, ValueError):
                pass

    # ------------------------------------------------------------------
    # Дерево ролей
    # ------------------------------------------------------------------
    def _build_tree_pane(self):
        frame = tk.Frame(self.paned)

        frame_header = tk.Frame(frame)
        frame_header.pack(fill="x")
        tk.Label(frame_header, text="Роли / Под-роли:",
                 font=("Arial", 10, "bold")).pack(side="left")
        tk.Button(frame_header, text="Развернуть", font=("Arial", 8),
                  command=self._expand_all_roles).pack(side="right", padx=2)
        tk.Button(frame_header, text="Свернуть", font=("Arial", 8),
                  command=self._collapse_all_roles).pack(side="right", padx=2)

        self.tree_roles = ttk.Treeview(frame, show="tree", selectmode="browse")
        self.tree_roles.column("#0", width=250, minwidth=180)
        self.tree_roles.pack(fill="both", expand=True, pady=2)
        self.tree_roles.bind("<<TreeviewSelect>>", self._on_role_select)
        self.tree_roles.bind("<<TreeviewOpen>>", self._on_node_toggled)
        self.tree_roles.bind("<<TreeviewClose>>", self._on_node_toggled)

        self.tree_roles.tag_configure("role_node", font=("Arial", 11, "bold"))
        self.tree_roles.tag_configure("sub_role_node", font=("Arial", 10, "normal"))

        return frame

    def _get_tree_state(self) -> dict:
        state = self.prefs_repo.get("roles_tree_state")
        if not isinstance(state, dict):
            state = {}
        return state

    def _save_tree_state(self, state: dict):
        self.prefs_repo.set("roles_tree_state", state)

    def _on_node_toggled(self, event=None):
        state = self._get_tree_state()
        for role in self.roles_repo.get_all():
            role_id = role[0]
            iid = f"role_{role_id}"
            if self.tree_roles.exists(iid):
                state[str(role_id)] = bool(self.tree_roles.item(iid, "open"))
        self._save_tree_state(state)

    def _expand_all_roles(self):
        roles = self.roles_repo.get_all()
        state = {str(r[0]): True for r in roles}
        self._save_tree_state(state)
        if self.tree_roles.exists("root"):
            self.tree_roles.item("root", open=True)
        for item in self.tree_roles.get_children("root"):
            if item.startswith("role_"):
                self.tree_roles.item(item, open=True)

    def _collapse_all_roles(self):
        """P-01: корень остаётся развёрнутым, роли — свёрнуты (подроли скрыты)."""
        roles = self.roles_repo.get_all()
        state = {str(r[0]): False for r in roles}
        self._save_tree_state(state)
        if self.tree_roles.exists("root"):
            self.tree_roles.item("root", open=True)
        for item in self.tree_roles.get_children("root"):
            if item.startswith("role_"):
                self.tree_roles.item(item, open=False)

    def _load_tree(self):
        for item in self.tree_roles.get_children():
            self.tree_roles.delete(item)

        state = self._get_tree_state()

        self.tree_roles.insert("", "end", iid="root", text="📁 Все роли", open=True)

        for r in sorted(self.roles_repo.get_all(), key=lambda x: x[0]):
            rid, name = r[0], r[1]
            is_open = state.get(str(rid), True)
            self.tree_roles.insert("root", "end", iid=f"role_{rid}",
                                   text=f"{rid}. {name}", open=is_open,
                                   tags=("role_node",))
            for sr in sorted(self.sub_roles_repo.get_by_parent(rid), key=lambda x: x[0]):
                self.tree_roles.insert(f"role_{rid}", "end",
                                       iid=f"sub_{sr[0]}", text=sr[1],
                                       tags=("sub_role_node",))

        if self.current_sub_role_id is not None:
            iid = f"sub_{self.current_sub_role_id}"
            if self.tree_roles.exists(iid):
                self.tree_roles.selection_set(iid)
                self.tree_roles.focus(iid)
                return
        if self.current_role_id is not None:
            iid = f"role_{self.current_role_id}"
            if self.tree_roles.exists(iid):
                self.tree_roles.selection_set(iid)
                self.tree_roles.focus(iid)
                return
        if self.tree_roles.exists("root"):
            self.tree_roles.selection_set("root")
            self.tree_roles.focus("root")

    def _on_role_select(self, event=None):
        sel = self.tree_roles.selection()
        if not sel:
            self.current_role_id = None
            self.current_sub_role_id = None
        else:
            iid = sel[0]
            if iid == "root":
                self.current_role_id = None
                self.current_sub_role_id = None
            elif iid.startswith("role_"):
                self.current_role_id = int(iid.replace("role_", ""))
                self.current_sub_role_id = None
            else:
                self.current_sub_role_id = int(iid.replace("sub_", ""))
                self.current_role_id = None

        self._load_indicators()
        self._update_metric_values()

    # ------------------------------------------------------------------
    # Панель списка индикаторов
    # ------------------------------------------------------------------
    def _build_list_pane(self):
        frame = tk.Frame(self.paned)

        filter_frame = tk.Frame(frame)
        filter_frame.pack(fill="x", pady=3, padx=3)

        # Фильтр "Влияет на"
        tk.Label(filter_frame, text="Влияет на:",
                 font=("Arial", 9, "bold")).pack(side="left")
        for value, label in (("all", "Все"), ("satisfaction", "Sat"), ("attention", "Att")):
            tk.Radiobutton(filter_frame, text=label, value=value,
                           variable=self.var_affects_filter,
                           command=self._on_filter_changed).pack(side="left", padx=2)

        tk.Label(filter_frame, text=" | ").pack(side="left")

        # Фильтр "Период"
        tk.Label(filter_frame, text="Период:",
                 font=("Arial", 9, "bold")).pack(side="left")
        for value, label in (("all", "Все"), ("day", "День"),
                             ("week", "Нед"), ("month", "Мес")):
            tk.Radiobutton(filter_frame, text=label, value=value,
                           variable=self.var_metric_type_filter,
                           command=self._on_filter_changed).pack(side="left", padx=2)

        # Кнопки
        tk.Button(filter_frame, text="Обновить",
                  command=self.refresh_data).pack(side="right", padx=2)
        tk.Button(filter_frame, text="Удалить", command=self.on_delete,
                  fg="red").pack(side="right", padx=2)
        tk.Button(filter_frame, text="Добавить новый",
                  command=self.on_add).pack(side="right", padx=2)

        self.sheet_indicators = Sheet(
            frame,
            headers=["ID", "Название", "Метрика", "Влияет на", "Источник"],
            show_row_index=False, show_top_left=False,
            show_x_scrollbar=True, show_y_scrollbar=True,
            table_grid_fg="#000000", outline_thickness=1,
            header_bg="#f0f0f0", header_fg="#000000",
            font=("Arial", 9, "normal"), header_font=("Arial", 9, "bold"),
            row_height=25, auto_resize_row_heights=True,
        )
        self.sheet_indicators.pack(fill="both", expand=True, padx=3, pady=(0, 3))
        self.sheet_indicators.enable_bindings("all")
        self.sheet_indicators.readonly_columns(columns=[0, 1, 2, 3, 4])
        self.sheet_indicators.extra_bindings("cell_select", self._on_indicator_row_selected)
        self.sheet_indicators.set_column_widths([50, 220, 250, 110, 200])

        return frame

    # ------------------------------------------------------------------
    # Панель формы
    # ------------------------------------------------------------------
    def _build_form_pane(self):
        frame = tk.Frame(self.paned)

        container = tk.Frame(frame)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, highlightthickness=0)
        sb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)

        form_frame = tk.Frame(canvas)
        canvas.create_window((0, 0), window=form_frame, anchor="nw")
        form_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(1, width=e.width))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        tk.Label(form_frame, text="Настройка индикатора",
                 font=("Arial", 12, "bold")).pack(pady=10)

        frm = tk.Frame(form_frame)
        frm.pack(padx=20, pady=5, fill="x")

        # 0. Метрика
        tk.Label(frm, text="Метрика:").grid(row=0, column=0, sticky="e", pady=2)
        self.cb_metric = ttk.Combobox(frm, state="readonly", width=40)
        self.cb_metric.grid(row=0, column=1, sticky="w", pady=2)
        self.cb_metric.bind("<<ComboboxSelected>>", self._on_metric_changed)

        # 1. Источники
        tk.Label(frm, text="Тип активности:").grid(row=1, column=0, sticky="e", pady=2)
        self.cb_type = ttk.Combobox(frm, state="readonly", width=40)
        self.cb_type.grid(row=1, column=1, sticky="w", pady=2)
        self.cb_type.bind("<<ComboboxSelected>>", self._on_type_selected)

        tk.Label(frm, text="Обязанность:").grid(row=2, column=0, sticky="e", pady=2)
        self.cb_duty = ttk.Combobox(frm, state="readonly", width=40)
        self.cb_duty.grid(row=2, column=1, sticky="w", pady=2)
        self.cb_duty.bind("<<ComboboxSelected>>", self._on_duty_selected)

        tk.Label(frm, text="Вопрос:").grid(row=3, column=0, sticky="e", pady=2)
        self.cb_question = ttk.Combobox(frm, state="readonly", width=40)
        self.cb_question.grid(row=3, column=1, sticky="w", pady=2)
        self.cb_question.bind("<<ComboboxSelected>>", self._on_question_selected)

        tk.Label(frm, text="(выберите ровно одно: тип, обязанность или вопрос)",
                 fg="gray", font=("Arial", 8, "italic")).grid(
            row=3, column=2, sticky="w", padx=5
        )

        # 4. Ось
        tk.Label(frm, text="Влияет на:").grid(row=4, column=0, sticky="e", pady=2)
        self.cb_affects = ttk.Combobox(frm, state="readonly", width=40)
        self.cb_affects['values'] = [e.value for e in AffectAxis]
        self.cb_affects.grid(row=4, column=1, sticky="w", pady=2)

        # 5. Основные данные
        tk.Label(frm, text="Название:").grid(row=5, column=0, sticky="e", pady=2)
        self.ent_name = tk.Entry(frm, width=42)
        self.ent_name.grid(row=5, column=1, sticky="w", pady=2)

        tk.Label(frm, text="Описание:").grid(row=6, column=0, sticky="e", pady=2)
        self.ent_desc = tk.Entry(frm, width=42)
        self.ent_desc.grid(row=6, column=1, sticky="w", pady=2)

        tk.Label(frm, text="Единица (unit):").grid(row=7, column=0, sticky="e", pady=2)
        self.ent_unit = tk.Entry(frm, width=42)
        self.ent_unit.grid(row=7, column=1, sticky="w", pady=2)

        # 6. Типы
        tk.Label(frm, text="Тип значения:").grid(row=8, column=0, sticky="e", pady=2)
        self.cb_value_type = ttk.Combobox(frm, state="readonly", width=40)
        self.cb_value_type['values'] = [e.value for e in ValueType]
        self.cb_value_type.grid(row=8, column=1, sticky="w", pady=2)

        tk.Label(frm, text="Тип цели:").grid(row=9, column=0, sticky="e", pady=2)
        self.cb_goal_type = ttk.Combobox(frm, state="readonly", width=40)
        self.cb_goal_type['values'] = [e.value for e in GoalType]
        self.cb_goal_type.grid(row=9, column=1, sticky="w", pady=2)

        tk.Label(frm, text="Метод расчета:").grid(row=10, column=0, sticky="e", pady=2)
        self.cb_calc_method = ttk.Combobox(frm, state="readonly", width=40)
        self.cb_calc_method.grid(row=10, column=1, sticky="w", pady=2)

        # 7. Цели
        tk.Label(frm, text="Цель (Target):").grid(row=11, column=0, sticky="e", pady=2)
        self.ent_target = tk.Entry(frm, width=42)
        self.ent_target.grid(row=11, column=1, sticky="w", pady=2)

        tk.Label(frm, text="Шаг (Step):").grid(row=12, column=0, sticky="e", pady=2)
        self.ent_step = tk.Entry(frm, width=42)
        self.ent_step.grid(row=12, column=1, sticky="w", pady=2)

        tk.Label(frm, text="Штраф за шаг (%):").grid(row=13, column=0, sticky="e", pady=2)
        self.ent_penalty = tk.Entry(frm, width=42)
        self.ent_penalty.grid(row=13, column=1, sticky="w", pady=2)

        tk.Label(frm, text="Вес (0-100):").grid(row=14, column=0, sticky="e", pady=2)
        self.ent_weight = tk.Entry(frm, width=42)
        self.ent_weight.grid(row=14, column=1, sticky="w", pady=2)

        frame_btns = tk.Frame(form_frame)
        frame_btns.pack(pady=15)

        tk.Button(frame_btns, text="Добавить новый",
                  command=self.on_add).pack(side="left", padx=5)
        tk.Button(frame_btns, text="Сохранить",
                  command=self.on_save, fg="green").pack(side="left", padx=5)
        tk.Button(frame_btns, text="Удалить",
                  command=self.on_delete, fg="red").pack(side="left", padx=5)

        return frame

    # ------------------------------------------------------------------
    # Загрузка данных
    # ------------------------------------------------------------------
    def refresh_data(self):
        # 1. Справочники
        types = self.types_repo.get_all()
        self.types_map = {t[1]: t[0] for t in types}
        self.types_id_to_name = {t[0]: t[1] for t in types}
        self.cb_type['values'] = list(self.types_map.keys())

        duties = self.duties_repo.get_all()
        self.duties_map = {d[1]: d[0] for d in duties}
        self.duties_id_to_name = {d[0]: d[1] for d in duties}
        self.all_duties_info = {d[1]: {"id": d[0], "period_type": d[6]} for d in duties}

        questions = self.questions_repo.get_all()
        self.questions_map = {f"#{q[0]}: {q[1]}": q[0] for q in questions}
        self.questions_id_to_name = {q[0]: q[1] for q in questions}
        self.cb_question['values'] = list(self.questions_map.keys())

        # 2. Метрики + роли
        self.all_metrics = self.metrics_repo.get_all_metrics()
        self.roles_dict = {r[0]: r[1] for r in self.roles_repo.get_all()}
        self.sub_roles_dict = {}
        for r_id in self.roles_dict:
            for sr in self.sub_roles_repo.get_by_parent(r_id):
                self.sub_roles_dict[sr[0]] = sr[1]

        # 3. Дерево
        self._load_tree()

        # 4. Список индикаторов
        self._load_indicators()

        # 5. Combobox метрик
        self._update_metric_values()

        # 6. Обновление duty-вариантов
        self._update_duty_values()

    def _metric_display(self, metric_id: int) -> str:
        for m in self.all_metrics:
            if m['id'] == metric_id:
                if m['role_id']:
                    name = f"Роль: {self.roles_dict.get(m['role_id'], '?')}"
                else:
                    name = f"Подроль: {self.sub_roles_dict.get(m['sub_role_id'], '?')}"
                return f"{name} ({m['type']})"
        return "?"

    def _source_display(self, ind: dict) -> str:
        if ind.get('activity_type_id'):
            return f"Тип: {self.types_id_to_name.get(ind['activity_type_id'], '?')}"
        if ind.get('regular_duty_id'):
            return f"Обязанность: {self.duties_id_to_name.get(ind['regular_duty_id'], '?')}"
        if ind.get('question_id'):
            return f"Вопрос: #{ind['question_id']} {self.questions_id_to_name.get(ind['question_id'], '?')}"
        return "?"

    def _get_allowed_metric_ids(self) -> set[int]:
        if self.current_sub_role_id is not None:
            return {m['id'] for m in self.all_metrics
                    if m['sub_role_id'] == self.current_sub_role_id}
        if self.current_role_id is not None:
            sub_ids = {sr[0] for sr in self.sub_roles_repo.get_by_parent(self.current_role_id)}
            return {m['id'] for m in self.all_metrics
                    if m['role_id'] == self.current_role_id
                    or m['sub_role_id'] in sub_ids}
        return {m['id'] for m in self.all_metrics}

    def _load_indicators(self):
        allowed = self._get_allowed_metric_ids()
        affects_filter = self.var_affects_filter.get()
        mt_filter = self.var_metric_type_filter.get()
        metric_type_by_id = {m['id']: m['type'] for m in self.all_metrics}

        indicators = self.indicator_repo.get_all()
        rows = []
        for ind in indicators:
            if ind['metric_id'] not in allowed:
                continue
            if affects_filter != "all" and ind.get('affects') != affects_filter:
                continue
            if mt_filter != "all":
                if metric_type_by_id.get(ind['metric_id']) != mt_filter:
                    continue
            rows.append([
                ind['id'],
                ind['name'],
                self._metric_display(ind['metric_id']),
                ind.get('affects') or "?",
                self._source_display(ind),
            ])
        self.sheet_indicators.set_sheet_data(rows, reset_col_positions=False)

    def _update_metric_values(self):
        allowed = self._get_allowed_metric_ids()
        self.metrics_map = {}
        for m_id in allowed:
            display = self._metric_display(m_id)
            self.metrics_map[display] = m_id
        self.cb_metric['values'] = list(self.metrics_map.keys())
        if self.cb_metric.get() and self.cb_metric.get() not in self.metrics_map:
            self.cb_metric.set("")

    def _update_duty_values(self):
        metric_display = self.cb_metric.get()
        metric_id = self.metrics_map.get(metric_display) if metric_display else None
        if metric_id is None:
            self.cb_duty['values'] = list(self.duties_map.keys())
            return
        metric = next((m for m in self.all_metrics if m['id'] == metric_id), None)
        if metric is None:
            self.cb_duty['values'] = list(self.duties_map.keys())
            return
        mtype = metric['type']
        relevant = [name for name, info in self.all_duties_info.items()
                    if info["period_type"] == mtype]
        self.cb_duty['values'] = relevant
        if self.cb_duty.get() and self.cb_duty.get() not in relevant:
            self.cb_duty.set("")

    def _update_calc_methods(self):
        has_type = bool(self.cb_type.get())
        has_duty = bool(self.cb_duty.get())
        has_question = bool(self.cb_question.get())

        if has_type:
            allowed = [CalcMethod.DURATION.value, CalcMethod.START_TIME.value, CalcMethod.COUNT.value]
        elif has_duty:
            allowed = [CalcMethod.DUTY_DONE.value, CalcMethod.DUTY_MARK.value]
        elif has_question:
            allowed = [CalcMethod.QUESTION_LAST.value]
        else:
            allowed = [e.value for e in CalcMethod]

        self.cb_calc_method['values'] = allowed
        if self.cb_calc_method.get() not in allowed:
            self.cb_calc_method.set(allowed[0] if allowed else "")

    # ------------------------------------------------------------------
    # Обработчики
    # ------------------------------------------------------------------
    def _on_filter_changed(self):
        self.prefs_repo.set("indicator_config_affects_filter", self.var_affects_filter.get())
        self.prefs_repo.set("indicator_config_metric_type_filter", self.var_metric_type_filter.get())
        self._load_indicators()

    def _on_metric_changed(self, event=None):
        self._update_duty_values()

    def _on_type_selected(self, event=None):
        if self.cb_type.get():
            self.cb_duty.set("")
            self.cb_question.set("")
        self._update_calc_methods()

    def _on_duty_selected(self, event=None):
        if self.cb_duty.get():
            self.cb_type.set("")
            self.cb_question.set("")
        self._update_calc_methods()

    def _on_question_selected(self, event=None):
        if self.cb_question.get():
            self.cb_type.set("")
            self.cb_duty.set("")
        self._update_calc_methods()

    def _on_indicator_row_selected(self, event=None):
        sel = self.sheet_indicators.get_currently_selected()
        row = getattr(sel, "row", None)
        if row is None:
            return
        ind_id = self.sheet_indicators.get_cell_data(row, 0)
        try:
            ind_id = int(ind_id)
        except (ValueError, TypeError):
            return
        self._load_indicator_into_form(ind_id)

    def _load_indicator_into_form(self, ind_id: int):
        indicators = self.indicator_repo.get_all()
        ind = next((i for i in indicators if i['id'] == ind_id), None)
        if not ind:
            return
        self.current_indicator_id = ind_id

        self.cb_metric.set(self._metric_display(ind['metric_id']))
        self._update_duty_values()

        self.cb_type.set("")
        self.cb_duty.set("")
        self.cb_question.set("")
        if ind['activity_type_id']:
            self.cb_type.set(self.types_id_to_name.get(ind['activity_type_id'], ""))
        elif ind['regular_duty_id']:
            self.cb_duty.set(self.duties_id_to_name.get(ind['regular_duty_id'], ""))
        elif ind['question_id']:
            qname = self.questions_id_to_name.get(ind['question_id'], "")
            self.cb_question.set(f"#{ind['question_id']}: {qname}")

        self.cb_affects.set(ind.get('affects') or "")

        self.ent_name.delete(0, tk.END)
        self.ent_name.insert(0, ind['name'] or "")
        self.ent_desc.delete(0, tk.END)
        self.ent_desc.insert(0, ind['description'] or "")
        self.ent_unit.delete(0, tk.END)
        self.ent_unit.insert(0, ind['unit'] or "")
        self.cb_value_type.set(ind['value_type'])
        self.cb_goal_type.set(ind['goal_type'])

        self._update_calc_methods()
        self.cb_calc_method.set(ind['calc_method'])

        self.ent_target.delete(0, tk.END)
        self.ent_target.insert(0, ind['target_value'] or "")
        self.ent_step.delete(0, tk.END)
        self.ent_step.insert(0, str(ind['goal_step'] or 0))
        self.ent_penalty.delete(0, tk.END)
        self.ent_penalty.insert(0, str(ind['goal_penalty'] or 0))
        self.ent_weight.delete(0, tk.END)
        # weight=0 должен показываться как 0, а не подменяться на 50.
        self.ent_weight.insert(
            0, str(ind['weight']) if ind['weight'] is not None else "50"
        )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def on_add(self):
        self.current_indicator_id = None
        try:
            self.sheet_indicators.deselect()
        except Exception:
            pass

        self.cb_metric.set("")
        self.cb_type.set("")
        self.cb_duty.set("")
        self.cb_question.set("")
        self.cb_affects.set("")
        self._update_duty_values()
        self.ent_name.delete(0, tk.END)
        self.ent_desc.delete(0, tk.END)
        self.ent_unit.delete(0, tk.END)
        self.cb_value_type.set(ValueType.NUMBER.value)
        self.cb_goal_type.set(GoalType.MAXIMIZE.value)
        self._update_calc_methods()
        self.ent_target.delete(0, tk.END)
        self.ent_step.delete(0, tk.END)
        self.ent_step.insert(0, "0")
        self.ent_penalty.delete(0, tk.END)
        self.ent_penalty.insert(0, "0")
        self.ent_weight.delete(0, tk.END)
        self.ent_weight.insert(0, "50")

    def on_save(self):
        try:
            metric_id = self.metrics_map.get(self.cb_metric.get())
            if not metric_id:
                messagebox.showwarning("Ошибка", "Выберите метрику!")
                return

            type_name = self.cb_type.get() or ""
            duty_name = self.cb_duty.get() or ""
            question_name = self.cb_question.get() or ""

            chosen = [n for n in (type_name, duty_name, question_name) if n]
            if not chosen:
                messagebox.showwarning(
                    "Ошибка",
                    "Выберите ровно один источник: тип активности, обязанность или вопрос!"
                )
                return
            if len(chosen) > 1:
                messagebox.showwarning(
                    "Ошибка",
                    "Выберите только один источник (тип / обязанность / вопрос)!"
                )
                return

            affects = self.cb_affects.get()
            if not affects:
                messagebox.showwarning(
                    "Ошибка",
                    "Выберите, на что влияет индикатор: satisfaction или attention."
                )
                return

            type_id = self.types_map.get(type_name) if type_name else None
            duty_id = self.duties_map.get(duty_name) if duty_name else None
            question_id = self.questions_map.get(question_name) if question_name else None

            name = self.ent_name.get().strip()
            if not name:
                messagebox.showwarning("Ошибка", "Название не может быть пустым!")
                return

            calc_method = self.cb_calc_method.get()

            if type_id and calc_method in (
                CalcMethod.DUTY_DONE.value, CalcMethod.DUTY_MARK.value,
                CalcMethod.QUESTION_LAST.value,
            ):
                messagebox.showwarning(
                    "Ошибка",
                    "Для индикатора по типу активности нельзя выбрать метод "
                    f"'{calc_method}'. Доступно: calc_duration, calc_start_time, calc_count."
                )
                return
            if duty_id and calc_method not in (CalcMethod.DUTY_DONE.value, CalcMethod.DUTY_MARK.value):
                messagebox.showwarning(
                    "Ошибка",
                    "Для индикатора по обязанности доступны только "
                    "calc_duty_done и calc_duty_mark."
                )
                return
            if question_id and calc_method != CalcMethod.QUESTION_LAST.value:
                messagebox.showwarning(
                    "Ошибка",
                    "Для индикатора по вопросу доступен только calc_question_last."
                )
                return

            if duty_id:
                info = self.all_duties_info.get(duty_name, {})
                duty_ptype = info.get("period_type")
                metric = next((m for m in self.all_metrics if m['id'] == metric_id), None)
                if metric and duty_ptype != metric['type']:
                    messagebox.showwarning(
                        "Ошибка",
                        f"Период обязанности ({duty_ptype}) не совпадает "
                        f"с типом метрики ({metric['type']})."
                    )
                    return

            data = {
                "metric_id": metric_id,
                "activity_type_id": type_id,
                "regular_duty_id": duty_id,
                "question_id": question_id,
                "affects": affects,
                "name": name,
                "description": self.ent_desc.get().strip(),
                "unit": self.ent_unit.get().strip(),
                "value_type": self.cb_value_type.get(),
                "goal_type": self.cb_goal_type.get(),
                "target_value": self.ent_target.get().strip(),
                "goal_step": float(self.ent_step.get() or 0),
                "goal_penalty": float(self.ent_penalty.get() or 0),
                "weight": int(self.ent_weight.get().strip() or 50),
                "calc_method": calc_method,
            }

            if self.current_indicator_id is None:
                self.indicator_repo.add(**data)
            else:
                self.indicator_repo.update(indicator_id=self.current_indicator_id, **data)

            # Q-04 (из прошлого раунда): сброс фильтра affects на «Все»
            self.var_affects_filter.set("all")
            self.prefs_repo.set("indicator_config_affects_filter", "all")

            self.refresh_data()
            messagebox.showinfo("Успех", "Индикатор сохранен!")
        except ValueError:
            messagebox.showerror("Ошибка", "Проверьте, что Шаг, Штраф и Вес — это числа!")
        except Exception as e:
            messagebox.showerror("Ошибка БД", f"Не удалось сохранить:\n{e}")

    def on_delete(self):
        if self.current_indicator_id is None:
            messagebox.showwarning("Внимание", "Выберите индикатор для удаления!")
            return
        if messagebox.askyesno("Подтверждение", "Удалить выбранный индикатор?"):
            try:
                self.indicator_repo.delete(self.current_indicator_id)
                self.current_indicator_id = None
                try:
                    self.sheet_indicators.deselect()
                except Exception:
                    pass
                self.refresh_data()
            except Exception as e:
                messagebox.showerror("Ошибка БД", f"Не удалось удалить:\n{e}")