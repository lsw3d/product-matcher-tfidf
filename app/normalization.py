from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


_DOMAIN_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bболгарк\w*\b"), "ушм"),
    (re.compile(r"\bшурик\w*\b"), "шуруповерт"),
    (re.compile(r"\bпроф\.?\s*труб\w*\b"), "труба профильная"),
    (re.compile(r"\bнаждачк\w*\b"), "шкурка шлифовальная"),
    (re.compile(r"\bхомут\w*\s+пластиков\w*\b"), "стяжка нейлоновая"),
    (re.compile(r"\bпластиков\w*\s+хомут\w*\b"), "стяжка нейлоновая"),
    (re.compile(r"\bкруг\s+зачистн\w*\b"), "диск шлифовальный зачистной"),
    (re.compile(r"\bгкл\b"), "гкл гипсокартон"),
    (re.compile(r"\bсдс\b"), "sds"),
    (re.compile(r"\bлс\b"), "ls"),
)

_QUERY_NOISE_RE = re.compile(
    r"\b(?:здравствуйте|пожалуйста|нужен|нужна|нужны|дайте|какие|какой|какая|есть|сколько|посоветуйте|недорогой|недорогая|в\s+наличии)\b"
)

_NON_PRODUCT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:до\s+скольки|режим\s+работы|работаете)\b"),
    re.compile(r"\b(?:оплатить|оплата|картой|наличными)\b"),
    re.compile(r"\b(?:где\s+находится|адрес\s+магазина)\b"),
    re.compile(r"\b(?:статус\s+заказа|заказ\s*№?)\b"),
    re.compile(r"\b(?:вернуть|возврат|гаранти\w*|достав\w*)\b"),
    re.compile(r"\b(?:спасибо|благодарю).*(?:заказ|получил|получила)\b"),
)

_EXPLICIT_DIMENSION_RE = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)"
    r"\s*x\s*(\d+(?:\.\d+)?)"
    r"(?:\s*x\s*(\d+(?:\.\d+)?))?(?![\w.])"
)

_ON_DIMENSION_RE = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)\s+на\s+(\d+(?:\.\d+)?)(?![\w.])"
)

_NUMBER_WITH_UNIT_RE = re.compile(
    r"(?<![\w.-])(\d+(?:\.\d+)?)\s*(мм|см|м|вт|дж|г|кг|мл|л)\b"
)

_CODE_RE = re.compile(
    r"\b(?:ph|pz|t|sl|m|p|pw|тр|арс|tk)\s*-?\s*\d+(?:\.\d+)?(?:[a-zа-я])?\b",
    re.IGNORECASE,
)

_PACK_COUNT_RE = re.compile(
    r"\b(?:пачк\w*|упаковк\w*|уп\.?)\s*(\d{2,5})\b"
)


@dataclass(frozen=True, slots=True)
class QueryFeatures:
    normalized: str
    dimensions: tuple[tuple[float, ...], ...]
    codes: frozenset[str]
    quantities: tuple[tuple[float, str], ...]
    numbers: frozenset[float]
    pack_count: int | None
    unit_hint: str | None


