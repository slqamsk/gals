# src/questionnaires_settings_tab.py
# Вкладка «Настройка»: дерево ролей слева; справа — вопросы (сверху) и варианты (снизу).
#
# В preferences сохраняются: ширины колонок обеих таблиц,
# разделитель «дерево | контент» (sash_h) и «вопросы | варианты» (sash_v).
import json
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

from tksheet import Sheet


class QuestionnairesSettingsTab(tk.Frame):
    WIDTHS_QUESTIONS = [50, 250, 120, 120]
    WIDTHS_OPTIONS = [50, 100, 300]

    def __init__(self, parent, repo, roles_repo, sub_roles_repo, prefs_repo):
        super().__init__(parent)
        self.repo = repo
        self.roles_repo = roles_repo
        self.sub_roles_repo = sub_roles_repo
        self.prefs_repo = prefs_repo

        self.current_role_id = None
        self.current_sub_role_id = None
        self.current_question_id = None
        self.roles_id_to_name = {}
        self.sub_roles_id_to_name = {}

        self.paned = tk.PanedWindow(self, orient="horizontal", sashwidth=5)
        self.paned.pack(fill="both", expand=True, padx=10, pady=5)

        self._build_tree()
        self._build_right()
        self._load_widths()
        self._restore_sashes()
        self.refresh_all()

    def _build_tree(self):
        frame = tk.Frame(self.paned)
        self.paned.add(frame, stretch="never", width=280)
        tk.Label(frame, text="Роли / Под-роли:", font=("Arial", 10, "bold")).pack(anchor="w")
        self.tree = ttk.Treeview(frame, show="tree", selectmode="browse")
        self.tree.pack(fill="both", expand=True, pady=2)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.paned.bind("<ButtonRelease-1>", self._save_sash_h)

    def _build_right(self):
        frame = tk.Frame(self.paned)
        self.paned.add(frame, stretch="always")

        self.vpaned = tk.PanedWindow(frame, orient="vertical", sashwidth=5)
        self.vpaned.pack(fill="both", expand=True)
        self.vpaned.bind("<ButtonRelease-1>", self._save_sash_v)

        top = tk.Frame(self.vpaned)
        self.vpaned.add(top, stretch="always", height=300)

        btns_t = tk.Frame(top)
        btns_t.pack(fill="x", pady=2)
        tk.Label(btns_t, text="Вопросы:", font=("Arial", 10, "bold")).pack(side="left")
        tk.Button(btns_t, text="Добавить вопрос",
                  command=self._add_question).pack(side="right", padx=2)
        tk.Button(btns_t, text="Удалить", fg="red",
                  command=self._delete_question).pack(side="right", padx=2)

        self.sheet_questions = Sheet(
            top, headers=["ID", "Текст", "Роль", "Подроль"],
            show_row_index=False, show_top_left=False,
            show_x_scrollbar=True, show_y_scrollbar=True,
            table_grid_fg="#000000", outline_thickness=1,
            header_bg="#f0f0f0", header_fg="#000000",
            font=("Arial", 9, "normal"), header_font=("Arial", 9, "bold"),
            row_height=25, auto_resize_row_heights=True,
        )
        self.sheet_questions.pack(fill="both", expand=True)
        self.sheet_questions.enable_bindings("all")
        self.sheet_questions.readonly_columns(columns=[0, 2, 3])
        self.sheet_questions.extra_bindings("end_edit_cell", self._on_question_edited)
        self.sheet_questions.extra_bindings("cell_select", self._on_question_select)
        self.sheet_questions.MT.bind("<Double-Button-1>",
                                     self._on_question_dblclick, add="+")

        bottom = tk.Frame(self.vpaned)
        self.vpaned.add(bottom, stretch="always", height=300)

        btns_b = tk.Frame(bottom)
        btns_b.pack(fill="x", pady=2)
        tk.Label(btns_b, text="Варианты ответа:", font=("Arial", 10, "bold")).pack(side="left")
        tk.Button(btns_b, text="Добавить вариант",
                  command=self._add_option).pack(side="right", padx=2)
        tk.Button(btns_b, text="Удалить", fg="red",
                  command=self._delete_option).pack(side="right", padx=2)

        self.sheet_options = Sheet(
            bottom, headers=["ID", "Значение", "Описание"],
            show_row_index=False, show_top_left=False,
            show_x_scrollbar=True, show_y_scrollbar=True,
            table_grid_fg="#000000", outline_thickness=1,
            header_bg="#f0f0f0", header_fg="#000000",
            font=("Arial", 9, "normal"), header_font=("Arial", 9, "bold"),
            row_height=25, auto_resize_row_heights=True,
        )
        self.sheet_options.pack(fill="both", expand=True)
        self.sheet_options.enable_bindings("all")
        self.sheet_options.readonly_columns(columns=[0])
        self.sheet_options.extra_bindings("end_edit_cell", self._on_option_edited)

    # ---------- Сохранение / восстановление GUI ----------
    def _get_widths(self, key: str, default: list[int]) -> list[int]:
        try:
            raw = self.prefs_repo.get(key)
            widths = json.loads(raw) if isinstance(raw, str) else raw
            if (isinstance(widths, list) and len(widths) == len(default)
                    and all(w is not None for w in widths)):
                return [int(w) for w in widths]
        except Exception:
            pass
        return list(default)

    def _load_widths(self):
        """Один раз при создании. При обновлении данных не вызывать."""
        try:
            self.sheet_questions.set_column_widths(
                self._get_widths("questionnaires_questions_col_widths",
                                 self.WIDTHS_QUESTIONS))
            self.sheet_options.set_column_widths(
                self._get_widths("questionnaires_options_col_widths",
                                 self.WIDTHS_OPTIONS))
        except Exception:
            pass

    def _restore_sashes(self):
        def apply():
            pos_h = self.prefs_repo.get("questionnaires_settings_sash_h")
            if isinstance(pos_h, int):
                try:
                    self.paned.sash_place(0, pos_h, 0)
                except tk.TclError:
                    pass
            pos_v = self.prefs_repo.get("questionnaires_settings_sash_v")
            if isinstance(pos_v, int):
                try:
                    self.vpaned.sash_place(0, 0, pos_v)
                except tk.TclError:
                    pass
        self.after(50, apply)

    def _save_sash_h(self, event=None):
        try:
            x, _y = self.paned.sash_coord(0)
            self.prefs_repo.set("questionnaires_settings_sash_h", x)
        except Exception:
            pass

    def _save_sash_v(self, event=None):
        try:
            _x, y = self.vpaned.sash_coord(0)
            self.prefs_repo.set("questionnaires_settings_sash_v", y)
        except Exception:
            pass

    def save_state(self):
        for sheet, key in (
            (self.sheet_questions, "questionnaires_questions_col_widths"),
            (self.sheet_options, "questionnaires_options_col_widths"),
        ):
            try:
                widths = sheet.get_column_widths()
                if widths and all(int(w) > 0 for w in widths):
                    self.prefs_repo.set(key, json.dumps([int(w) for w in widths]))
            except Exception:
                pass
        self._save_sash_h()
        self._save_sash_v()

    # ---------- Данные ----------
    def refresh_all(self):
        prev_role, prev_sub = self.current_role_id, self.current_sub_role_id
        self.roles_id_to_name = {r[0]: r[1] for r in self.roles_repo.get_all()}
        self.sub_roles_id_to_name = {}
        for r in self.roles_repo.get_all():
            for sr in self.sub_roles_repo.get_by_parent(r[0]):
                self.sub_roles_id_to_name[sr[0]] = sr[1]

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

        self._load_questions()

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
        self._load_questions()

    def _load_questions(self):
        questions = self.repo.get_filtered(
            role_id=self.current_role_id,
            sub_role_id=self.current_sub_role_id,
            include_common=False,
        )
        rows = []
        for q in questions:
            qid, text, rid, srid = q
            rname = self.roles_id_to_name.get(rid, "") if rid else ""
            srname = self.sub_roles_id_to_name.get(srid, "") if srid else ""
            rows.append([qid, text, rname, srname])
        self.sheet_questions.set_sheet_data(rows, reset_col_positions=False)
        self.sheet_options.set_sheet_data([], reset_col_positions=False)
        self.current_question_id = None

    def _on_question_select(self, event=None):
        sel = self.sheet_questions.get_currently_selected()
        row = getattr(sel, "row", None)
        if row is None:
            self.current_question_id = None
            self.sheet_options.set_sheet_data([], reset_col_positions=False)
            return
        qid = self.sheet_questions.get_cell_data(row, 0)
        try:
            self.current_question_id = int(qid)
        except (ValueError, TypeError):
            return
        self._load_options()

    def _load_options(self):
        if self.current_question_id is None:
            self.sheet_options.set_sheet_data([], reset_col_positions=False)
            return
        opts = self.repo.get_options_for_question(self.current_question_id)
        rows = [[o[0], o[2], o[3]] for o in opts]
        self.sheet_options.set_sheet_data(rows, reset_col_positions=False)

    def _on_question_edited(self, event):
        if event.column != 1:
            return
        row = event.row
        qid = self.sheet_questions.get_cell_data(row, 0)
        try:
            qid = int(qid)
        except (ValueError, TypeError):
            return
        text = self.sheet_questions.get_cell_data(row, 1)
        if not text or not str(text).strip():
            messagebox.showwarning("Ошибка", "Текст не может быть пустым")
            self._load_questions()
            return
        q = self.repo.get_by_id(qid)
        if not q:
            return
        try:
            self.repo.update(qid, str(text).strip(), q[2], q[3])
        except Exception as e:
            messagebox.showerror("Ошибка БД", str(e))
        self._load_questions()

    def _on_question_dblclick(self, event):
        row = self.sheet_questions.identify_row(event)
        col = self.sheet_questions.identify_column(event)
        if row == "" or col == "":
            return
        try:
            row = int(row); col = int(col)
        except ValueError:
            return
        if col in [2, 3]:
            self._open_role_picker(row)

    def _open_role_picker(self, row):
        qid = self.sheet_questions.get_cell_data(row, 0)
        try:
            qid = int(qid)
        except (ValueError, TypeError):
            return
        q = self.repo.get_by_id(qid)
        if not q:
            return

        dialog = tk.Toplevel(self)
        dialog.transient(self.winfo_toplevel())
        dialog.title("Привязка вопроса")
        dialog.geometry("450x550")
        dialog.grab_set()

        tree = ttk.Treeview(dialog, show="tree", selectmode="browse")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        tree.insert("", "end", iid="none", text="(общий, без привязки)")
        tree.insert("", "end", iid="root", text="📁 Все роли")
        for r in sorted(self.roles_repo.get_all(), key=lambda x: x[0]):
            rid, name = r[0], r[1]
            tree.insert("root", "end", iid=f"role_{rid}", text=f"{rid}. {name}")
            for sr in sorted(self.sub_roles_repo.get_by_parent(rid), key=lambda x: x[0]):
                tree.insert(f"role_{rid}", "end",
                            iid=f"sub_{sr[0]}", text=sr[1])

        def select():
            sel = tree.selection()
            if not sel:
                return
            iid = sel[0]
            if iid == "none":
                new_rid, new_srid = None, None
            elif iid == "root":
                return
            elif iid.startswith("role_"):
                new_rid = int(iid.replace("role_", ""))
                new_srid = None
            else:
                new_srid = int(iid.replace("sub_", ""))
                new_rid = None
            try:
                self.repo.update(qid, q[1], new_rid, new_srid)
            except Exception as e:
                messagebox.showerror("Ошибка БД", str(e), parent=dialog)
                return
            dialog.destroy()
            self._load_questions()

        tree.bind("<Double-Button-1>", lambda e: select())
        tk.Button(dialog, text="Выбрать", command=select).pack(pady=10)

    def _add_question(self):
        dialog = tk.Toplevel(self)
        dialog.transient(self.winfo_toplevel())
        dialog.title("Новый вопрос")
        dialog.geometry("420x220")
        dialog.grab_set()

        tk.Label(dialog, text="Текст вопроса:",
                 anchor="w").pack(fill="x", padx=15, pady=(15, 0))
        ent_text = tk.Entry(dialog)
        ent_text.pack(fill="x", padx=15, pady=2)

        if self.current_sub_role_id is not None:
            scope = "подроли"
        elif self.current_role_id is not None:
            scope = "роли"
        else:
            scope = "как общий (без привязки)"
        tk.Label(dialog, text=f"Будет создан для {scope}",
                 fg="gray").pack(anchor="w", padx=15, pady=5)

        def save():
            text = ent_text.get().strip()
            if not text:
                messagebox.showerror("Ошибка", "Текст пуст", parent=dialog)
                return
            try:
                self.repo.add(text, self.current_role_id, self.current_sub_role_id)
            except Exception as e:
                messagebox.showerror("Ошибка БД", str(e), parent=dialog)
                return
            dialog.destroy()
            self._load_questions()

        frame_btns = tk.Frame(dialog)
        frame_btns.pack(pady=15)
        tk.Button(frame_btns, text="Сохранить", command=save,
                  width=12).pack(side="left", padx=5)
        tk.Button(frame_btns, text="Отмена", command=dialog.destroy,
                  width=12).pack(side="left", padx=5)

    def _delete_question(self):
        sel = self.sheet_questions.get_currently_selected()
        row = getattr(sel, "row", None)
        if row is None:
            messagebox.showwarning("Внимание", "Выберите вопрос")
            return
        qid = self.sheet_questions.get_cell_data(row, 0)
        try:
            qid = int(qid)
        except (ValueError, TypeError):
            return

        cnt = self.repo.get_answers_count(qid)
        if cnt > 0:
            messagebox.showerror("Ошибка удаления",
                                 f"У вопроса есть ответы ({cnt}). Удалить нельзя.")
            return

        if not messagebox.askyesno("Подтверждение", f"Удалить вопрос #{qid}?"):
            return

        try:
            self.repo.delete(qid)
        except sqlite3.IntegrityError as e:
            messagebox.showerror("Ошибка", f"Нельзя удалить: {e}")
            return
        except Exception as e:
            messagebox.showerror("Ошибка БД", str(e))
            return
        self._load_questions()

    def _on_option_edited(self, event):
        if self.current_question_id is None:
            return
        row = event.row
        oid = self.sheet_options.get_cell_data(row, 0)
        try:
            oid = int(oid)
        except (ValueError, TypeError):
            return
        try:
            val = int(self.sheet_options.get_cell_data(row, 1))
        except (ValueError, TypeError):
            messagebox.showwarning("Ошибка", "Значение — целое 0-100")
            self._load_options()
            return
        if not (0 <= val <= 100):
            messagebox.showwarning("Ошибка", "Значение 0-100")
            self._load_options()
            return
        desc = self.sheet_options.get_cell_data(row, 2)
        if not desc or not str(desc).strip():
            messagebox.showwarning("Ошибка", "Описание пусто")
            self._load_options()
            return
        try:
            self.repo.update_option(oid, val, str(desc).strip())
        except sqlite3.IntegrityError:
            messagebox.showerror("Ошибка", "Вариант с таким значением уже есть")
        except Exception as e:
            messagebox.showerror("Ошибка БД", str(e))
        self._load_options()

    def _add_option(self):
        if self.current_question_id is None:
            messagebox.showwarning("Внимание", "Выберите вопрос")
            return

        dialog = tk.Toplevel(self)
        dialog.transient(self.winfo_toplevel())
        dialog.title("Новый вариант")
        dialog.geometry("400x180")
        dialog.grab_set()

        tk.Label(dialog, text="Значение (0-100):",
                 anchor="w").pack(fill="x", padx=15, pady=(15, 0))
        ent_val = tk.Entry(dialog)
        ent_val.pack(fill="x", padx=15, pady=2)

        tk.Label(dialog, text="Описание:",
                 anchor="w").pack(fill="x", padx=15, pady=(10, 0))
        ent_desc = tk.Entry(dialog)
        ent_desc.pack(fill="x", padx=15, pady=2)

        def save():
            try:
                v = int(ent_val.get().strip())
            except ValueError:
                messagebox.showerror("Ошибка", "Значение — целое 0-100", parent=dialog)
                return
            if not (0 <= v <= 100):
                messagebox.showerror("Ошибка", "Значение 0-100", parent=dialog)
                return
            d = ent_desc.get().strip()
            if not d:
                messagebox.showerror("Ошибка", "Описание пусто", parent=dialog)
                return
            try:
                self.repo.add_option(self.current_question_id, v, d)
            except sqlite3.IntegrityError:
                messagebox.showerror("Ошибка", "Вариант с таким значением уже есть",
                                     parent=dialog)
                return
            except Exception as e:
                messagebox.showerror("Ошибка БД", str(e), parent=dialog)
                return
            dialog.destroy()
            self._load_options()

        frame_btns = tk.Frame(dialog)
        frame_btns.pack(pady=15)
        tk.Button(frame_btns, text="Сохранить", command=save,
                  width=12).pack(side="left", padx=5)
        tk.Button(frame_btns, text="Отмена", command=dialog.destroy,
                  width=12).pack(side="left", padx=5)

    def _delete_option(self):
        if self.current_question_id is None:
            return
        sel = self.sheet_options.get_currently_selected()
        row = getattr(sel, "row", None)
        if row is None:
            messagebox.showwarning("Внимание", "Выберите вариант")
            return
        oid = self.sheet_options.get_cell_data(row, 0)
        try:
            oid = int(oid)
        except (ValueError, TypeError):
            return
        if not messagebox.askyesno(
            "Подтверждение",
            f"Удалить вариант #{oid}?\n"
            f"Ответы, созданные с ним, не пострадают (хранят снимок)."
        ):
            return
        try:
            self.repo.delete_option(oid)
        except Exception as e:
            messagebox.showerror("Ошибка БД", str(e))
            return
        self._load_options()