# src/tree_tab.py
# Вкладка "Дерево ролей" (режим чтения).
#
# Состояние "свёрнуто/развёрнуто" хранится в preferences (roles_tree_state)
# и общее для всех вкладок с деревом ролей.

import tkinter as tk
from tkinter import ttk
from .roles_repo import RolesRepository
from .sub_roles_repo import SubRolesRepository
from .preferences_repo import PreferencesRepository


class TreeRolesTab(tk.Frame):
    def __init__(self, parent, roles_repo: RolesRepository, sub_roles_repo: SubRolesRepository,
                 prefs_repo: PreferencesRepository):
        super().__init__(parent)
        self.roles_repo = roles_repo
        self.sub_roles_repo = sub_roles_repo
        self.prefs_repo = prefs_repo

        frame_buttons = tk.Frame(self)
        frame_buttons.pack(pady=5, padx=10, fill="x")

        self.btn_expand = tk.Button(frame_buttons, text="Развернуть всё", command=self.expand_all)
        self.btn_expand.pack(side="left", padx=5)

        self.btn_collapse = tk.Button(frame_buttons, text="Свернуть всё", command=self.collapse_all)
        self.btn_collapse.pack(side="left", padx=5)

        self.btn_refresh = tk.Button(frame_buttons, text="Обновить", command=self.refresh_tree)
        self.btn_refresh.pack(side="left", padx=5)

        lbl_hint = tk.Label(frame_buttons, text="(Только для просмотра)", fg="gray")
        lbl_hint.pack(side="right", padx=5)

        self.tree = ttk.Treeview(self, columns=("desc",), selectmode="browse")
        self.tree.heading("#0", text="Роль / Под-роль")
        self.tree.heading("desc", text="Описание")

        self.tree.column("#0", width=300)
        self.tree.column("desc", width=400)

        self.tree.tag_configure("role_node", font=("Arial", 11, "bold"))
        self.tree.tag_configure("sub_role_node", font=("Arial", 10, "normal"))

        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        # Сохраняем состояние ролей при сворачивании/разворачивании
        self.tree.bind("<<TreeviewOpen>>", self._on_node_toggled)
        self.tree.bind("<<TreeviewClose>>", self._on_node_toggled)

        self.refresh_tree()

    def _get_state(self) -> dict:
        state = self.prefs_repo.get("roles_tree_state")
        if not isinstance(state, dict):
            state = {}
        return state

    def _save_state(self, state: dict):
        self.prefs_repo.set("roles_tree_state", state)

    def _on_node_toggled(self, event=None):
        """Сохраняет текущее состояние всех ролей в preferences."""
        state = self._get_state()
        for role in self.roles_repo.get_all():
            role_id = role[0]
            iid = f"role_{role_id}"
            if self.tree.exists(iid):
                state[str(role_id)] = bool(self.tree.item(iid, "open"))
        self._save_state(state)

    def refresh_tree(self):
        state = self._get_state()

        for item in self.tree.get_children():
            self.tree.delete(item)

        # Корень «Все роли» — как на вкладке «Связи ролей»
        self.tree.insert(
            "", "end", iid="root", text="📁 Все роли",
            tags=("role_node",),
            open=True,
        )

        roles = sorted(self.roles_repo.get_all(), key=lambda r: r[0])

        for role in roles:
            role_id, name, desc, color = role[0], role[1], role[2], role[3]
            desc = desc or ""
            color = color or "#FFFFFF"

            role_iid = f"role_{role_id}"
            # По умолчанию развёрнуто
            is_open = state.get(str(role_id), True)
            role_text = f"{role_id}. {name}"

            tag_color = f"color_{role_id}"
            self.tree.tag_configure(tag_color, background=color)

            self.tree.insert("root", "end", iid=role_iid, text=role_text, values=(desc,),
                             open=is_open, tags=("role_node", tag_color))

            sub_roles = sorted(self.sub_roles_repo.get_by_parent(role_id), key=lambda sr: sr[0])
            for sr in sub_roles:
                sr_id, sr_name, sr_desc = sr[0], sr[1], sr[2]
                sr_desc = sr_desc or ""
                sub_iid = f"sub_{sr_id}"

                self.tree.insert(role_iid, "end", iid=sub_iid, text=sr_name, values=(sr_desc,),
                                 tags=("sub_role_node", tag_color))

    def expand_all(self):
        """Разворачивает все роли и записывает состояние (все True)."""
        roles = self.roles_repo.get_all()
        state = {str(r[0]): True for r in roles}
        self._save_state(state)
        if self.tree.exists("root"):
            self.tree.item("root", open=True)
        for item in self.tree.get_children("root"):
            if item.startswith("role_"):
                self.tree.item(item, open=True)

    def collapse_all(self):
        """Сворачивает все роли и записывает состояние (все False)."""
        roles = self.roles_repo.get_all()
        state = {str(r[0]): False for r in roles}
        self._save_state(state)
        if self.tree.exists("root"):
            self.tree.item("root", open=False)