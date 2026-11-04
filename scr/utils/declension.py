"""Дательный падеж для обращения в ТКП: «Директору», «Чистякову Федору Владимировичу»."""

import re

from pytrovich.detector import PetrovichGenderDetector
from pytrovich.enums import Case, Gender, NamePart
from pytrovich.maker import PetrovichDeclinationMaker

_maker = PetrovichDeclinationMaker()
_detector = PetrovichGenderDetector()

_ADJ_RE = re.compile(r"(ый|ий|ой|ая|яя)$")
_HUSHING = "жшщч"
_GUTTURAL = "кгх"


def _keep_case(word: str, ending_len: int, new_ending: str) -> str:
    return word[: len(word) - ending_len] + new_ending


def _adjective(word: str) -> str:
    low = word.lower()
    if low.endswith(("ая", "яя")):
        return _keep_case(word, 2, "ой" if low.endswith("ая") else "ей")
    if low.endswith("ий") and len(low) > 2 and low[-3] not in _GUTTURAL:
        return _keep_case(word, 2, "ему")
    return _keep_case(word, 2, "ому")


def _noun(word: str) -> str:
    low = word.lower()
    if low.endswith(("ь", "й")):
        return _keep_case(word, 1, "ю")
    if low.endswith(("а", "я")):
        return _keep_case(word, 1, "е")
    if low[-1:].isalpha() and low[-1] not in "аеёиоуыэюя":
        return word + "у"
    return word


def position_dative(position: str) -> str:
    """Должность в дательном падеже: склоняются прилагательные и первое существительное,
    остальное (зависимые слова в родительном — «директор филиала») не меняется."""
    words = position.split()
    for i, word in enumerate(words):
        if not word[:1].isalpha() or any(ch.isdigit() for ch in word) or (word.isupper() and len(word) > 1):
            return " ".join(words)  # аббревиатура или номер — дальше не склоняем
        if _ADJ_RE.search(word.lower()) and len(word) > 3:
            words[i] = _adjective(word)
            continue
        words[i] = _noun(word)
        break
    return " ".join(words)


def fio_dative(fio: str) -> str:
    """ФИО «Фамилия Имя Отчество» в дательном падеже; пол — по отчеству или имени."""
    parts = fio.split()
    if not parts:
        return fio
    last, first, middle = (parts + [None, None])[:3]
    try:
        gender = _detector.detect(firstname=first, middlename=middle) if first or middle else Gender.ANDROGYNOUS
        result = [_maker.make(NamePart.LASTNAME, gender, Case.DATIVE, last)]
        if first:
            result.append(_maker.make(NamePart.FIRSTNAME, gender, Case.DATIVE, first))
        if middle:
            result.append(_maker.make(NamePart.MIDDLENAME, gender, Case.DATIVE, middle))
    except Exception:  # noqa: BLE001 — не удалось просклонять: как есть
        return fio
    return " ".join(result + parts[3:])


# ── Родительный падеж для договора: «в лице генерального директора Иванова Ивана Ивановича» ──


def _adjective_genitive(word: str) -> str:
    low = word.lower()
    if low.endswith(("ая", "яя")):
        return _keep_case(word, 2, "ой" if low.endswith("ая") else "ей")
    if low.endswith("ий") and len(low) > 2 and low[-3] not in _GUTTURAL:
        return _keep_case(word, 2, "его")
    return _keep_case(word, 2, "ого")


def _noun_genitive(word: str) -> str:
    low = word.lower()
    if low.endswith(("ь", "й")):
        return _keep_case(word, 1, "я")
    if low.endswith("я"):
        return _keep_case(word, 1, "и")
    if low.endswith("а"):
        return _keep_case(word, 1, "и" if len(low) > 1 and low[-2] in _GUTTURAL + _HUSHING else "ы")
    if low[-1:].isalpha() and low[-1] not in "аеёиоуыэюя":
        return word + "а"
    return word


def position_genitive(position: str) -> str:
    """Должность в родительном падеже с маленькой буквы: «Генеральный директор» → «генерального директора»."""
    words = position.split()
    for i, word in enumerate(words):
        if not word[:1].isalpha() or any(ch.isdigit() for ch in word) or (word.isupper() and len(word) > 1):
            break  # аббревиатура или номер — дальше не склоняем
        if _ADJ_RE.search(word.lower()) and len(word) > 3:
            words[i] = _adjective_genitive(word)
            continue
        words[i] = _noun_genitive(word)
        break
    if words and words[0][:1].isupper() and not (len(words[0]) > 1 and words[0].isupper()):
        words[0] = words[0][0].lower() + words[0][1:]
    return " ".join(words)


def _gender(first: str | None, middle: str | None) -> Gender:
    try:
        return _detector.detect(firstname=first, middlename=middle) if first or middle else Gender.ANDROGYNOUS
    except Exception:  # noqa: BLE001
        return Gender.ANDROGYNOUS


def is_female(fio: str) -> bool:
    parts = fio.split()
    first, middle = (parts[1:] + [None, None])[:2]
    return _gender(first, middle) == Gender.FEMALE


def fio_genitive(fio: str) -> str:
    """ФИО «Фамилия Имя Отчество» в родительном падеже; пол — по отчеству или имени."""
    parts = fio.split()
    if not parts:
        return fio
    last, first, middle = (parts + [None, None])[:3]
    gender = _gender(first, middle)
    try:
        result = [_maker.make(NamePart.LASTNAME, gender, Case.GENITIVE, last)]
        if first:
            result.append(_maker.make(NamePart.FIRSTNAME, gender, Case.GENITIVE, first))
        if middle:
            result.append(_maker.make(NamePart.MIDDLENAME, gender, Case.GENITIVE, middle))
    except Exception:  # noqa: BLE001 — не удалось просклонять: как есть
        return fio
    return " ".join(result + parts[3:])


def initials_signature(fio: str) -> str:
    """Подпись «А.В. Тихонов» из «Тихонов Анатолий Валентинович»."""
    parts = fio.split()
    if not parts:
        return fio
    initials = "".join(f"{p[0].upper()}." for p in parts[1:3] if p)
    return f"{initials} {parts[0]}".strip()
