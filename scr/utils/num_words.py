"""Суммы прописью и даты для договоров: «342 795,60 (триста сорок две тысячи семьсот девяносто пять) рублей 60 копеек»,
«16» октября 2026 г."""

from datetime import date, datetime

_ONES_M = ["", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
_ONES_F = ["", "одна", "две", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
_TEENS = [
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
    "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать",
]  # fmt: skip
_TENS = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто"]
_HUNDREDS = [
    "", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот", "восемьсот", "девятьсот",
]  # fmt: skip
# Разряды: (формы для 1, 2–4, 5–20), женский род
_SCALES = [
    (("", "", ""), False),
    (("тысяча", "тысячи", "тысяч"), True),
    (("миллион", "миллиона", "миллионов"), False),
    (("миллиард", "миллиарда", "миллиардов"), False),
]

MONTHS_GENITIVE = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]  # fmt: skip


def plural(n: int, forms: tuple[str, str, str]) -> str:
    """Форма слова для числа: (1 рубль, 2 рубля, 5 рублей)."""
    n = abs(n) % 100
    if 11 <= n <= 19:
        return forms[2]
    n %= 10
    if n == 1:
        return forms[0]
    if 2 <= n <= 4:
        return forms[1]
    return forms[2]


def _triad(n: int, feminine: bool) -> list[str]:
    words = [_HUNDREDS[n // 100]]
    rest = n % 100
    if 10 <= rest <= 19:
        words.append(_TEENS[rest - 10])
    else:
        words.append(_TENS[rest // 10])
        words.append((_ONES_F if feminine else _ONES_M)[rest % 10])
    return [w for w in words if w]


def int_to_words(n: int) -> str:
    """Целое число прописью (мужской род): 342795 → «триста сорок две тысячи семьсот девяносто пять»."""
    if n == 0:
        return "ноль"
    words: list[str] = []
    for i, (forms, feminine) in enumerate(_SCALES):
        triad = n // 1000**i % 1000
        if not triad:
            continue
        part = _triad(triad, feminine)
        if i:
            part.append(plural(triad, forms))
        words = part + words
    return " ".join(words)


def money(value: float) -> str:
    """342795.6 → «342 795,60» (неразрывный пробел между разрядами)."""
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def rubles_in_words(value: float) -> str:
    """«342 795,60 (триста сорок две тысячи семьсот девяносто пять) рублей 60 копеек»."""
    kopecks_total = round(value * 100)
    rubles, kopecks = divmod(kopecks_total, 100)
    return (
        f"{money(kopecks_total / 100)} ({int_to_words(rubles)}) "
        f"{plural(rubles, ('рубль', 'рубля', 'рублей'))} "
        f"{kopecks:02d} {plural(kopecks, ('копейка', 'копейки', 'копеек'))}"
    )


def date_words(value: date | datetime | None) -> str:
    """«16» октября 2026 г.; нет даты — бланк для заполнения."""
    if value is None:
        return "«__» ____________ 20__ г."
    return f"«{value.day:02d}» {MONTHS_GENITIVE[value.month - 1]} {value.year} г."
