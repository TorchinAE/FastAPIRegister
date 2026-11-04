"""Договор и спецификация в Word по шаблонам xlsx_templates/Contract.docx и Contract_specification.docx.

В шаблонах — метки в фигурных скобках ({номер договора}, {организация}, ...), см. CONTRACT_FIELDS / SPEC_FIELDS.
Метка может быть разбита Word на несколько фрагментов (runs) — заменяется по тексту абзаца,
оформление берётся от фрагмента, где метка начинается.

Метки-условия в начале абзаца: {если самовывоз} / {если доставка} — абзац остаётся только при выполнении условия;
{оплата 1} — абзац первого платежа, {оплата 2} — абзац для каждого следующего платежа.
Таблица спецификации: строка после заголовка — образец строки оборудования (остальные строки до «Итого» удаляются),
в строках итогов — {итого}, {ндс}, {сумма ндс}, {всего}.
"""

import io
import re
from copy import deepcopy
from dataclasses import dataclass, field

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table, _Row
from docx.text.paragraph import Paragraph

# Метки договора и спецификации (для справки на странице и в тестах)
CONTRACT_FIELDS = [
    "{номер договора}", "{дата договора}", "{следующий год}", "{организация}", "{организация полностью}",
    "{должность директора}", "{ФИО директора}", "{действующего}", "{основание}", "{реквизиты}",
    "{подпись директора}",
]  # fmt: skip
SPEC_FIELDS = [
    "{номер спецификации}", "{дата спецификации}", "{номер договора}", "{дата договора}", "{организация}",
    "{организация полностью}", "{должность директора}", "{ФИО директора}", "{действующего}", "{основание}",
    "{срок поставки}", "{процент}", "{сумма}", "{доп услуги}", "{адрес доставки}", "{итого}", "{ндс}",
    "{сумма ндс}", "{всего}", "{подпись директора}",
]  # fmt: skip

IF_PICKUP = "{если самовывоз}"
IF_DELIVERY = "{если доставка}"
PAYMENT_FIRST = "{оплата 1}"
PAYMENT_NEXT = "{оплата 2}"


def _runs(p: Paragraph) -> list:
    return list(p.runs)


def replace_in_paragraph(p: Paragraph, mapping: dict[str, str]) -> bool:
    """Заменяет метки в абзаце, даже если они разбиты на несколько runs. True — была замена."""
    changed = False
    for key, value in mapping.items():
        offset = 0  # поиск — после вставленного значения (значение может содержать метку)
        while True:
            runs = _runs(p)
            texts = [r.text for r in runs]
            full = "".join(texts)
            start = full.find(key, offset)
            if start < 0:
                break
            offset = start + len(value)
            end = start + len(key)
            pos = 0
            first = None
            for i, t in enumerate(texts):
                r_start, r_end = pos, pos + len(t)
                pos = r_end
                if r_end <= start or r_start >= end:
                    if r_start >= end:
                        break
                    continue
                before = t[: max(0, start - r_start)]
                after = t[max(0, end - r_start) :] if r_end > end else ""
                if first is None:
                    first = i
                    runs[i].text = before + value + after
                else:
                    runs[i].text = after
            changed = True
    return changed


def _remove(p: Paragraph) -> None:
    el = p._element
    el.getparent().remove(el)


def _clone_after(p: Paragraph) -> Paragraph:
    new = deepcopy(p._element)
    p._element.addnext(new)
    return Paragraph(new, p._parent)


def _all_paragraphs(doc) -> list[Paragraph]:
    result = list(doc.paragraphs)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                result.extend(cell.paragraphs)
    for section in doc.sections:
        for part in (section.header, section.footer):
            result.extend(part.paragraphs)
    return result


def _set_multiline(p: Paragraph, key: str, lines: list[str]) -> None:
    """Метка с несколькими строками (реквизиты): первая строка — в абзац с меткой, остальные — копиями абзаца."""
    lines = lines or [""]
    current = p
    clones = [p]
    for _ in lines[1:]:
        current = _clone_after(current)
        clones.append(current)
    for para, line in zip(clones, lines, strict=True):
        replace_in_paragraph(para, {key: line})


@dataclass
class Party:
    """Покупатель: организация и её руководитель."""

    name: str = ""
    full_name: str = ""
    director_position: str = ""  # родительный падеж: «генерального директора»
    director_name: str = ""  # родительный падеж: «Иванова Ивана Ивановича»
    acting: str = "действующего"  # «действующей» — руководитель-женщина
    basis: str = "Устава"
    requisites: str = ""
    signature: str = ""  # «И.И. Иванов»

    def mapping(self) -> dict[str, str]:
        return {
            "{организация полностью}": self.full_name or self.name,
            "{организация}": self.name,
            "{должность директора}": self.director_position,
            "{ФИО директора}": self.director_name,
            "{действующего}": self.acting,
            "{основание}": self.basis or "Устава",
            "{подпись директора}": self.signature,
        }


@dataclass
class ContractData:
    number: str
    date: str  # «16» октября 2026 г.
    next_year: str
    party: Party


@dataclass
class SpecRow:
    title: str
    lines: list[str] = field(default_factory=list)
    quantity: int | None = None  # None — заголовок раздела («КСО в составе:»)
    total: float = 0.0


@dataclass
class SpecPayment:
    percent: float
    amount: str  # «342 795,60 (… ) рублей 60 копеек»


