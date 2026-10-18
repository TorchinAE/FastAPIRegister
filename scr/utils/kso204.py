"""Расчёт КСО ↔ книга КСО204.xlsx (опросный лист, сводная информация, расчёт).

Блок расчёта N (1..10) — столбец N листа «КСО-204» (D..M), строка N «Сводной информации» (3..12)
и пара столбцов N листа «расчет» (C, E, G, ... U — цены, рентабельность, накладные, ФОТ).
Модули обязательных строк блока пишутся в строки «КСО-204» по названию строки (названия — как в «Прайсах»),
остальные модули — в строки «Дополнительно» (кол-во / оборудование).
"""

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

from scr.constants import DEFAULT_K_FOT, DEFAULT_K_NAKL
from scr.utils.xlsx_patch import Formula, XlsxPatcher

TEMPLATE_PATH = Path(__file__).resolve().parent.parent.parent / "xlsx_templates" / "КСО204.xlsx"

SHEET_KSO = "КСО-204"
SHEET_SUMMARY = "Сводная информация"
SHEET_CALC = "расчет"

MAX_BLOCKS = 10
KSO_COLS = "DEFGHIJKLM"  # «КСО-204»: столбец блока
CALC_COLS = ("C", "E", "G", "I", "K", "M", "O", "Q", "S", "U")  # «расчет»: столбец цены блока
SUMMARY_FIRST_ROW = 3  # «Сводная информация»: C — кол-во (= K + L), K — 1СШ, L — 2СШ

ROW_PURPOSE = 15  # Назначение камер
ROW_SCHEME = 10  # Номер схемы главных цепей (КСО-204 — по нему ищутся корпус, ФОТ и накладные)
ROW_TT_QTY = 21  # Трансформатор тока: кол-во
ROW_TT = 22  # Трансформатор тока: коэф. транс. (модуль)
EXTRA_ROWS = ((32, 33), (34, 35), (36, 37), (38, 39), (40, 41), (42, 43))  # Дополнительно: кол-во, оборудование
CALC_ROW_PROFIT = 33  # рентабельность блока (доля: 0.15 = 15%)
CALC_ROW_K_NAKL = 40  # «Кнакладные» — коэффициент накладных
CALC_ROW_K_FOT = 41  # «КФОТ» — коэффициент ФОТ
CALC_ROW_OVERHEAD = 42  # «Накладные … макс»
CALC_ROW_FOT = 43  # «ФОТ … макс»
SCHEME = "КСО-204"


def _norm(name: str) -> str:
    return re.sub(r"[\s.\-_]", "", str(name or "").lower().replace("ё", "е"))


# Название обязательной строки расчёта (как в «Прайсах» или на листе «КСО-204») → строка листа «КСО-204»
_SLOT_ROWS: dict[str, int] = {}
for _row, _names in {
    17: ("Шинный разъединитель", "ШР", "Разъединитель", "РВЗ", "РВФЗ"),
    18: ("Выключатель", "Выкл", "Вакуумник", "ВВ"),
    19: ("Блок управления", "БУ"),
    20: ("МПЗ", "Микропроцессорные реле", "Реле"),
    ROW_TT: ("Трансформатор тока", "ТТ", "ТПОЛ", "ТОЛ"),
    23: ("Линейный разъединитель", "ЛР"),
    24: ("Счетчик", "Счетчик учета ЭЭ", "Счетчик10"),
    25: ("ТН", "Трансформатор напряжения"),
    26: ("ТСН", "Трансформатор собственных нужд"),
    27: ("ПТ", "Предохранитель"),
    28: ("ОПН",),
    29: ("Блокировка", "Элементы электромагнитной блокировки", "ВП-19"),
    30: ("ЗБ-1М",),
    31: (
        "ТТНП",
        "ТТ нулевой последовательности",
        "Трансформатор тока нулевой последовательности",
        "ТТнулевойпоследлвательности",
    ),
    44: ("Кабель",),
}.items():
    for _name in _names:
        _SLOT_ROWS[_norm(_name)] = _row


def slot_row(slot_name: str) -> int | None:
    """Строка листа «КСО-204» для обязательной строки расчёта; None — пишется в «Дополнительно»."""
    return _SLOT_ROWS.get(_norm(slot_name))


@dataclass
class KsoHeader:
    tkp_num: str = ""
    issue_date: date | None = None
    object_name: str = ""
    company: str = ""
    contact: str = ""
    phone: str = ""
    # Номинальный ток сборных шин (C12) — максимальный ном. ток модулей; None — как в шаблоне
    bus_current: int | None = None
    k_fot: float = DEFAULT_K_FOT
    k_nakl: float = DEFAULT_K_NAKL


