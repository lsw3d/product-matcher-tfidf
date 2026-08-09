from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


_DOMAIN_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    # Сначала сохраняем явно указанный тип шлифмашины, чтобы более общий
    # alias ниже не превратил ленточную/орбитальную машину в УШМ.
    (
        re.compile(r"\bленточн\w*\s+шлифовальн\w*\s+машин\w*\b"),
        "ленточная шлифмашина",
    ),
    (
        re.compile(
            r"\b(?:эксцентриков\w*|орбитальн\w*)\s+"
            r"шлифовальн\w*\s+машин\w*\b"
        ),
        "орбитальная шлифмашина",
    ),
    (
        re.compile(r"\bвибрационн\w*\s+шлифовальн\w*\s+машин\w*\b"),
        "вибрационная шлифмашина",
    ),
    (re.compile(r"\bуглошлифовальн\w*\s+машин\w*\b"), "ушм"),
    (re.compile(r"\bшлифовальн\w*\s+машин\w*\b"), "ушм"),
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

# Признаки, которые меняют сам вариант товара.
# Если покупатель явно указал такой признак, кандидат должен его содержать.
_QUALIFIER_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b(?:по\s+дерев\w*|гипсокартон\s+дерев\w*)\b"),
        "application:wood",
    ),
    (
        re.compile(r"\b(?:по\s+металл\w*|гипсокартон\s+металл\w*)\b"),
        "application:metal",
    ),
    (re.compile(r"\bпо\s+бетон\w*\b"), "application:concrete"),
    (re.compile(r"\bпо\s+камн\w*\b"), "application:stone"),
    (
        re.compile(r"\bпо\s+нержав\w*(?:\s+стал\w*)?\b"),
        "application:stainless",
    ),
    (re.compile(r"\bлазерн\w*\b"), "level:laser"),
    (re.compile(r"\bпузырьков\w*\b"), "level:bubble"),
    (re.compile(r"\bсамоконтр\w*\b"), "fastener:self_locking"),
    (re.compile(r"\bленточн\w*\b"), "grinder:belt"),
    (
        re.compile(r"\b(?:эксцентриков\w*|орбитальн\w*)\b"),
        "grinder:orbital",
    ),
    (re.compile(r"\bвибрационн\w*\b"), "grinder:vibrating"),
    (re.compile(r"\bушм\b"), "grinder:angle"),
    (re.compile(r"\bсин\w*\b"), "color:blue"),
    (re.compile(r"\bкрасн\w*\b"), "color:red"),
    (re.compile(r"\bчерн\w*\b"), "color:black"),
    (re.compile(r"\bбел\w*\b"), "color:white"),
    (re.compile(r"\bзелен\w*\b"), "color:green"),
    (re.compile(r"\bжелт\w*\b"), "color:yellow"),
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
    r"(?<![\w.])(?:m\s*-?\s*)?(\d+(?:\.\d+)?)"
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
    r"\b(?:ph|pz|t|sl|m|p|pw|din|тр|арс|tk)\s*-?\s*\d+(?:\.\d+)?(?:[a-zа-я])?\b",
    re.IGNORECASE,
)

_STANDALONE_CODE_RE = re.compile(r"\b(?:sds|ls)\b", re.IGNORECASE)

# Латинское слово считаем брендом только в типичной позиции после русского
# названия товара: «дрель bosch», «дрель prowerk». Случайное английское
# слово в другой части сообщения больше не становится hard constraint.
_BRAND_AFTER_PRODUCT_RE = re.compile(
    r"\b[а-я]+(?:\s+[а-я]+){0,2}\s+(?P<brand>[a-z]{3,})\b",
    re.IGNORECASE,
)

# В M10x60 обычная граница слова после 10 отсутствует из-за x.
_THREAD_CODE_RE = re.compile(
    r"(?<!\w)m\s*-?\s*(\d+(?:\.\d+)?)(?=\s*x|\b)",
    re.IGNORECASE,
)

_PACK_COUNT_RE = re.compile(
    r"\b(?:пачк\w*|упаковк\w*|уп\.?)\s*(?P<value>\d{2,5})\b"
)

_ORDER_AMOUNT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?P<value>\d+(?:\.\d+)?)\s*"
        r"(?:шт(?:\.|ук\w*)?|штук\w*|метр\w*|м|килограмм\w*|кг|лист(?:а|ов|ами)?|пачк\w*|упаковк\w*)\b"
    ),
    re.compile(
        r"\b(?:шт(?:\.|ук\w*)?|штук\w*|метр\w*|килограмм\w*|кг|лист(?:а|ов)?|пачк\w*|упаковк\w*)\s+"
        r"(?P<value>\d+(?:\.\d+)?)\b"
    ),
    re.compile(
        r"^\s*(?P<value>\d+(?:\.\d+)?)\s+(?=[a-zа-я])"
    ),
    re.compile(
        r"\b(?:нужно|надо|дайте|возьму|хочу|закаж\w*|мне)\s+"
        r"(?P<value>\d+(?:\.\d+)?)\b"
    ),
    re.compile(
        r"\b(?:до|за|около|бюджет\w*|не\s+дороже)\s*"
        r"(?P<value>\d+(?:\.\d+)?)\s*(?:руб(?:\.|лей|ля)?|₽)?\b"
    ),
)


