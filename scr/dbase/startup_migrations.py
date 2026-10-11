"""Доводка схемы SQLite при старте: create_all не добавляет колонки в существующие таблицы."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

logger = logging.getLogger(__name__)

# (таблица, колонка, DDL-тип) — добавляются, если отсутствуют
ADD_COLUMNS = [
    ("module_types_calc", "fot_item_id", "INTEGER"),
    ("module_types_calc", "overhead_item_id", "INTEGER"),
    ("modules", "nom_tok", "INTEGER NOT NULL DEFAULT 0"),
    ("modules", "nom_tok_manual", "BOOLEAN NOT NULL DEFAULT 0"),
    ("request_calcs", "quantity", "INTEGER NOT NULL DEFAULT 1"),
    ("request_calcs", "works_cost", "NUMERIC(12, 2) NOT NULL DEFAULT 0"),
]

# Устаревшие колонки, которых нет в модели. NOT NULL без DEFAULT ломает INSERT — удаляем.
DROP_COLUMNS = [
    ("module_types_calc", "default_fot"),
    ("module_types_calc", "default_overhead"),
]


async def _columns(conn: AsyncConnection, table: str) -> set[str]:
    result = await conn.execute(text(f"PRAGMA table_info({table})"))
    return {row[1] for row in result.fetchall()}


async def run_startup_migrations(conn: AsyncConnection) -> None:
    for table, column, ddl in ADD_COLUMNS:
        if column not in await _columns(conn, table):
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
            logger.info("Добавлена колонка %s.%s", table, column)
    for table, column in DROP_COLUMNS:
        if column in await _columns(conn, table):
            try:
                await conn.execute(text(f"ALTER TABLE {table} DROP COLUMN {column}"))
                logger.info("Удалена устаревшая колонка %s.%s", table, column)
            except Exception:
                logger.exception("Не удалось удалить колонку %s.%s", table, column)
