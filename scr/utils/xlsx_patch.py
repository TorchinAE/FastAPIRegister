"""Запись значений в ячейки готового xlsx без пересохранения книги через openpyxl.

openpyxl при сохранении теряет сводные таблицы, подключения к данным, картинки и часть оформления,
поэтому значения пишутся прямо в XML листов внутри zip-архива, остальные части книги не меняются.
"""

import io
import re
import zipfile
from datetime import date, datetime
from xml.sax.saxutils import escape


class Formula(str):
    """Значение ячейки — формула (без ведущего «=»)."""


_SHEET_RE = re.compile(r'<sheet\b[^>]*\bname="([^"]+)"[^>]*\br:id="([^"]+)"')
_REL_RE = re.compile(r'<Relationship\b[^>]*\bId="([^"]+)"[^>]*\bTarget="([^"]+)"')
_ROW_RE = re.compile(r'<row\b[^>]*?\br="(\d+)"[^>]*?(?:/>|>.*?</row>)', re.DOTALL)
_CELL_RE = re.compile(r'<c\b[^>]*?\br="([A-Z]+)(\d+)"[^>]*?(?:/>|>.*?</c>)', re.DOTALL)
_STYLE_RE = re.compile(r'\bs="(\d+)"')
_REF_RE = re.compile(r"^([A-Z]+)(\d+)$")


def _col_index(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + ord(ch) - 64
    return n


def _excel_serial(value: date | datetime) -> float:
    if isinstance(value, datetime):
        delta = value.replace(tzinfo=None) - datetime(1899, 12, 30)  # noqa: DTZ001 — эпоха Excel без пояса
        return delta.days + delta.seconds / 86400
    return float((value - date(1899, 12, 30)).days)


def _cell_xml(ref: str, style: str | None, value) -> str:
    attrs = f'r="{ref}"' + (f' s="{style}"' if style else "")
    if value is None or value == "":
        return f"<c {attrs}/>"
    if isinstance(value, Formula):
        return f"<c {attrs}><f>{escape(str(value))}</f></c>"
    if isinstance(value, bool):
        return f'<c {attrs} t="b"><v>{int(value)}</v></c>'
    if isinstance(value, date | datetime):
        value = _excel_serial(value)
    if isinstance(value, int | float):
        return f"<c {attrs}><v>{value!r}</v></c>"
    text = escape(str(value))
    space = ' xml:space="preserve"' if text != text.strip() or "\n" in text else ""
    return f'<c {attrs} t="inlineStr"><is><t{space}>{text}</t></is></c>'


def _set_in_row(row_xml: str, ref: str, value) -> str:
    """Заменяет или вставляет (по порядку столбцов) ячейку в XML строки."""
    col = _REF_RE.match(ref).group(1)
    target = _col_index(col)
    for m in _CELL_RE.finditer(row_xml):
        idx = _col_index(m.group(1))
        if idx == target:
            style = _STYLE_RE.search(m.group(0)[: m.group(0).find(">")])
            new = _cell_xml(ref, style.group(1) if style else None, value)
            return row_xml[: m.start()] + new + row_xml[m.end() :]
        if idx > target:
            return row_xml[: m.start()] + _cell_xml(ref, None, value) + row_xml[m.start() :]
    new = _cell_xml(ref, None, value)
    if row_xml.endswith("/>"):
        return row_xml[:-2] + ">" + new + "</row>"
    return row_xml[: -len("</row>")] + new + "</row>"


def set_cells(sheet_xml: str, values: dict[str, object]) -> str:
    """Записывает значения {"D15": "Линия", ...} в XML листа; None — очистить значение (стиль остаётся)."""
    by_row: dict[int, dict[str, object]] = {}
    for ref, value in values.items():
        m = _REF_RE.match(ref)
        if not m:
            raise ValueError(f"Неверный адрес ячейки: {ref}")
        by_row.setdefault(int(m.group(2)), {})[ref] = value

    start = sheet_xml.index("<sheetData")
    end = sheet_xml.index("</sheetData>") if "</sheetData>" in sheet_xml else None
    head_end = sheet_xml.index(">", start) + 1
    if end is None:  # <sheetData/>
        head, body, tail = sheet_xml[:start] + "<sheetData>", "", sheet_xml[head_end:]
        tail = "</sheetData>" + tail
    else:
        head, body, tail = sheet_xml[:head_end], sheet_xml[head_end:end], sheet_xml[end:]

    for row_num in sorted(by_row):
        rows = list(_ROW_RE.finditer(body))
        match = next((m for m in rows if int(m.group(1)) == row_num), None)
        if match:
            row_xml = match.group(0)
            for ref, value in by_row[row_num].items():
                row_xml = _set_in_row(row_xml, ref, value)
            body = body[: match.start()] + row_xml + body[match.end() :]
            continue
        row_xml = f'<row r="{row_num}"/>'
        for ref, value in by_row[row_num].items():
            row_xml = _set_in_row(row_xml, ref, value)
        after = next((m for m in rows if int(m.group(1)) > row_num), None)
        pos = after.start() if after else len(body)
        body = body[:pos] + row_xml + body[pos:]
    return head + body + tail


class XlsxPatcher:
    """Книга xlsx в памяти: set(лист, {ячейка: значение}) → save() байты с пересчётом формул при открытии."""

    def __init__(self, data: bytes):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self._infos = z.infolist()
            self._parts = {i.filename: z.read(i.filename) for i in self._infos}
        workbook = self._parts["xl/workbook.xml"].decode("utf-8")
        rels = dict(_REL_RE.findall(self._parts["xl/_rels/workbook.xml.rels"].decode("utf-8")))
        self.sheets: dict[str, str] = {}
        for name, rid in _SHEET_RE.findall(workbook):
            target = rels[rid].lstrip("/")
            self.sheets[_unescape(name)] = target if target.startswith("xl/") else "xl/" + target

    def set(self, sheet: str, values: dict[str, object]) -> None:
        path = self.sheets[sheet]
        self._parts[path] = set_cells(self._parts[path].decode("utf-8"), values).encode("utf-8")

    def save(self) -> bytes:
        parts = dict(self._parts)
        # Цепочка вычислений ссылается на ячейки с формулами; после замены формул значениями она неверна —
        # удаляем, Excel построит её заново. Формулы пересчитываются при открытии книги.
        parts.pop("xl/calcChain.xml", None)
        rels = parts["xl/_rels/workbook.xml.rels"].decode("utf-8")
        rels = re.sub(r'<Relationship\b[^>]*Target="/?(?:xl/)?calcChain\.xml"[^>]*/>', "", rels)
        parts["xl/_rels/workbook.xml.rels"] = rels.encode("utf-8")
        types = parts["[Content_Types].xml"].decode("utf-8")
        types = re.sub(r'<Override\b[^>]*PartName="/xl/calcChain\.xml"[^>]*/>', "", types)
        parts["[Content_Types].xml"] = types.encode("utf-8")
        workbook = parts["xl/workbook.xml"].decode("utf-8")
        if "fullCalcOnLoad" not in workbook:
            if "<calcPr" in workbook:
                workbook = workbook.replace("<calcPr", '<calcPr fullCalcOnLoad="1"', 1)
            else:
                workbook = workbook.replace("</workbook>", '<calcPr fullCalcOnLoad="1"/></workbook>')
        parts["xl/workbook.xml"] = workbook.encode("utf-8")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for info in self._infos:
                if info.filename in parts:
                    z.writestr(info.filename, parts[info.filename])
        return buf.getvalue()


def _unescape(text: str) -> str:
    return (
        text.replace("&quot;", '"')
        .replace("&apos;", "'")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
    )