@dataclass
class KsoBlock:
    qty_1sh: int = 1
    qty_2sh: int = 0
    profit_percent: float = 0.0
    fot: float = 0.0
    overhead: float = 0.0
    purpose: str = ""
    # (название обязательной строки, модуль, кол-во)
    slots: list[tuple[str, str, int]] = field(default_factory=list)
    # (модуль, кол-во) — модули, добавленные вручную
    extras: list[tuple[str, int]] = field(default_factory=list)


def build_kso204(header: KsoHeader, blocks: list[KsoBlock], template: bytes | None = None) -> tuple[bytes, list[str]]:
    """Заполняет шаблон КСО204. Возвращает (xlsx, предупреждения)."""
    if len(blocks) > MAX_BLOCKS:
        raise ValueError(f"В КСО204 помещается не больше {MAX_BLOCKS} блоков, в расчёте — {len(blocks)}")
    book = XlsxPatcher(template if template is not None else TEMPLATE_PATH.read_bytes())
    warnings: list[str] = []

    kso: dict[str, object] = {
        "I1": header.tkp_num or None,
        "K1": header.issue_date or date.today(),
        "D2": header.object_name or None,
        "D3": header.company or None,
        "F5": header.contact or None,
        "K5": header.phone or None,
    }
    if header.bus_current:
        kso["C12"] = header.bus_current
    summary: dict[str, object] = {"K2": "1СШ", "L2": "2СШ"}
    calc: dict[str, object] = {}
    used_rows = sorted({ROW_PURPOSE, ROW_SCHEME, ROW_TT_QTY, *_SLOT_ROWS.values(), *sum(EXTRA_ROWS, ())})

    for i in range(MAX_BLOCKS):
        col, calc_col, srow = KSO_COLS[i], CALC_COLS[i], SUMMARY_FIRST_ROW + i
        values: dict[int, object] = dict.fromkeys(used_rows)
        block = blocks[i] if i < len(blocks) else None
        summary[f"C{srow}"] = Formula(f"K{srow}+L{srow}")
        if block is None:
            summary.update({f"K{srow}": None, f"L{srow}": None})
            calc.update(
                dict.fromkeys(
                    f"{calc_col}{r}" for r in (CALC_ROW_PROFIT, CALC_ROW_K_NAKL, CALC_ROW_K_FOT, CALC_ROW_OVERHEAD,
                                               CALC_ROW_FOT)
                )
            )  # fmt: skip
        else:
            values[ROW_PURPOSE] = block.purpose or f"Блок {i + 1}"
            values[ROW_SCHEME] = SCHEME
            extras = list(block.extras)
            for slot_name, module_name, qty in block.slots:
                row = slot_row(slot_name)
                if row == ROW_TT:
                    if values[ROW_TT] is None:
                        values[ROW_TT], values[ROW_TT_QTY] = module_name, qty
                        continue
                elif row is not None and values[row] is None and qty == 1:
                    values[row] = module_name
                    continue
                # Строка не сопоставлена, уже занята или модулей несколько — в «Дополнительно»
                extras.append((module_name, qty))
            if len(extras) > len(EXTRA_ROWS):
                dropped = ", ".join(name for name, _ in extras[len(EXTRA_ROWS) :])
                warnings.append(
                    f"Блок {i + 1}: в «Дополнительно» помещается {len(EXTRA_ROWS)} строк, не вошли: {dropped}"
                )
            for (qty_row, name_row), (name, qty) in zip(EXTRA_ROWS, extras, strict=False):
                values[qty_row], values[name_row] = qty, name
            summary.update({f"K{srow}": block.qty_1sh, f"L{srow}": block.qty_2sh})
            calc.update({
                f"{calc_col}{CALC_ROW_PROFIT}": round(block.profit_percent / 100, 6),
                f"{calc_col}{CALC_ROW_K_NAKL}": header.k_nakl,
                f"{calc_col}{CALC_ROW_K_FOT}": header.k_fot,
                f"{calc_col}{CALC_ROW_OVERHEAD}": round(block.overhead, 2),
                f"{calc_col}{CALC_ROW_FOT}": round(block.fot, 2),
            })  # fmt: skip
        kso.update({f"{col}{row}": value for row, value in values.items()})

    book.set(SHEET_KSO, kso)
    book.set(SHEET_SUMMARY, summary)
    book.set(SHEET_CALC, calc)
    return book.save(), warnings