@dataclass(frozen=True, slots=True)
class QueryFeatures:
    normalized: str
    dimensions: tuple[tuple[float, ...], ...]
    codes: frozenset[str]
    qualifiers: frozenset[str]
    quantities: tuple[tuple[float, str], ...]
    numbers: frozenset[float]
    pack_count: int | None
    unit_hint: str | None


def _base_normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower().replace("ё", "е")
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)
    text = text.replace("×", "x")
    text = re.sub(r"(?<=\d)\s*[хx*]\s*(?=\d)", "x", text)

    text = re.sub(r"(?<![a-z])mm\b", " мм", text)
    text = re.sub(r"(?<![a-z])cm\b", " см", text)
    text = re.sub(r"(?<![a-z])kg\b", " кг", text)
    text = re.sub(r"(?<![a-z])ml\b", " мл", text)
    text = re.sub(r"(?<=\d)\s*w\b", " вт", text)
    text = re.sub(r"(?<=\d)\s*v\b", " в", text)

    text = re.sub(r"\bм(?=\s*-?\s*\d)", "m", text)
    text = re.sub(r"\bр(?=\s*-?\s*\d)", "p", text)

    text = re.sub(r"\(\s*а\s*\)\s*-?\s*ls\b", " ls", text)

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

    codes.update(
        f"m{match.group(1)}"
        for match in _THREAD_CODE_RE.finditer(normalized)
    )

    codes.update(
        match.group(0).lower()
        for match in _STANDALONE_CODE_RE.finditer(normalized)
    )

    codes.update(
        match.group("brand").lower()
        for match in _BRAND_AFTER_PRODUCT_RE.finditer(normalized)
        if match.group("brand").lower() not in {"sds", "plus", "ls"}
    )

    return frozenset(codes)


def extract_qualifiers(text: str) -> frozenset[str]:
    normalized = normalize_text(text)

    return frozenset(
        qualifier
        for pattern, qualifier in _QUALIFIER_PATTERNS
        if pattern.search(normalized)
    )


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

    ignored_spans: list[tuple[int, int]] = []

    for pattern in _ORDER_AMOUNT_PATTERNS:
        for match in pattern.finditer(normalized):
            ignored_spans.append(match.span("value"))

    for match in _PACK_COUNT_RE.finditer(normalized):
        ignored_spans.append(match.span("value"))

    def is_order_amount(start: int, end: int) -> bool:
        return any(
            start >= ignored_start and end <= ignored_end
            for ignored_start, ignored_end in ignored_spans
        )

    return frozenset(
        float(match.group(0))
        for match in re.finditer(r"\d+(?:\.\d+)?", normalized)
        if not is_order_amount(*match.span())
    )


def extract_pack_count(text: str) -> int | None:
    normalized = normalize_text(text)

    match = _PACK_COUNT_RE.search(normalized)

    return int(match.group("value")) if match else None


def extract_unit_hint(text: str) -> str | None:
    normalized = normalize_text(text)

    if re.search(r"\b(?:пачк\w*|упаковк\w*)\b", normalized):
        return "уп"

    if re.search(r"\b(?:кг|килограмм\w*)\b", normalized):
        return "кг"

    if re.search(r"\b(?:за\s+метр|погонн\w*\s+метр)\b", normalized):
        return "м"

    if re.search(r"\bлист(?:а|ов|ами)?\b", normalized):
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


def lexical_text(text: str) -> str:
    """Текстовые признаки товара без числовых характеристик и моделей."""
    normalized = retrieval_text(text)

    # Убираем модели и размерные токены: они используются отдельно как
    # structural constraints и не должны сами доказывать тип товара.
    normalized = re.sub(
        r"\b[a-zа-я]+-?\d[\w.-]*\b",
        " ",
        normalized,
    )
    normalized = re.sub(
        r"(?<!\w)\d+(?:\.\d+)?(?:x\d+(?:\.\d+)?)+(?!\w)",
        " ",
        normalized,
    )
    normalized = re.sub(r"\d+(?:\.\d+)?", " ", normalized)
    normalized = re.sub(
        r"\b(?:мм|см|м|вт|дж|г|кг|мл|л|шт|уп|на)\b",
        " ",
        normalized,
    )
    normalized = re.sub(r"[^a-zа-я]+", " ", normalized)

    return re.sub(r"\s+", " ", normalized).strip()


def parse_query(text: str) -> QueryFeatures:
    return QueryFeatures(
        normalized=normalize_text(text),
        dimensions=extract_dimensions(text),
        codes=extract_codes(text),
        qualifiers=extract_qualifiers(text),
        quantities=extract_quantities(text),
        numbers=extract_numbers(text),
        pack_count=extract_pack_count(text),
        unit_hint=extract_unit_hint(text),
    )