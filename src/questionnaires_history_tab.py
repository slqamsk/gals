# src/questionnaires_history_tab.py
# Вкладка «История»: дерево ролей слева, таблица ответов справа.
#
# В preferences сохраняются: ширины колонок таблицы, позиция разделителя
# «дерево | таблица», режим периода, выбранная дата и выбранный вопрос.
import json
import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
from datetime import datetime, timedelta

from tksheet import Sheet

from . import datetime_utils


class QuestionnairesHistoryTab(tk.Frame):
    PERIODS = ["Все", "Сегодня", "Вчера", "За 7 дней", "За 30 дней", "Выбрать дату"]
    WIDTHS = [50, 140, 200, 70, 250, 250]

    def __init__(self, parent, repo, roles_repo, sub_roles_repo, prefs_repo):
        super().__init__(parent)
        self.repo = repo
        self.roles_repo = roles_repo
        self.sub_roles_repo = sub_roles_repo
        self.prefs_repo = prefs_repo

        self.current_role_id = None
        self.current_sub_role_id = None
        self.questions_map = {}
        self.qid_to_text = {}

        # Пока идёт восстановление состояния — не пишем prefs.
        self._restoring = True

        self.paned = tk.PanedWindow(self, orient="horizontal", sashwidth=5)
        self.paned.pack(fill="both", expand=True, padx=10, pady=5)

        self._build_tree()
        self._build_right()
        self._load_widths()
        self._restore_sash()
        self._restore_filters()
        self._restoring = False
        self.refresh_all()

    def _build_tree(self):
        frame = tk.Frame(self.paned)
        self.paned.add(frame, stretch="never", width=280)
        tk.Label(frame, text="Роли / Под-роли:", font=("Arial", 10, "bold")).pack(anchor="w")
        self.tree = ttk.Treeview(frame, show="tree", selectmode="browse")
        self.tree.pack(fill="both", expand=True, pady=2)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.paned.bind("<ButtonRelease-1>", self._save_sash)

    def _build_right(self):
        frame = tk.Frame(self.paned)
        self.paned.add(frame, stretch="always")

        top = tk.Frame(frame)
        top.pack(fill="x", pady=5)

        tk.Label(top, text="Период:").pack(side="left")
        self.cb_period = ttk.Combobox(top, state="readonly",
                                      values=self.PERIODS, width=15)
        self.cb_period.set("Все")
        self.cb_period.pack(side="left", padx=5)
        self.cb_period.bind("<<ComboboxSelected>>", self._on_period_changed)

        self.date_entry = DateEntry(top, width=12,
                                    date_pattern='yyyy-mm-dd', locale='ru_RU')
        self.date_entry.pack(side="left", padx=5)
        self.date_entry.config(state="disabled")
        self.date_entry.bind("<<DateEntrySelected>>", self._on_date_changed)

        tk.Label(top, text="Вопрос:").pack(side="left", padx=(15, 0))
        self.cb_question = ttk.Combobox(top, state="readonly", width=30)
        self.cb_question.pack(side="left", padx=5)
        self.cb_question.bind("<<ComboboxSelected>>", self._on_question_changed)

        tk.Button(top, text="Обновить", command=self.refresh_table).pack(side="left", padx=5)
        tk.Button(top, text="Удалить выбранный", fg="red",
                  command=self._on_delete).pack(side="left", padx=5)

        self.sheet = Sheet(
            frame,
            headers=["ID", "Дата-время", "Вопрос", "Значение", "Описание", "Комментарий"],
            show_row_index=False, show_top_left=False,
            show_x_scrollbar=True, show_y_scrollbar=True,
            table_grid_fg="#000000", outline_thickness=1,
            header_bg="#f0f0f0", header_fg="#000000",
            font=("Arial", 9, "normal"), header_font=("Arial", 9, "bold"),
            row_height=25, auto_resize_row_heights=True,
        )
        self.sheet.pack(fill="both", expand=True)
        self.sheet.enable_bindings("all")
        self.sheet.readonly_columns(columns=[0, 2])
        self.sheet.extra_bindings("end_edit_cell", self._on_edit)
        self.sheet.MT.bind("<Double-Button-1>", self._on_double_click, add="+")
        # Ширины применяются в _load_widths() после создания таблицы.

    # ------------------------------------------------------------------
    # Фильтры
    # ------------------------------------------------------------------
    def _on_period_changed(self, event=None):
        if self.cb_period.get() == "Выбрать дату":
            self.date_entry.config(state="normal")
        else:
            self.date_entry.config(state="disabled")
        if not self._restoring:
            self.save_state()
        self.refresh_table()

    def _on_date_changed(self, event=None):
        if not self._restoring:
            self.save_state()
        self.refresh_table()

    def _on_question_changed(self, event=None):
        if not self._restoring:
            self.save_state()
        self.refresh_table()

    # ------------------------------------------------------------------
    # Сохранение / восстановление GUI
    # ------------------------------------------------------------------
    def _load_widths(self):
        """Один раз при создании. При обновлении данных не вызывать —
        иначе сбросятся ширины, подвинутые мышью, но ещё не сохранённые."""
        widths = list(self.WIDTHS)
        try:
            raw = self.prefs_repo.get("questionnaires_history_col_widths")
            saved = json.loads(raw) if isinstance(raw, str) else raw
            if (isinstance(saved, list) and len(saved) == len(self.WIDTHS)
                    and all(w is not None for w in saved)):
                widths = [int(w) for w in saved]
        except Exception:
            pass
        try:
            self.sheet.set_column_widths(widths)
        except Exception:
            pass

    def _restore_sash(self):
        pos = self.prefs_repo.get("questionnaires_history_sash")
        if not isinstance(pos, int):
            return

        def apply():
            try:
                self.paned.sash_place(0, pos, 0)
            except tk.TclError:
                pass
        self.after(50, apply)

    def _save_sash(self, event=None):
        if self._restoring:
            return
        try:
            x, _y = self.paned.sash_coord(0)
            self.prefs_repo.set("questionnaires_history_sash", x)
        except Exception:
            pass

    def _restore_filters(self):
        period = self.prefs_repo.get("questionnaires_history_period")
        if period not in self.PERIODS:
            period = "Все"
        self.cb_period.set(period)
        self.date_entry.config(
            state="normal" if period == "Выбрать дату" else "disabled")

        saved_date = self.prefs_repo.get("questionnaires_history_date")
        if saved_date:
            try:
                self.date_entry.set_date(datetime.strptime(saved_date, "%Y-%m-%d"))
            except Exception:
                pass

        # Список вопросов заполняем здесь, чтобы восстановленный выбор
        # не сбросился при первом refresh_table().
        self._reload_questions()
        saved_qid = self.prefs_repo.get("questionnaires_history_question_id")
        if saved_qid is not None:
            for name, qid in self.questions_map.items():
                if qid == saved_qid:
                    self.cb_question.set(name)
                    break

    def _reload_questions(self):
        """Обновляет список вопросов, сохраняя текущий выбор."""
        prev = self.cb_question.get() or "Все"
        all_questions = self.repo.get_all()
        self.qid_to_text = {q[0]: q[1] for q in all_questions}
        self.questions_map = {"Все": None}
        for q in all_questions:
            self.questions_map[q[1]] = q[0]
        self.cb_question['values'] = list(self.questions_map.keys())
        self.cb_question.set(prev if prev in self.questions_map else "Все")

    def save_state(self):
        try:
            widths = self.sheet.get_column_widths()
            if widths and all(int(w) > 0 for w in widths):
                self.prefs_repo.set("questionnaires_history_col_widths",
                                    json.dumps([int(w) for w in widths]))
        except Exception:
            pass
        self._save_sash()
        self.prefs_repo.set("questionnaires_history_period", self.cb_period.get())
        self.prefs_repo.set("questionnaires_history_question_id",
                            self.questions_map.get(self.cb_question.get()))
        try:
            self.prefs_repo.set("questionnaires_history_date",
                                self.date_entry.get_date().strftime("%Y-%m-%d"))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Данные
    # ------------------------------------------------------------------
    def _get_date_range(self):
        period = self.cb_period.get()
        today = datetime_utils.to_datetime(datetime_utils.get_now_iso()).date()

        if period == "Все":
            return None, None
        if period == "Сегодня":
            d = today.isoformat()
            return f"{d}T00:00:00+03:00", f"{d}T23:59:59+03:00"
        if period == "Вчера":
            d = (today - timedelta(days=1)).isoformat()
            return f"{d}T00:00:00+03:00", f"{d}T23:59:59+03:00"
        if period == "За 7 дней":
            d = (today - timedelta(days=6)).isoformat()
            return f"{d}T00:00:00+03:00", None
        if period == "За 30 дней":
            d = (today - timedelta(days=29)).isoformat()
            return f"{d}T00:00:00+03:00", None
        if period == "Выбрать дату":
            d = self.date_entry.get_date().strftime("%Y-%m-%d")
            return f"{d}T00:00:00+03:00", f"{d}T23:59:59+03:00"
        return None, None

    def refresh_all(self):
        prev_role, prev_sub = self.current_role_id, self.current_sub_role_id
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.tree.insert("", "end", iid="root", text="📁 Все роли", open=True)
        for r in sorted(self.roles_repo.get_all(), key=lambda x: x[0]):
            rid, name = r[0], r[1]
            self.tree.insert("root", "end", iid=f"role_{rid}",
                             text=f"{rid}. {name}", open=True)
            for sr in sorted(self.sub_roles_repo.get_by_parent(rid), key=lambda x: x[0]):
                self.tree.insert(f"role_{rid}", "end",
                                 iid=f"sub_{sr[0]}", text=sr[1])

        if prev_sub is not None and self.tree.exists(f"sub_{prev_sub}"):
            self.tree.selection_set(f"sub_{prev_sub}")
        elif prev_role is not None and self.tree.exists(f"role_{prev_role}"):
            self.tree.selection_set(f"role_{prev_role}")
        elif self.tree.exists("root"):
            self.tree.selection_set("root")

        self.refresh_table()

    def _on_select(self, event=None):
        sel = self.tree.selection()
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
        self.refresh_table()

    def _get_qids_from_tree(self):
        if self.current_role_id is None and self.current_sub_role_id is None:
            return None
        qs = self.repo.get_filtered(
            role_id=self.current_role_id,
            sub_role_id=self.current_sub_role_id,
            include_common=False,
        )
        return [q[0] for q in qs]

    def refresh_table(self):
        self._reload_questions()

        q_filter = self.questions_map.get(self.cb_question.get())
        if q_filter is not None:
            qids = [q_filter]
        else:
            qids = self._get_qids_from_tree()

        df, dt = self._get_date_range()
        try:
            rows = self.repo.get_answers(question_ids=qids, date_from=df, date_to=dt)
        except Exception as e:
            messagebox.showerror("Ошибка БД", f"Не удалось загрузить:\n{e}")
            rows = []

        data = []
        for r in rows:
            aid, qid, val, desc, comment, measured = r
            data.append([
                aid,
                datetime_utils.to_display(measured),
                self.qid_to_text.get(qid, "?"),
                val,
                desc,
                comment or "",
            ])
        self.sheet.set_sheet_data(data, reset_col_positions=False)

    # ------------------------------------------------------------------
    # Редактирование
    # ------------------------------------------------------------------
    def _on_edit(self, event):
        row = event.row
        col = event.column
        if col in [0, 2]:
            return
        aid = self.sheet.get_cell_data(row, 0)
        try:
            aid = int(aid)
        except (ValueError, TypeError):
            return
        ans = self.repo.get_answer_by_id(aid)
        if not ans:
            return
        try:
            value = int(self.sheet.get_cell_data(row, 3))
        except (ValueError, TypeError):
            value = ans[2]
        desc = self.sheet.get_cell_data(row, 4) or ans[3]
        comment = self.sheet.get_cell_data(row, 5) or ""
        try:
            self.repo.update_answer(aid, value, str(desc), comment.strip() or None, ans[5])
        except Exception as e:
            messagebox.showerror("Ошибка БД", f"Не удалось сохранить:\n{e}")
        self.refresh_table()

    def _on_double_click(self, event):
        row = self.sheet.identify_row(event)
        col = self.sheet.identify_column(event)
        if row == "" or col == "":
            return
        try:
            row = int(row); col = int(col)
        except ValueError:
            return
        if col == 3:
            self._open_value_picker(row)

    def _open_value_picker(self, row):
        aid = self.sheet.get_cell_data(row, 0)
        try:
            aid = int(aid)
        except (ValueError, TypeError):
            return
        ans = self.repo.get_answer_by_id(aid)
        if not ans:
            return
        qid = ans[1]
        options = self.repo.get_options_for_question(qid)

        dialog = tk.Toplevel(self)
        dialog.transient(self.winfo_toplevel())
        dialog.title("Значение ответа")
        dialog.geometry("480x540")
        dialog.grab_set()

        tk.Label(dialog, text="Варианты ответа:",
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=15, pady=(10, 5))

        var_choice = tk.IntVar(value=-1)
        opts_data = {}
        for o in options:
            oid, _q, val, desc = o
            tk.Radiobutton(dialog, text=f"{val} — {desc}",
                           variable=var_choice, value=oid,
                           font=("Arial", 10)).pack(anchor="w", padx=25)
            opts_data[oid] = {"value": val, "description": desc}

        tk.Label(dialog, text="Или вручную:",
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=15, pady=(15, 0))

        frame_man = tk.Frame(dialog)
        frame_man.pack(fill="x", padx=15, pady=5)
        tk.Label(frame_man, text="Значение (0-100):").pack(side="left")
        var_val = tk.StringVar(value=str(ans[2]))
        tk.Entry(frame_man, textvariable=var_val, width=8).pack(side="left", padx=5)

        frame_desc = tk.Frame(dialog)
        frame_desc.pack(fill="x", padx=15, pady=5)
        tk.Label(frame_desc, text="Описание:").pack(side="left")
        var_desc = tk.StringVar(value=ans[3])
        tk.Entry(frame_desc, textvariable=var_desc, width=35).pack(side="left", padx=5, fill="x", expand=True)

        def on_choice(*args):
            oid = var_choice.get()
            if oid in opts_data:
                var_val.set(str(opts_data[oid]["value"]))
                var_desc.set(opts_data[oid]["description"])

        var_choice.trace_add("write", on_choice)

        def save():
            try:
                v = int(var_val.get())
            except ValueError:
                messagebox.showerror("Ошибка", "Значение — целое 0-100", parent=dialog)
                return
            if not (0 <= v <= 100):
                messagebox.showerror("Ошибка", "Значение 0-100", parent=dialog)
                return
            d = var_desc.get().strip()
            if not d:
                messagebox.showerror("Ошибка", "Описание не может быть пустым", parent=dialog)
                return
            try:
                self.repo.update_answer(aid, v, d, ans[4], ans[5])
            except Exception as e:
                messagebox.showerror("Ошибка БД", str(e), parent=dialog)
                return
            dialog.destroy()
            self.refresh_table()

        frame_btns = tk.Frame(dialog)
        frame_btns.pack(pady=15)
        tk.Button(frame_btns, text="Сохранить", command=save, width=12).pack(side="left", padx=5)
        tk.Button(frame_btns, text="Отмена", command=dialog.destroy, width=12).pack(side="left", padx=5)

    def _on_delete(self):
        sel = self.sheet.get_currently_selected()
        row = getattr(sel, "row", None)
        if row is None:
            messagebox.showwarning("Внимание", "Выберите ответ")
            return
        aid = self.sheet.get_cell_data(row, 0)
        try:
            aid = int(aid)
        except (ValueError, TypeError):
            return
        if not messagebox.askyesno("Подтверждение", f"Удалить ответ #{aid}?"):
            return
        try:
            self.repo.delete_answer(aid)
        except Exception as e:
            messagebox.showerror("Ошибка БД", str(e))
            return
        self.refresh_table()