@dataclass
class ParsedBlock:
    index: int
    qty_1sh: int
    qty_2sh: int
    profit_percent: float | None
    fot: float
    overhead: float
    purpose: str
    rows: dict[int, str]  # строка «КСО-204» → модуль
    tt_qty: int
    extras: list[tuple[str, int]]


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    return "" if text.startswith("=") else text


def _num(value, default: float = 0.0) -> float:
    if value is None or (isinstance(value, str) and (not value.strip() or value.startswith("="))):
        return default
    try:
        return float(str(value).replace(" ", "").replace("\xa0", "").replace(",", "."))
    except ValueError:
        return default


def parse_kso204(data: bytes) -> list[ParsedBlock]:
    """Блоки расчёта из книги КСО204: заполненные столбцы листа «КСО-204» (по «Назначению камер» или модулям)."""
    wb = load_workbook(io.BytesIO(data))
    kso, summary, calc = wb[SHEET_KSO], wb[SHEET_SUMMARY], wb[SHEET_CALC]
    default_profit = calc["A33"].value
    module_rows = sorted(set(_SLOT_ROWS.values()))
    blocks: list[ParsedBlock] = []
    for i in range(MAX_BLOCKS):
        col, calc_col, srow = KSO_COLS[i], CALC_COLS[i], SUMMARY_FIRST_ROW + i
        purpose = _text(kso[f"{col}{ROW_PURPOSE}"].value)
        rows = {r: _text(kso[f"{col}{r}"].value) for r in module_rows}
        rows = {r: name for r, name in rows.items() if name}
        extras = []
        for qty_row, name_row in EXTRA_ROWS:
            name = _text(kso[f"{col}{name_row}"].value)
            if name:
                extras.append((name, max(1, int(_num(kso[f"{col}{qty_row}"].value, 1)))))
        if not purpose and not rows and not extras:
            continue
        total = int(_num(summary[f"C{srow}"].value, 1))
        q1_raw, q2_raw = summary[f"K{srow}"].value, summary[f"L{srow}"].value
        if q1_raw is None and q2_raw is None:
            qty_1sh, qty_2sh = total, 0
        else:
            qty_1sh, qty_2sh = int(_num(q1_raw)), int(_num(q2_raw))
        profit_raw = calc[f"{calc_col}{CALC_ROW_PROFIT}"].value
        if isinstance(profit_raw, str) and profit_raw.replace(" ", "") == "=$A$33":
            profit_raw = default_profit
        profit = _num(profit_raw, -1)
        blocks.append(
            ParsedBlock(
                index=i + 1,
                qty_1sh=qty_1sh,
                qty_2sh=qty_2sh,
                profit_percent=round(profit * 100, 4) if profit >= 0 else None,
                fot=_num(calc[f"{calc_col}{CALC_ROW_FOT}"].value),
                overhead=_num(calc[f"{calc_col}{CALC_ROW_OVERHEAD}"].value),
                purpose=purpose,
                rows=rows,
                tt_qty=max(1, int(_num(kso[f"{col}{ROW_TT_QTY}"].value, 1))),
                extras=extras,
            )
        )
    return blocks


def kso204_filename(tkp_num: str) -> str:
    safe = re.sub(r'[\\/:*?"<>|\s]', "_", tkp_num or "")
    return f"КСО204-ткп{safe}.xlsx"


# ── Варианты расчёта: номер ТКП «8-ив» → вариант 1, «8-2ив» → вариант 2, ... ──

_TKP_RE = re.compile(r"^(?P<id>\d+)-(?P<n>\d*)(?P<city>\D.*)?$")


def split_tkp_num(tkp_num: str) -> tuple[str, int, str] | None:
    """«8-2ив» → ("8", 2, "ив"); «8-ив» → ("8", 1, "ив"); не по шаблону → None."""
    m = _TKP_RE.match((tkp_num or "").strip())
    if not m:
        return None
    return m.group("id"), int(m.group("n") or 1), m.group("city") or ""


def variant_tkp_num(base_id: str, n: int, city: str) -> str:
    return f"{base_id}-{city}" if n == 1 else f"{base_id}-{n}{city}"


def list_variant_files(folder: Path, base_id: str) -> dict[int, Path]:
    """Файлы вариантов КСО204 этой ТКП в папке: {номер варианта: путь}."""
    result: dict[int, Path] = {}
    if not folder.is_dir():
        return result
    prefix = f"КСО204-ткп{base_id}-"
    for path in folder.iterdir():
        if path.is_file() and path.name.startswith(prefix) and path.suffix.lower() == ".xlsx":
            parsed = split_tkp_num(f"{base_id}-{path.stem[len(prefix) :]}")
            if parsed:
                result[parsed[1]] = path
    return dict(sorted(result.items()))


def to_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else None