def _base_normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower().replace("ё", "е")
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)
    text = text.replace("×", "x")
    text = re.sub(r"(?<=\d)\s*[хx*]\s*(?=\d)", "x", text)

    # Кириллические символы, похожие на латинские, в технических кодах.
    text = re.sub(r"\bм(?=\s*-?\s*\d)", "m", text)
    text = re.sub(r"\bр(?=\s*-?\s*\d)", "p", text)

    # Приводим обозначение ВВГнг(А)-LS к единой форме.
    text = re.sub(r"\(\s*а\s*\)\s*-?\s*ls\b", " ls", text)

    # Дефисы между словами заменяем пробелами, но сохраняем их в моделях PW-750.
    text = re.sub(r"(?<=[a-zа-я])-(?=[a-zа-я])", " ", text)
    text = re.sub(r"[()\[\]{},;:!?\"']+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def normalize_text(text: str) -> str:
    text = _base_normalize(text)

    text = re.sub(r"\bполтора\b", "1.5", text)
    text = re.sub(r"\bметров(?:ая|ый|ую|ые)\b", "1000 мм", text)

    for pattern, replacement in _DOMAIN_ALIASES:
        text = pattern.sub(replacement, text)

    return re.sub(r"\s+", " ", text).strip()


def _normalize_code(value: str) -> str:
    return value.lower().replace(" ", "").replace("-", "")


def extract_codes(text: str) -> frozenset[str]:
    normalized = normalize_text(text)

    codes = {
        _normalize_code(match.group(0))
        for match in _CODE_RE.finditer(normalized)
    }

    # Латинские слова в каталоге обычно являются сильными признаками:
    # брендом, стандартом или частью модельного обозначения.
    # Поэтому неизвестный бренд не должен матчиться на похожой товар
    # другого производителя только из-за совпадения типа и мощности.
    codes.update(
        re.findall(
            r"(?<![a-z])\b[a-z]{2,}\b(?![a-z])",
            normalized,
        )
    )

    return frozenset(codes)


def extract_dimensions(text: str) -> tuple[tuple[float, ...], ...]:
    normalized = normalize_text(text)

    result: list[tuple[float, ...]] = []

    for match in _EXPLICIT_DIMENSION_RE.finditer(normalized):
        result.append(
            tuple(
                float(value)
                for value in match.groups()
                if value is not None
            )
        )

    # "190 на 48 зубьев" — это диаметр и число зубьев,
    # а не геометрический размер 190x48.
    for match in _ON_DIMENSION_RE.finditer(normalized):
        tail = normalized[match.end() : match.end() + 20]

        if re.search(r"\bзуб", tail):
            continue

        result.append(
            (
                float(match.group(1)),
                float(match.group(2)),
            )
        )

    return tuple(dict.fromkeys(result))


def extract_quantities(text: str) -> tuple[tuple[float, str], ...]:
    normalized = normalize_text(text)

    return tuple(
        (float(value), unit)
        for value, unit in _NUMBER_WITH_UNIT_RE.findall(normalized)
    )


def extract_numbers(text: str) -> frozenset[float]:
    normalized = normalize_text(text)

    return frozenset(
        float(value)
        for value in re.findall(r"\d+(?:\.\d+)?", normalized)
    )


def extract_pack_count(text: str) -> int | None:
    normalized = normalize_text(text)

    match = _PACK_COUNT_RE.search(normalized)

    return int(match.group(1)) if match else None


def extract_unit_hint(text: str) -> str | None:
    normalized = normalize_text(text)

    if re.search(r"\b(?:пачк\w*|упаковк\w*)\b", normalized):
        return "уп"

    if re.search(r"\b(?:кг|килограмм\w*)\b", normalized):
        return "кг"

    if re.search(r"\b(?:за\s+метр|погонн\w*\s+метр)\b", normalized):
        return "м"

    if re.search(r"\bлистами\b", normalized):
        return "лист"

    return None


def is_explicitly_non_product(text: str) -> bool:
    normalized = normalize_text(text)

    return any(
        pattern.search(normalized)
        for pattern in _NON_PRODUCT_PATTERNS
    )


def retrieval_text(text: str) -> str:
    normalized = normalize_text(text)
    normalized = _QUERY_NOISE_RE.sub(" ", normalized)

    return re.sub(r"\s+", " ", normalized).strip()


def parse_query(text: str) -> QueryFeatures:
    return QueryFeatures(
        normalized=normalize_text(text),
        dimensions=extract_dimensions(text),
        codes=extract_codes(text),
        quantities=extract_quantities(text),
        numbers=extract_numbers(text),
        pack_count=extract_pack_count(text),
        unit_hint=extract_unit_hint(text),
    )