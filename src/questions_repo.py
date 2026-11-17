# src/questions_repo.py
# Репозиторий для подсистемы субъективных оценок:
# questions, question_options, answers.

import sqlite3

from . import datetime_utils
from .database import Database


class QuestionsRepository:
    def __init__(self, db: Database):
        self.db = db

    # =========================================================================
    # ВОПРОСЫ (questions)
    # =========================================================================
    def get_all(self) -> list[tuple]:
        """(id, text, role_id, sub_role_id). Сортировка по id."""
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT id, text, role_id, sub_role_id FROM questions ORDER BY id"
            ).fetchall()
        finally:
            conn.close()

    def get_filtered(self, role_id: int | None = None,
                     sub_role_id: int | None = None,
                     include_common: bool = False) -> list[tuple]:
        """Фильтр вопросов по роли/подроли.

        - role_id=None, sub_role_id=None → все вопросы.
        - sub_role_id задан → вопросы этой подроли (role_id = parent).
        - role_id задан → вопросы этой роли + её подролей.
        - include_common=True → добавить «общие» (role_id IS NULL AND sub_role_id IS NULL).
        """
        conn = self.db.connect()
        try:
            if sub_role_id is not None:
                cond = "sub_role_id = :sid"
                params = {"sid": sub_role_id}
                if include_common:
                    cond = "(sub_role_id = :sid OR (role_id IS NULL AND sub_role_id IS NULL))"
                return conn.execute(
                    f"SELECT id, text, role_id, sub_role_id FROM questions "
                    f"WHERE {cond} ORDER BY id",
                    params
                ).fetchall()

            if role_id is not None:
                cond = (
                    "role_id = :rid OR sub_role_id IN "
                    "(SELECT id FROM sub_roles WHERE parent_role_id = :rid)"
                )
                if include_common:
                    cond = f"({cond} OR (role_id IS NULL AND sub_role_id IS NULL))"
                return conn.execute(
                    f"SELECT id, text, role_id, sub_role_id FROM questions "
                    f"WHERE {cond} ORDER BY id",
                    {"rid": role_id}
                ).fetchall()

            return self.get_all()
        finally:
            conn.close()

    def get_by_id(self, qid: int) -> tuple | None:
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT id, text, role_id, sub_role_id FROM questions WHERE id = :id",
                {"id": qid}
            ).fetchone()
        finally:
            conn.close()

    def add(self, text: str, role_id: int | None = None, sub_role_id: int | None = None) -> int:
        conn = self.db.connect()
        try:
            now = datetime_utils.get_now_iso()
            cur = conn.execute(
                "INSERT INTO questions (text, role_id, sub_role_id, created_at) "
                "VALUES (:t, :r, :s, :n)",
                {"t": text, "r": role_id, "s": sub_role_id, "n": now}
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def update(self, qid: int, text: str,
               role_id: int | None, sub_role_id: int | None):
        conn = self.db.connect()
        try:
            conn.execute(
                "UPDATE questions SET text = :t, role_id = :r, sub_role_id = :s "
                "WHERE id = :id",
                {"id": qid, "t": text, "r": role_id, "s": sub_role_id}
            )
            conn.commit()
        finally:
            conn.close()

    def delete(self, qid: int):
        conn = self.db.connect()
        try:
            conn.execute("DELETE FROM questions WHERE id = :id", {"id": qid})
            conn.commit()
        finally:
            conn.close()

    def get_answers_count(self, qid: int) -> int:
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT COUNT(*) FROM answers WHERE question_id = :id",
                {"id": qid}
            ).fetchone()[0]
        finally:
            conn.close()

    # =========================================================================
    # ВАРИАНТЫ (question_options)
    # =========================================================================
    def get_options_for_question(self, qid: int) -> list[tuple]:
        """(id, question_id, value, description). Сортировка по value."""
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT id, question_id, value, description FROM question_options "
                "WHERE question_id = :qid ORDER BY value",
                {"qid": qid}
            ).fetchall()
        finally:
            conn.close()

    def get_option_by_id(self, oid: int) -> tuple | None:
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT id, question_id, value, description FROM question_options "
                "WHERE id = :id",
                {"id": oid}
            ).fetchone()
        finally:
            conn.close()

    def add_option(self, question_id: int, value: int, description: str):
        conn = self.db.connect()
        try:
            now = datetime_utils.get_now_iso()
            conn.execute(
                "INSERT INTO question_options (question_id, value, description, created_at) "
                "VALUES (:q, :v, :d, :n)",
                {"q": question_id, "v": value, "d": description, "n": now}
            )
            conn.commit()
        finally:
            conn.close()

    def update_option(self, oid: int, value: int, description: str):
        conn = self.db.connect()
        try:
            conn.execute(
                "UPDATE question_options SET value = :v, description = :d "
                "WHERE id = :id",
                {"id": oid, "v": value, "d": description}
            )
            conn.commit()
        finally:
            conn.close()

    def delete_option(self, oid: int):
        conn = self.db.connect()
        try:
            conn.execute("DELETE FROM question_options WHERE id = :id", {"id": oid})
            conn.commit()
        finally:
            conn.close()

    # =========================================================================
    # ОТВЕТЫ (answers)
    # =========================================================================
    def get_answers(self, question_ids: list[int] | None = None,
                    date_from: str | None = None,
                    date_to: str | None = None) -> list[tuple]:
        """(id, question_id, value, option_description, extra_comment, measured_at).

        question_ids=None → без фильтра по вопросам. Пустой список → пусто.
        date_from/date_to — ISO-строки (включительно).
        Сортировка: measured_at DESC, id DESC.
        """
        conn = self.db.connect()
        try:
            conds = []
            params: dict = {}
            if question_ids is not None:
                if not question_ids:
                    return []
                placeholders = ",".join(f":qid{i}" for i in range(len(question_ids)))
                conds.append(f"question_id IN ({placeholders})")
                for i, q in enumerate(question_ids):
                    params[f"qid{i}"] = q
            if date_from:
                conds.append("measured_at >= :df")
                params["df"] = date_from
            if date_to:
                conds.append("measured_at <= :dt")
                params["dt"] = date_to

            where = ""
            if conds:
                where = "WHERE " + " AND ".join(conds)

            return conn.execute(
                f"SELECT id, question_id, value, option_description, extra_comment, measured_at "
                f"FROM answers {where} ORDER BY measured_at DESC, id DESC",
                params
            ).fetchall()
        finally:
            conn.close()

    def get_answer_by_id(self, aid: int) -> tuple | None:
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT id, question_id, value, option_description, extra_comment, measured_at "
                "FROM answers WHERE id = :id",
                {"id": aid}
            ).fetchone()
        finally:
            conn.close()

    def add_answers_batch(self, items: list[dict], measured_at: str):
        """items: [{question_id, value, option_description, extra_comment}, ...]."""
        conn = self.db.connect()
        try:
            measured_at = datetime_utils.to_minute_iso(measured_at)
            now = datetime_utils.get_now_iso()
            conn.execute("BEGIN")
            for it in items:
                conn.execute(
                    "INSERT INTO answers "
                    "(question_id, value, option_description, extra_comment, measured_at, created_at) "
                    "VALUES (:q, :v, :od, :ec, :m, :n)",
                    {"q": it["question_id"], "v": it["value"],
                     "od": it["option_description"], "ec": it.get("extra_comment"),
                     "m": measured_at, "n": now}
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def update_answer(self, aid: int, value: int, option_description: str,
                      extra_comment: str | None, measured_at: str):
        conn = self.db.connect()
        try:
            measured_at = datetime_utils.to_minute_iso(measured_at)
            conn.execute(
                "UPDATE answers SET value = :v, option_description = :od, "
                "extra_comment = :ec, measured_at = :m WHERE id = :id",
                {"id": aid, "v": value, "od": option_description,
                 "ec": extra_comment, "m": measured_at}
            )
            conn.commit()
        finally:
            conn.close()

    def delete_answer(self, aid: int):
        conn = self.db.connect()
        try:
            conn.execute("DELETE FROM answers WHERE id = :id", {"id": aid})
            conn.commit()
        finally:
            conn.close()