"""Шаблоны документов (КСО204, ТКП, договор, спецификация).

Файл берётся из папки шаблонов (настройка template_folder), если он там есть, иначе — встроенный
из xlsx_templates/ проекта.
"""

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from scr.constants import SETTING_TEMPLATE_FOLDER

BUILTIN_DIR = Path(__file__).resolve().parent.parent.parent / "xlsx_templates"


def template_path(folder: str, filename: str) -> Path:
    """Шаблон из папки шаблонов, если файл там есть, иначе встроенный."""
    if folder:
        custom = Path(folder) / filename
        try:
            if custom.is_file():
                return custom
        except OSError:
            pass
    return BUILTIN_DIR / filename


async def read_template(session: AsyncSession, filename: str) -> bytes:
    from scr.dbase import crud_settings

    folder = await crud_settings.get_setting(session, SETTING_TEMPLATE_FOLDER) or ""
    return template_path(folder, filename).read_bytes()
