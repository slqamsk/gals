# src/questionnaires_mark_tab.py
# Вкладка «Отмечание»: дерево ролей слева, форма ответов справа.
#
# В preferences сохраняется позиция разделителя «дерево | форма».
import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry

from . import datetime_utils


class QuestionnairesMarkTab(tk.Frame):
    def __init__(self, parent, repo, roles_repo, sub_roles_repo, prefs_repo):
        super().__init__(parent)
        self.repo = repo
        self.roles_repo = roles_repo
        self.sub_roles_repo = sub_roles_repo
        self.prefs_repo = prefs_repo

        self.current_role_id = None
        self.current_sub_role_id = None
        self.answers_state = {}

        self.paned = tk.PanedWindow(self, orient="horizontal", sashwidth=5)
        self.paned.pack(fill="both", expand=True, padx=10, pady=5)

        self._build_tree()
        self._build_right()
        self._restore_sash()
        self.refresh_all()

    def _build_tree(self):
        frame = tk.Frame(self.paned)
        self.paned.add(frame, stretch="never", width=280)
        tk.Label(frame, text="Роли / Под-роли:", font=("Arial", 10, "bold")).pack(anchor="w")
        self.tree = ttk.Treeview(frame, show="tree", selectmode="browse")
        self.tree.pack(fill="both", expand=True, pady=2)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.tag_configure("role_node", font=("Arial", 11, "bold"))
        self.paned.bind("<ButtonRelease-1>", self._save_sash)

    # ------------------------------------------------------------------
    # Сохранение / восстановление GUI
    # ------------------------------------------------------------------
    def _restore_sash(self):
        pos = self.prefs_repo.get("questionnaires_mark_sash")
        if not isinstance(pos, int):
            return

        def apply():
            try:
                self.paned.sash_place(0, pos, 0)
            except tk.TclError:
                pass
        self.after(50, apply)

    def _save_sash(self, event=None):
        try:
            x, _y = self.paned.sash_coord(0)
            self.prefs_repo.set("questionnaires_mark_sash", x)
        except Exception:
            pass

    def save_state(self):
        self._save_sash()

    # ------------------------------------------------------------------
    # Форма ответов
    # ------------------------------------------------------------------
    def _build_right(self):
        frame = tk.Frame(self.paned)
        self.paned.add(frame, stretch="always")

        top = tk.Frame(frame)
        top.pack(fill="x", pady=5)

        tk.Label(top, text="Дата и время:", font=("Arial", 10, "bold")).pack(side="left")
        now = datetime_utils.to_datetime(datetime_utils.get_now_iso())
        self.cal = DateEntry(
            top, width=12, background='darkblue', foreground='white', borderwidth=2,
            year=now.year, month=now.month, day=now.day,
            date_pattern='yyyy-mm-dd', locale='ru_RU'
        )
        self.cal.pack(side="left", padx=5)

        self.var_hour = tk.StringVar(value=now.strftime("%H"))
        self.var_min = tk.StringVar(value=now.strftime("%M"))
        tk.Spinbox(top, from_=0, to=23, width=3, textvariable=self.var_hour,
                   format="%02.0f").pack(side="left")
        tk.Label(top, text=":").pack(side="left")
        tk.Spinbox(top, from_=0, to=59, width=3, textvariable=self.var_min,
                   format="%02.0f").pack(side="left")
        tk.Button(top, text="Сейчас", command=self._set_now).pack(side="left", padx=10)

        container = tk.Frame(frame)
        container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(container, highlightthickness=0)
        sb = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)

        self.form_frame = tk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.form_frame, anchor="nw")
        self.form_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(1, width=e.width)
        )
        self.canvas.bind_all("<MouseWheel>",
                             lambda e: self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        bottom = tk.Frame(frame)
        bottom.pack(fill="x", pady=5)
        tk.Button(bottom, text="Сохранить", command=self._on_save,
                  font=("Arial", 10, "bold"), fg="green", width=15).pack(side="left")
        tk.Button(bottom, text="Очистить", command=self._on_clear,
                  font=("Arial", 10), width=15).pack(side="left", padx=10)

    def _set_now(self):
        now = datetime_utils.to_datetime(datetime_utils.get_now_iso())
        self.cal.set_date(now)
        self.var_hour.set(now.strftime("%H"))
        self.var_min.set(now.strftime("%M"))

    def refresh_all(self):
        prev_role, prev_sub = self.current_role_id, self.current_sub_role_id
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.tree.insert("", "end", iid="root", text="📁 Все роли", open=True)
        for r in sorted(self.roles_repo.get_all(), key=lambda x: x[0]):
            rid, name = r[0], r[1]
            self.tree.insert("root", "end", iid=f"role_{rid}",
                             text=f"{rid}. {name}", open=True, tags=("role_node",))
            for sr in sorted(self.sub_roles_repo.get_by_parent(rid), key=lambda x: x[0]):
                self.tree.insert(f"role_{rid}", "end",
                                 iid=f"sub_{sr[0]}", text=sr[1])

        if prev_sub is not None and self.tree.exists(f"sub_{prev_sub}"):
            self.tree.selection_set(f"sub_{prev_sub}")
        elif prev_role is not None and self.tree.exists(f"role_{prev_role}"):
            self.tree.selection_set(f"role_{prev_role}")
        elif self.tree.exists("root"):
            self.tree.selection_set("root")

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
        self._rebuild_form()

    def _rebuild_form(self):
        for w in self.form_frame.winfo_children():
            w.destroy()
        self.answers_state = {}

        questions = self.repo.get_filtered(
            role_id=self.current_role_id,
            sub_role_id=self.current_sub_role_id,
            include_common=True,
        )
        if not questions:
            tk.Label(self.form_frame,
                     text="Нет вопросов для выбранной роли/подроли",
                     fg="gray", font=("Arial", 10, "italic")).pack(pady=20)
            return

        for q in questions:
            qid, text, _rid, _srid = q
            block = tk.LabelFrame(self.form_frame, text=text,
                                  padx=10, pady=5, font=("Arial", 10, "bold"))
            block.pack(fill="x", pady=5, padx=5)

            options = self.repo.get_options_for_question(qid)
            if not options:
                tk.Label(block, text="(нет вариантов ответа)",
                         fg="red", font=("Arial", 9)).pack(anchor="w")
                continue

            var_value = tk.IntVar(value=-1)
            opts_data = {}
            for o in options:
                oid, _qid, val, desc = o
                tk.Radiobutton(block, text=f"{val} — {desc}",
                               variable=var_value, value=oid,
                               font=("Arial", 10)).pack(anchor="w", pady=1)
                opts_data[oid] = {"value": val, "description": desc}

            frame_c = tk.Frame(block)
            frame_c.pack(fill="x", pady=(5, 0))
            tk.Label(frame_c, text="Комментарий:", font=("Arial", 9)).pack(side="left")
            var_comment = tk.StringVar()
            tk.Entry(frame_c, textvariable=var_comment, font=("Arial", 10)).pack(
                side="left", fill="x", expand=True, padx=5
            )

            self.answers_state[qid] = {
                "var_value": var_value,
                "options": opts_data,
                "comment": var_comment,
            }

    def _on_clear(self):
        for info in self.answers_state.values():
            info["var_value"].set(-1)
            info["comment"].set("")

    def _on_save(self):
        if not self.answers_state:
            messagebox.showwarning("Ошибка", "Нет вопросов для сохранения")
            return
        try:
            h = int(self.var_hour.get())
            m = int(self.var_min.get())
        except (ValueError, TypeError):
            messagebox.showerror("Ошибка", "Некорректное время")
            return
        if not (0 <= h <= 23 and 0 <= m <= 59):
            messagebox.showerror("Ошибка", "Часы 0-23, минуты 0-59")
            return

        sd = self.cal.get_date()
        measured_at = f"{sd.year}-{sd.month:02d}-{sd.day:02d}T{h:02d}:{m:02d}:00+03:00"

        items = []
        for qid, info in self.answers_state.items():
            oid = info["var_value"].get()
            if oid == -1:
                continue
            opt = info["options"].get(oid)
            if not opt:
                continue
            items.append({
                "question_id": qid,
                "value": opt["value"],
                "option_description": opt["description"],
                "extra_comment": info["comment"].get().strip() or None,
            })

        if not items:
            messagebox.showwarning("Внимание", "Не выбрано ни одного ответа")
            return

        try:
            self.repo.add_answers_batch(items, measured_at)
        except Exception as e:
            messagebox.showerror("Ошибка БД", f"Не удалось сохранить:\n{e}")
            return

        messagebox.showinfo("Успех", f"Сохранено ответов: {len(items)}")
        self._on_clear()