"""Доводка схемы SQLite при старте: create_all не добавляет колонки в существующие таблицы."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from scr.constants import OLD_SETTING_TEMPLATE_FOLDER, SETTING_TEMPLATE_FOLDER

logger = logging.getLogger(__name__)

# (таблица, колонка, DDL-тип) — добавляются, если отсутствуют
ADD_COLUMNS = [
    ("module_types_calc", "fot_item_id", "INTEGER"),
    ("module_types_calc", "overhead_item_id", "INTEGER"),
    ("modules", "nom_tok", "INTEGER NOT NULL DEFAULT 0"),
    ("modules", "nom_tok_manual", "BOOLEAN NOT NULL DEFAULT 0"),
    ("request_calcs", "quantity", "INTEGER NOT NULL DEFAULT 1"),
    ("request_calcs", "works_cost", "NUMERIC(12, 2) NOT NULL DEFAULT 0"),
    ("modules", "material_type_id", "INTEGER REFERENCES material_types(id) ON DELETE SET NULL"),
    ("module_type_defaults", "slot_id", "INTEGER REFERENCES module_type_slots(id) ON DELETE SET NULL"),
    ("request_calc_items", "slot_id", "INTEGER REFERENCES module_type_slots(id) ON DELETE SET NULL"),
    ("materials", "unit", "VARCHAR(20) NOT NULL DEFAULT 'шт'"),
    ("materials", "accuracy_class", "VARCHAR(20)"),
    ("request_calcs", "qty_1sh", "INTEGER NOT NULL DEFAULT 0"),
    ("request_calcs", "qty_2sh", "INTEGER NOT NULL DEFAULT 0"),
    ("request_calcs", "purpose", "VARCHAR(20)"),
    ("material_types", "color", "VARCHAR(20)"),
    ("module_type_slots", "filters", "VARCHAR(200)"),
    ("module_type_defaults", "template_id", "INTEGER REFERENCES module_type_templates(id) ON DELETE CASCADE"),
    ("request_calcs", "name", "VARCHAR(200)"),
    ("requests", "power_transformer_cost", "NUMERIC(12, 2) DEFAULT 0"),
    ("requests", "mounting_cost", "NUMERIC(12, 2) DEFAULT 0"),
    ("request_calcs", "template_id", "INTEGER REFERENCES module_type_templates(id) ON DELETE SET NULL"),
    ("organizations", "full_name", "VARCHAR(300)"),
    ("organizations", "basis", "VARCHAR(200)"),
    ("organizations", "requisites", "TEXT"),
    ("contract_specs", "specification_date", "DATETIME"),
    ("module_type_slots", "color", "VARCHAR(20)"),
    ("request_calcs", "fot_manual", "BOOLEAN NOT NULL DEFAULT 1"),
    ("request_calcs", "overhead_manual", "BOOLEAN NOT NULL DEFAULT 1"),
    ("request_calcs", "sort_order", "INTEGER NOT NULL DEFAULT 0"),
    ("module_type_slots", "join_prev", "BOOLEAN NOT NULL DEFAULT 0"),
    ("request_calcs", "slot_copies", "TEXT"),
    ("module_type_templates", "slot_copies", "TEXT"),
    ("request_calc_items", "copy_no", "INTEGER NOT NULL DEFAULT 0"),
    ("module_type_defaults", "copy_no", "INTEGER NOT NULL DEFAULT 0"),
]

# Существующие блоки КСО: всё количество — на 1СШ
FILL_KSO_QTY_1SH = """
UPDATE request_calcs SET qty_1sh = quantity
WHERE module_type_id IN (SELECT id FROM module_types_calc WHERE slug = 'kso')
"""

# Таблицы с устаревшими UNIQUE-ограничениями: SQLite не умеет их удалять — таблица пересоздаётся по модели
REBUILD_IF_CONSTRAINT = [
    ("module_type_defaults", "uq_modtype_default_module"),
    # Модуль по умолчанию — один на строку в каждом шаблоне, а не на строку вообще
    ("module_type_defaults", "uq_modtype_default_slot UNIQUE"),
    ("request_calc_items", "uq_calc_item_module"),
    # Копии блоков строк в расчёте и шаблоне: уникальность — с номером копии
    ("request_calc_items", "uq_calc_item_slot UNIQUE"),
    ("module_type_defaults", "uq_modtype_default_tpl_slot UNIQUE"),
]

# Тип модуля по умолчанию — общий тип материалов его состава (если тип один)
FILL_MODULE_MATERIAL_TYPE = """
UPDATE modules SET material_type_id = (
    SELECT MIN(m.type_id) FROM module_items mi JOIN materials m ON m.id = mi.material_id
    WHERE mi.module_id = modules.id
)
WHERE material_type_id IS NULL AND (
    SELECT COUNT(DISTINCT m.type_id) FROM module_items mi JOIN materials m ON m.id = mi.material_id
    WHERE mi.module_id = modules.id AND m.type_id IS NOT NULL
) = 1
"""

# Настройка tkp_template_folder переименована в template_folder (папка всех шаблонов)
RENAME_SETTINGS = [(OLD_SETTING_TEMPLATE_FOLDER, SETTING_TEMPLATE_FOLDER)]

# Устаревшие колонки, которых нет в модели. NOT NULL без DEFAULT ломает INSERT — удаляем.
DROP_COLUMNS = [
    ("module_types_calc", "default_fot"),
    ("module_types_calc", "default_overhead"),
]


async def _columns(conn: AsyncConnection, table: str) -> set[str]:
    result = await conn.execute(text(f"PRAGMA table_info({table})"))
    return {row[1] for row in result.fetchall()}


async def _rebuild_table(conn: AsyncConnection, table: str) -> None:
    """Пересоздаёт таблицу по текущей модели, сохраняя данные общих колонок."""
    from scr.dbase.models import Base

    old = f"{table}_old"
    old_columns = await _columns(conn, table)
    await conn.execute(text(f"ALTER TABLE {table} RENAME TO {old}"))
    await conn.run_sync(lambda sync_conn: Base.metadata.tables[table].create(sync_conn))
    common = ", ".join(sorted(old_columns & await _columns(conn, table)))
    await conn.execute(text(f"INSERT INTO {table} ({common}) SELECT {common} FROM {old}"))
    await conn.execute(text(f"DROP TABLE {old}"))


async def run_startup_migrations(conn: AsyncConnection) -> None:
    for table, constraint in REBUILD_IF_CONSTRAINT:
        result = await conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = :t"), {"t": table}
        )
        sql = result.scalar_one_or_none() or ""
        if constraint in sql:
            await _rebuild_table(conn, table)
            logger.info("Пересоздана таблица %s (снято ограничение %s)", table, constraint)
    for table, column, ddl in ADD_COLUMNS:
        if column not in await _columns(conn, table):
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
            logger.info("Добавлена колонка %s.%s", table, column)
            if (table, column) == ("modules", "material_type_id"):
                await conn.execute(text(FILL_MODULE_MATERIAL_TYPE))
            if (table, column) == ("request_calcs", "qty_1sh"):
                await conn.execute(text(FILL_KSO_QTY_1SH))
    for old_key, new_key in RENAME_SETTINGS:
        old = await conn.execute(text("SELECT value FROM settings WHERE key = :k"), {"k": old_key})
        old_value = old.scalar_one_or_none()
        if old_value is None:
            continue
        new = await conn.execute(text("SELECT value FROM settings WHERE key = :k"), {"k": new_key})
        new_value = new.scalar_one_or_none()
        if new_value is None:
            await conn.execute(
                text("INSERT INTO settings (key, value) VALUES (:k, :v)"), {"k": new_key, "v": old_value}
            )
        elif not new_value and old_value:
            await conn.execute(text("UPDATE settings SET value = :v WHERE key = :k"), {"k": new_key, "v": old_value})
        await conn.execute(text("DELETE FROM settings WHERE key = :k"), {"k": old_key})
        logger.info("Настройка %s переименована в %s", old_key, new_key)
    for table, column in DROP_COLUMNS:
        if column in await _columns(conn, table):
            try:
                await conn.execute(text(f"ALTER TABLE {table} DROP COLUMN {column}"))
                logger.info("Удалена устаревшая колонка %s.%s", table, column)
            except Exception:
                logger.exception("Не удалось удалить колонку %s.%s", table, column)