@dataclass
class SpecData:
    number: str
    date: str
    contract_number: str
    contract_date: str
    party: Party
    rows: list[SpecRow] = field(default_factory=list)
    total: str = ""
    nds_percent: float = 20.0
    nds: str = ""
    total_nds: str = ""
    delivery_term: str = ""
    payments: list[SpecPayment] = field(default_factory=list)
    services: str = "не предусмотрены."
    delivery_address: str = ""  # пусто — самовывоз


def build_contract_docx(template: bytes, data: ContractData) -> bytes:
    doc = Document(io.BytesIO(template))
    mapping = {
        "{номер договора}": data.number,
        "{дата договора}": data.date,
        "{следующий год}": data.next_year,
        **data.party.mapping(),
    }
    lines = [line.rstrip() for line in (data.party.requisites or "").splitlines()]
    for p in _all_paragraphs(doc):
        if "{реквизиты}" in p.text:
            _set_multiline(p, "{реквизиты}", lines)
            continue
        replace_in_paragraph(p, mapping)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _fmt_qty(value: float) -> str:
    return f"{value:g}"


def _fill_cell(cell, text_runs: list[tuple[str, bool]]) -> None:
    """Текст ячейки: [(текст, жирный)], строки — с переносом. Оформление — от первого run образца."""
    p = cell.paragraphs[0]
    for extra in cell.paragraphs[1:]:
        _remove(extra)
    runs = _runs(p)
    sample = runs[0] if runs else None
    bold_sample = next((r for r in runs if r.bold), sample)
    plain_sample = next((r for r in runs if not r.bold), sample)
    for r in runs:
        r._element.getparent().remove(r._element)
    for i, (text, bold) in enumerate(text_runs):
        src = bold_sample if bold else plain_sample
        if src is not None:
            new = deepcopy(src._element)
            for child in list(new):
                if child.tag != qn("w:rPr"):
                    new.remove(child)
            p._element.append(new)
            run = p.runs[-1]
        else:
            run = p.add_run()
        run.text = ("\n" if i else "") + text
        run.bold = bold


def _fill_table(table: Table, data: SpecData) -> None:
    rows = list(table.rows)
    total_idx = next((i for i, r in enumerate(rows) if any("Итого" in c.text for c in r.cells)), len(rows))
    if total_idx < 2:
        return
    sample = rows[1]._tr
    for r in rows[2:total_idx]:
        r._tr.getparent().remove(r._tr)
    anchor = sample
    n = 0
    for row in data.rows:
        tr = deepcopy(sample)
        anchor.addnext(tr)
        anchor = tr
        cells = _Row(tr, table).cells
        unique = []
        for c in cells:
            if not unique or c._tc is not unique[-1]._tc:
                unique.append(c)
        if row.quantity is None:
            values = ["", None, "", ""]
        else:
            n += 1
            values = [str(n), None, _fmt_qty(row.quantity), _money_short(row.total)]
        _fill_cell(unique[0], [(values[0], False)])
        _fill_cell(unique[1], [(row.title, True)] + [(line, False) for line in row.lines])
        if len(unique) > 2:
            _fill_cell(unique[2], [(values[2], False)])
        if len(unique) > 3:
            _fill_cell(unique[3], [(values[3], False)])
    sample.getparent().remove(sample)


def _money_short(value: float) -> str:
    from scr.utils.num_words import money

    return money(value)


def build_spec_docx(template: bytes, data: SpecData) -> bytes:
    doc = Document(io.BytesIO(template))
    mapping = {
        "{номер спецификации}": data.number,
        "{дата спецификации}": data.date,
        "{номер договора}": data.contract_number,
        "{дата договора}": data.contract_date,
        "{срок поставки}": data.delivery_term,
        "{доп услуги}": data.services,
        "{адрес доставки}": data.delivery_address,
        "{итого}": data.total,
        "{ндс}": f"{data.nds_percent:g}",
        "{сумма ндс}": data.nds,
        "{всего}": data.total_nds,
        **data.party.mapping(),
    }
    for table in doc.tables:
        if any("Наименование" in c.text for c in table.rows[0].cells):
            _fill_table(table, data)

    for p in list(doc.paragraphs):
        text = p.text
        if IF_PICKUP in text:
            if data.delivery_address:
                _remove(p)
                continue
            replace_in_paragraph(p, {IF_PICKUP: ""})
        elif IF_DELIVERY in text:
            if not data.delivery_address:
                _remove(p)
                continue
            replace_in_paragraph(p, {IF_DELIVERY: ""})
        elif PAYMENT_FIRST in text:
            first = data.payments[0] if data.payments else SpecPayment(100, data.total_nds)
            replace_in_paragraph(p, {PAYMENT_FIRST: "", "{процент}": f"{first.percent:g}", "{сумма}": first.amount})
            continue
        elif PAYMENT_NEXT in text:
            anchor = p
            rest = data.payments[1:]
            for i, pay in enumerate(rest):
                anchor = _clone_after(anchor)
                values = {PAYMENT_NEXT: "", "{процент}": f"{pay.percent:g}", "{сумма}": pay.amount}
                if i < len(rest) - 1:
                    values["Окончательная оплата"] = "Оплата"  # промежуточный платёж
                replace_in_paragraph(anchor, values)
            _remove(p)
            continue
        replace_in_paragraph(p, mapping)
    for p in _all_paragraphs(doc):
        replace_in_paragraph(p, mapping)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


_BAD_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def safe_file_name(name: str) -> str:
    """Имя файла без недопустимых в Windows символов."""
    return re.sub(r"\s+", " ", _BAD_CHARS.sub(" ", name)).strip(" .") or "document"
