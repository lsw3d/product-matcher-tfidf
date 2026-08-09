from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


_FUZZY_TOKEN_ALIASES = {
    "болгарка": "ушм",
    "шурик": "шуруповерт",
    "наждачка": "шкурка шлифовальная",
}

_DOMAIN_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:для|на)\s+дерев\w*\b"), "по дереву"),
    (re.compile(r"\b(?:для|на)\s+металл\w*\b"), "по металлу"),
    (re.compile(r"\b(?:для|на)\s+бетон\w*\b"), "по бетону"),
    (re.compile(r"\b(?:для|на)\s+камн\w*\b"), "по камню"),
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
    (re.compile(r"\bгкл\s+гипсокартон\b"), "гипсокартонный"),
    (
        re.compile(r"\bдля\s+(?:гкл|гипсокартон(?:а|у|ом|е)?)\b"),
        "гипсокартонный",
    ),
    (re.compile(r"\bгкл\b"), "гипсокартонный"),
    (re.compile(r"\bгипсокартон\b"), "гипсокартонный"),
    (re.compile(r"\bсдс\b"), "sds"),
    (re.compile(r"\bввгнг(?:[аa])?(?:лс|ls)\b"), "ввгнг ls"),
    (re.compile(r"\bлс\b"), "ls"),
)

_QUALIFIER_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b(?:по\s+дерев\w*|гипсокартонн\w*\s+дерев\w*)\b"),
        "application:wood",
    ),
    (
        re.compile(r"\b(?:по\s+металл\w*|гипсокартонн\w*\s+металл\w*)\b"),
        "application:metal",
    ),
    (re.compile(r"\bпо\s+бетон\w*\b"), "application:concrete"),
    (re.compile(r"\bпо\s+камн\w*\b"), "application:stone"),
    (re.compile(r"\bпо\s+нержав\w*(?:\s+стал\w*)?\b"), "application:stainless"),
    (re.compile(r"\bлазерн\w*\b"), "level:laser"),
    (re.compile(r"\bпузырьков\w*\b"), "level:bubble"),
    (re.compile(r"\bсамоконтр\w*\b"), "fastener:self_locking"),
    (re.compile(r"\bленточн\w*\b"), "grinder:belt"),
    (re.compile(r"\b(?:эксцентриков\w*|орбитальн\w*)\b"), "grinder:orbital"),
    (re.compile(r"\bвибрационн\w*\b"), "grinder:vibrating"),
    (re.compile(r"\bушм\b"), "grinder:angle"),
    (re.compile(r"\bсин\w*\b"), "color:blue"),
    (re.compile(r"\bкрасн\w*\b"), "color:red"),
    (re.compile(r"\bчерн\w*\b"), "color:black"),
    (re.compile(r"\bбел\w*\b"), "color:white"),
    (re.compile(r"\bзелен\w*\b"), "color:green"),
    (re.compile(r"\bжелт\w*\b"), "color:yellow"),
)

_APPLICATION_PHRASES = (
    re.compile(r"\bпо\s+(?:дерев|металл|бетон|камн|нержав)\w*(?:\s+стал\w*)?\b"),
)

_QUERY_NOISE_RE = re.compile(
    r"\b(?:здравствуйте|пожалуйста|мне|нам|можно|нужен|нужна|нужны|нужно|"
    r"надо|дайте|хочу|хотел|хотела|хотелось|возьму|ищу|ищем|интересует|"
    r"купить|заказать|заказ|взять|показ\w*|покаж\w*|подберите|подобрать|какие|какой|какая|что|"
    r"можете|можешь|могли|будет|есть|сколько|сто(?:ит|ить)|стоимость|цена|почем|наличие|"
    r"посовет\w*|подсказ\w*|скаж\w*|сказ\w*|сейчас|сегодня|завтра|срочно|прямо|"
    r"случайно|около|один|одна|одно|одну|два|две|три|четыре|пар(?:а|ы|у|ой|ами|ах)?|"
    r"только|еще|тоже|также|нибудь|вообще|просто|желательно|обычн\w*|"
    r"люб(?:ой|ая|ые|ых)|уважаем\w*|"
    r"недорогой|недорогая|дешевый|дешевая|дешевле|подешевле|бюджетный|бюджетная|"
    r"хороший|хорошая|нормальный|нормальная|качественный|качественная|"
    r"модел\w*|мощност\w*|напряжени\w*|цвет\w*|зернистост\w*|резьб\w*|объем\w*|"
    r"материал\w*|назначени\w*|масс\w*|вес\w*|бренд\w*|производител\w*|названи\w*|"
    r"количеств\w*|марка|марки|марку|маркой|в\s+наличии)\b"
)

# Расходник + инструмент, в который он ставится: название инструмента здесь
# не признак товара и мешает подбору. Пары перечислены явно, потому что
# сочетание бывает и несовместимым: бур ставят в перфоратор, но не в дрель.
_TOOL_COMPATIBILITY_PATTERNS = tuple(
    (
        re.compile(
            rf"\b(?P<consumable>{consumable})(?P<between>(?:\s+\S+){{0,4}}?)"
            rf"\s+(?:для|на|под)\s+(?:{tools})\b"
        ),
        r"\g<consumable>\g<between>",
    )
    for consumable, tools in (
        (r"диск\w*|круг\w*", r"ушм|болгарк\w*"),
        (r"бур\w*", r"перфоратор\w*"),
        (r"бит\w*|сверл\w*", r"шуруповерт\w*|дрел\w*"),
    )
)

_FREE_TEXT_NOISE_PATTERNS = (
    re.compile(r"\b(?:добрый\s+(?:день|вечер|утро)|у\s+вас)\b"),
    re.compile(r"\bкакой\s+нибудь\b"),
    re.compile(r"\bкак\s+у\s+[a-zа-я]+\b"),
    re.compile(r"\bдля\s+(?:дома|работы|дачи)\b"),
)

_LEXICAL_ORDER_NOISE_RE = re.compile(
    r"\b(?:пачк\w*|упаковк\w*|уп\.?|шт(?:\.|ук\w*)?|штук\w*|"
    r"пар(?:а|ы|у|ой|ами|ах)?|метр\w*|килограмм\w*|кг|листа|листов|листами|"
    r"стенк\w*|диаметр(?:а|у|ом|е)?|размер(?:а|у|ом|е|ы|ов)?|"
    r"длин(?:а|ы|е|у|ой)?|ширин(?:а|ы|е|у|ой)?|толщин(?:а|ы|е|у|ой)?|"
    r"син\w*|красн\w*|черн\w*|бел\w*|зелен\w*|желт\w*|до|за|руб(?:\.|лей|ля)?|в)\b"
)

_NON_PRODUCT_PATTERNS = (
    re.compile(r"\b(?:до\s+скольки|режим\s+работы|работаете)\b"),
    re.compile(r"\b(?:оплатить|оплата|картой|наличными)\b"),
    re.compile(r"\b(?:где\s+находится|адрес\s+магазина)\b"),
    re.compile(r"\b(?:статус\s+заказа|заказ\s*(?:№\s*)?\d{3,})\b"),
    re.compile(r"\b(?:вернуть|возврат|достав\w*)\b"),
    re.compile(r"\b(?:по\s+гаранти\w*|гаранти\w*\s+(?:на\s+)?(?:заказ|покупк|товар|чек)\w*)\b"),
    re.compile(r"\b(?:спасибо|благодарю).*(?:заказ|получил|получила)\b"),
)

_EXPLICIT_DIMENSION_RE = re.compile(
    r"(?<![\w.])(?:m\s*-?\s*)?(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)"
    r"(?:\s*x\s*(\d+(?:\.\d+)?))?(?![\w.])"
)
_ON_DIMENSION_RE = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)\s+на\s+(\d+(?:\.\d+)?)(?![\w.])"
)
_NUMBER_WITH_UNIT_RE = re.compile(
    r"(?<![\w.-])(\d+(?:\.\d+)?)\s*(мм|см|вт|дж|кг|мл|м|в|г|л)\b"
)
_X_NUMBER_WITH_UNIT_RE = re.compile(r"(?<=x)(\d+(?:\.\d+)?)\s*(мм|см|м)\b")
_RANGE_WITH_UNIT_RE = re.compile(
    r"(?<![\w.-])(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*"
    r"(мм|см|вт|дж|кг|мл|м|в|г|л)\b"
)
_NEGATIVE_NUMBER_RE = re.compile(
    r"(?:(?<![a-zа-я0-9])-\s*\d|[xх×*]\s*-\s*\d)", re.IGNORECASE
)
_CODE_RE = re.compile(
    r"\b[a-zа-я]+(?:\s*-\s*)?\d+(?:\.\d+)?(?:[a-zа-я]+)?(?=\b|x\d)",
    re.IGNORECASE,
)
_STANDALONE_CODE_RE = re.compile(r"\b(?:sds|ls)\b", re.IGNORECASE)
_THREAD_CODE_RE = re.compile(
    r"(?<!\w)m\s*-?\s*(\d+(?:\.\d+)?)(?=\s*x|\b)", re.IGNORECASE
)

_PACK_COUNT_PATTERNS = (
    re.compile(
        r"\b(?:пачк\w*|упаковк\w*|уп\.?)\s*(?:по\s*)?"
        r"(?P<value>\d+)\s*шт(?:\.|ук\w*)?\b"
    ),
    re.compile(
        r"\b(?:пачк\w*|упаковк\w*|уп\.?)\s*(?:по\s*)?"
        r"(?P<value>\d{2,})\b"
    ),
    re.compile(
        r"\b(?:по\s*)?(?P<value>\d+)\s*шт(?:\.|ук\w*)?\s+"
        r"(?:в\s+)?(?:пачк\w*|упаковк\w*)\b"
    ),
)

_ORDER_AMOUNT_PATTERNS = (
    re.compile(r"\b(?:цена|стоимость|стоит)\s*(?P<value>\d+(?:\.\d+)?)\b"),
    re.compile(
        r"\b(?P<value>\d+(?:\.\d+)?)\s*(?:руб(?:\.|лей|ля)?|р\.?|₽)(?!\w)"
    ),
    re.compile(
        r"\b(?P<value>\d+(?:\.\d+)?)\s*"
        r"(?:шт(?:\.|ук\w*)?|штук\w*|метр\w*|м|килограмм\w*|кг|"
        r"пар(?:а|ы|у|ой|ами|ах)?|листа|листов|листами|пачк\w*|упаковк\w*)\b"
    ),
    re.compile(
        r"\b(?:шт(?:\.|ук\w*)?|штук\w*|метр\w*|килограмм\w*|кг|"
        r"пар(?:а|ы|у|ой|ами|ах)?|лист(?:а|ов|ами)|пачк\w*|упаковк\w*)\s+"
        r"(?P<value>\d+(?:\.\d+)?)\b"
    ),
    re.compile(r"^\s*(?P<value>1)\s+(?=[a-zа-я]+\b)"),
    re.compile(r"^\s*(?P<value>[234])\s+(?=[a-zа-я]+(?:а|я|ы|и)\b)"),
    re.compile(r"^\s*(?P<value>\d+(?:\.\d+)?)\s+(?=[a-zа-я]+(?:ов|ев|ей)\b)"),
    re.compile(
        r"\b(?:нужно|надо|дайте|возьму|хочу|закаж\w*|мне)\s+"
        r"(?P<value>\d+(?:\.\d+)?)\b"
    ),
    re.compile(
        r"\b(?:до|за|около|бюджет\w*|не\s+дороже)\s*"
        r"(?P<value>\d+(?:\.\d+)?)\s*(?:руб(?:\.|лей|ля)?|₽)?\b"
    ),
)

_CYRILLIC_RE = re.compile(r"[а-я]")
_MAX_CODE_VARIANTS = 8
_MIN_STEM_LENGTH = 3

# Частотные окончания русских существительных и прилагательных, от длинных
# к коротким: снимается ровно одно, самое длинное подходящее. Окончания с `й`
# записаны и в свёрнутом виде (`ей` -> `еи`), потому что диакритика снимается
# до отсечения окончания.
_WORD_ENDINGS = (
    "ыми", "ими", "ого", "его", "ому", "ему", "ами", "ями",
    "ах", "ях", "ов", "ев", "ей", "еи", "ый", "ыи", "ий", "ии", "ой", "ои",
    "ая", "яя", "ое", "ее", "ые", "ие", "ых", "их", "ую", "юю",
    "ам", "ям", "ом", "ем", "ью", "ья", "ия",
    "а", "е", "и", "о", "у", "ы", "ь", "ю", "я",
)

# Буквы, которые выглядят одинаково в кириллице и латинице: так покупатель
# набирает `р120` вместо `P120` или `рн2` вместо `PH2`.
_HOMOGLYPHS = {
    "а": "a", "в": "b", "е": "e", "к": "k", "м": "m", "н": "h",
    "о": "o", "р": "p", "с": "c", "т": "t", "у": "y", "х": "x",
}

# Транскрипция для кодов, записанных по звучанию: `ТР-750` -> `TR-750`,
# `АРС-230` -> `ARS-230`, `ПВ-12Л` -> `PW-12L`.
_TRANSCRIPTIONS = {
    "а": ("a",), "б": ("b",), "в": ("v", "w"), "г": ("g",), "д": ("d",),
    "е": ("e",), "ж": ("zh",), "з": ("z",), "и": ("i",), "й": ("y",),
    "к": ("k",), "л": ("l",), "м": ("m",), "н": ("n",), "о": ("o",),
    "п": ("p",), "р": ("r",), "с": ("s",), "т": ("t",), "у": ("u",),
    "ф": ("f",), "х": ("h",), "ц": ("c",), "ч": ("ch",), "ш": ("sh",),
    "щ": ("sch",), "ъ": ("",), "ы": ("y",), "ь": ("",), "э": ("e",),
    "ю": ("yu",), "я": ("ya",),
}

_UNIT_HINTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:пачк\w*|упаковк\w*|уп\.?)\b"), "уп"),
    (re.compile(r"\b(?:кг|килограмм\w*)\b"), "кг"),
    (re.compile(r"\bпар(?:а|ы|у|ой|ами|ах)?\b"), "пара"),
    (re.compile(r"\b(?:за\s+метр|погонн\w*\s+метр)\b"), "м"),
    (re.compile(r"\bлист(?:а|ов|ами)?\b"), "лист"),
)

_LATIN_UNITS = (("mm", "мм"), ("cm", "см"), ("kg", "кг"), ("ml", "мл"))
_FULL_UNITS = (
    ("миллиметр", "мм"),
    ("сантиметр", "см"),
    ("метр", "м"),
    ("ватт", "вт"),
    ("вольт", "в"),
    ("килограмм", "кг"),
    ("грамм", "г"),
    ("миллилитр", "мл"),
    ("литр", "л"),
)


@dataclass(frozen=True, slots=True)
class ItemFeatures:
    normalized: str
    lexical: str
    dimensions: tuple[tuple[float, ...], ...]
    codes: frozenset[str]
    code_variants: frozenset[str]
    qualifiers: frozenset[str]
    quantities: tuple[tuple[float, str], ...]
    numbers: frozenset[float]
    pack_count: int | None


@dataclass(frozen=True, slots=True)
class QueryFeatures:
    normalized: str
    retrieval: str
    lexical: str
    dimensions: tuple[tuple[float, ...], ...]
    codes: frozenset[str]
    qualifiers: frozenset[str]
    quantities: tuple[tuple[float, str], ...]
    numbers: frozenset[float]
    pack_count: int | None
    unit_hint: str | None
    non_product: bool


def _base_normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower().replace("ё", "е")
    text = re.sub(r"(?<=\d),(?=\d)", ".", text).replace("×", "x")
    text = re.sub(r"(?<=\d)\s*[хx*]\s*(?=\d)", "x", text)

    for latin, russian in _LATIN_UNITS:
        text = re.sub(rf"(?<![a-z]){latin}\b", f" {russian}", text)
    text = re.sub(r"(?<=\d)\s*w\b", " вт", text)
    text = re.sub(r"(?<=\d)\s*v\b", " в", text)

    text = re.sub(r"\bметр(?:а|ов|ы)?\s+(\d+(?:\.\d+)?)\b", r"\1 м", text)
    for full, short in _FULL_UNITS:
        text = re.sub(rf"(?<=\d)\s*{full}(?:а|ов|ы)?\b", f" {short}", text)

    text = re.sub(r"\bм(?=\s*-?\s*\d)", "m", text)
    text = re.sub(r"\bр(?=\s*-?\s*\d)", "p", text)
    text = re.sub(r"\(\s*а\s*\)\s*-?\s*ls\b", " ls", text)
    text = re.sub(r"(?<=[a-zа-я])-(?=[a-zа-я])", " ", text)
    text = re.sub(r"[()\[\]{},;:!?\"']+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def token_key(value: str) -> str:
    """Ключ сравнения слов: снимает диакритику (`й` -> `и`) и окончание.

    Полноценная морфология здесь избыточна: достаточно отрезать одно самое
    длинное окончание, чтобы `саморезы`, `саморезов` и `саморез` сошлись в
    одну форму. Остаток различий (`гайки` / `гаек`) добирает проверка на
    одну правку в `_tokens_are_similar`.
    """
    folded = "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )
    for ending in _WORD_ENDINGS:
        if folded.endswith(ending) and len(folded) - len(ending) >= _MIN_STEM_LENGTH:
            return folded[: -len(ending)]
    return folded


def is_one_edit_apart(left: str, right: str) -> bool:
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) == len(right):
        return sum(a != b for a, b in zip(left, right)) <= 1

    shorter, longer = (left, right) if len(left) < len(right) else (right, left)
    short_idx = long_idx = 0
    skipped = False
    while short_idx < len(shorter) and long_idx < len(longer):
        if shorter[short_idx] == longer[long_idx]:
            short_idx += 1
            long_idx += 1
        elif skipped:
            return False
        else:
            skipped = True
            long_idx += 1
    return True


def _matches_fuzzy_alias(value: str, alias: str) -> bool:
    if value == alias:
        return True
    if len(alias) <= 5:
        safe_prefix = len(value) >= 3 and value[:3] == alias[:3]
    else:
        safe_prefix = bool(value) and value[0] == alias[0]
    return safe_prefix and is_one_edit_apart(value, alias)


def _replace_fuzzy_token_aliases(text: str) -> str:
    result = []
    for token in text.split():
        result.append(
            next(
                (
                    canonical
                    for alias, canonical in _FUZZY_TOKEN_ALIASES.items()
                    if _matches_fuzzy_alias(token, alias)
                ),
                token,
            )
        )
    return " ".join(result)


def _remove_tool_compatibility(text: str) -> str:
    for pattern, replacement in _TOOL_COMPATIBILITY_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def normalize_text(text: str) -> str:
    text = _base_normalize(text)
    text = re.sub(r"\bполтора\b", "1.5", text)
    text = re.sub(r"\bметров(?:ая|ый|ую|ые)\b", "1000 мм", text)
    text = _replace_fuzzy_token_aliases(text)
    for pattern, replacement in _DOMAIN_ALIASES:
        text = pattern.sub(replacement, text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_code(value: str) -> str:
    normalized = value.lower().replace(" ", "").replace("-", "")
    return re.sub(r"(?:li|ли|л)$", "l", normalized)


def code_variants(code: str) -> frozenset[str]:
    """Латинские прочтения кода, записанного кириллицей.

    Кириллица встречается по обе стороны: покупатель пишет `т30` или `рн2`,
    а в каталоге есть `ТР-750` и `АРС-230`. Одной таблицей это не покрыть:
    в `р120` буква `р` — гомоглиф латинской `p`, а в `ТР-750` — транскрипция
    `r`. Поэтому код разворачивается в набор прочтений, а сравнение кодов
    считается успешным при непустом пересечении наборов.
    """
    if not _CYRILLIC_RE.search(code):
        return frozenset({code})

    variants = {code}
    if all(character in _HOMOGLYPHS for character in code if _CYRILLIC_RE.match(character)):
        variants.add("".join(_HOMOGLYPHS.get(character, character) for character in code))

    transcriptions = [""]
    for character in code:
        options = _TRANSCRIPTIONS.get(character, (character,))
        transcriptions = [
            prefix + option for prefix in transcriptions[:_MAX_CODE_VARIANTS] for option in options
        ]
    variants.update(transcriptions[:_MAX_CODE_VARIANTS])
    return frozenset(variants)


def _extract_codes(normalized: str) -> frozenset[str]:
    codes = {_normalize_code(match.group()) for match in _CODE_RE.finditer(normalized)}
    codes.update(f"m{match.group(1)}" for match in _THREAD_CODE_RE.finditer(normalized))
    codes.update(match.group().lower() for match in _STANDALONE_CODE_RE.finditer(normalized))
    return frozenset(codes)


def _extract_qualifiers(normalized: str) -> frozenset[str]:
    without_compatibility = _remove_tool_compatibility(normalized)
    return frozenset(
        qualifier
        for pattern, qualifier in _QUALIFIER_PATTERNS
        if pattern.search(without_compatibility)
    )


def _extract_dimensions(normalized: str) -> tuple[tuple[float, ...], ...]:
    result = [
        tuple(float(value) for value in match.groups() if value is not None)
        for match in _EXPLICIT_DIMENSION_RE.finditer(normalized)
    ]
    for match in _ON_DIMENSION_RE.finditer(normalized):
        if not re.search(r"\bзуб", normalized[match.end() : match.end() + 20]):
            result.append((float(match.group(1)), float(match.group(2))))
    return tuple(dict.fromkeys(result))


def _extract_quantities(normalized: str) -> tuple[tuple[float, str], ...]:
    matches = [*_NUMBER_WITH_UNIT_RE.findall(normalized), *_X_NUMBER_WITH_UNIT_RE.findall(normalized)]
    matches.extend(
        (value, unit)
        for start, end, unit in _RANGE_WITH_UNIT_RE.findall(normalized)
        for value in (start, end)
    )
    return tuple(dict.fromkeys((float(value), unit) for value, unit in matches))


def _extract_numbers(normalized: str) -> frozenset[float]:
    ignored = [
        match.span("value")
        for pattern in (*_ORDER_AMOUNT_PATTERNS, *_PACK_COUNT_PATTERNS)
        for match in pattern.finditer(normalized)
    ]
    return frozenset(
        float(match.group())
        for match in re.finditer(r"\d+(?:\.\d+)?", normalized)
        if not any(match.start() >= start and match.end() <= end for start, end in ignored)
    )


def _extract_pack_count(normalized: str) -> int | None:
    for pattern in _PACK_COUNT_PATTERNS:
        if match := pattern.search(normalized):
            value = match.group("value").lstrip("0") or "0"
            # Python 3.11+ отказывается парсить очень длинные числа, а такой
            # "размер упаковки" всё равно недостижим: -1 не совпадёт ни с чем.
            return -1 if len(value) > 9 else int(value)
    return None


def _extract_unit_hint(normalized: str) -> str | None:
    return next(
        (unit for pattern, unit in _UNIT_HINTS if pattern.search(normalized)),
        None,
    )


def extract_codes(text: str) -> frozenset[str]:
    return _extract_codes(normalize_text(text))


def extract_qualifiers(text: str) -> frozenset[str]:
    return _extract_qualifiers(normalize_text(text))


def extract_dimensions(text: str) -> tuple[tuple[float, ...], ...]:
    return _extract_dimensions(normalize_text(text))


def extract_quantities(text: str) -> tuple[tuple[float, str], ...]:
    return _extract_quantities(normalize_text(text))


def extract_numbers(text: str) -> frozenset[float]:
    return _extract_numbers(normalize_text(text))


def extract_pack_count(text: str) -> int | None:
    return _extract_pack_count(normalize_text(text))


def extract_unit_hint(text: str) -> str | None:
    return _extract_unit_hint(normalize_text(text))


def _is_explicitly_non_product(normalized: str) -> bool:
    return any(pattern.search(normalized) for pattern in _NON_PRODUCT_PATTERNS)


def is_explicitly_non_product(text: str) -> bool:
    return _is_explicitly_non_product(normalize_text(text))


def contains_negative_number(text: str) -> bool:
    normalized = _base_normalize(text.replace("−", "-"))
    normalized = _CODE_RE.sub(" ", normalized)
    normalized = re.sub(
        r"(?<![\w.])\d+(?:[.,]\d+)?\s*-\s*\d+(?:[.,]\d+)?",
        " ",
        normalized,
    )
    return _NEGATIVE_NUMBER_RE.search(normalized) is not None


def _retrieval_text(normalized: str) -> str:
    text = _remove_tool_compatibility(normalized)
    for pattern in _FREE_TEXT_NOISE_PATTERNS:
        text = pattern.sub(" ", text)
    tokens = _QUERY_NOISE_RE.sub(" ", text).split()
    # `лист` — это и товар (`Лист гипсокартонный`), и единица продажи
    # (`шкурка p120 лист`). Во втором случае слово только мешает: каталог
    # знает его как название семейства и увёл бы запрос к гипсокартону.
    if len(tokens) > 1 and tokens[0] != "лист" and "гипсокартонный" not in tokens:
        tokens = [token for token in tokens if token != "лист"]
    return " ".join(tokens)


def _lexical_text(retrieval: str) -> str:
    tokens = retrieval.split()
    # Отдельно стоящий `гкл` — это лист гипсокартона, а не свойство:
    # без явного семейства запрос ушёл бы к саморезам по гипсокартону.
    if tokens and tokens[0] == "гипсокартонный" and "лист" not in tokens:
        retrieval = f"лист {retrieval}"
    # Назначение (`по дереву`, `по металлу`) уже проверяется как qualifier,
    # и как опорное слово оно только вредит: иначе запрос `бетон 10 мм`
    # притворяется товаром за счёт названия `Сверло по бетону 10 мм`.
    text = retrieval
    for pattern in _APPLICATION_PHRASES:
        text = pattern.sub(" ", text)
    text = re.sub(r"\b[a-zа-я]+-?\d[\w.-]*\b", " ", text)
    text = re.sub(r"(?<!\w)\d+(?:\.\d+)?(?:x\d+(?:\.\d+)?)+(?!\w)", " ", text)
    text = re.sub(r"\d+(?:\.\d+)?", " ", text)
    text = re.sub(r"\b(?:мм|см|м|вт|дж|г|мл|л|на)\b", " ", text)
    text = _LEXICAL_ORDER_NOISE_RE.sub(" ", text)
    return re.sub(r"\s+", " ", re.sub(r"[^a-zа-я]+", " ", text)).strip()


def retrieval_text(text: str) -> str:
    return _retrieval_text(normalize_text(text))


def lexical_text(text: str) -> str:
    return _lexical_text(retrieval_text(text))


def parse_query(text: str) -> QueryFeatures:
    normalized = normalize_text(text)
    retrieval = _retrieval_text(normalized)
    return QueryFeatures(
        normalized=normalized,
        retrieval=retrieval,
        lexical=_lexical_text(retrieval),
        dimensions=_extract_dimensions(normalized),
        codes=_extract_codes(normalized),
        qualifiers=_extract_qualifiers(normalized),
        quantities=_extract_quantities(normalized),
        numbers=_extract_numbers(normalized),
        pack_count=_extract_pack_count(normalized),
        unit_hint=_extract_unit_hint(normalized),
        non_product=_is_explicitly_non_product(normalized),
    )


def parse_item(name: str) -> ItemFeatures:
    normalized = normalize_text(name)
    codes = _extract_codes(normalized)
    return ItemFeatures(
        normalized=normalized,
        lexical=_lexical_text(_retrieval_text(normalized)),
        dimensions=_extract_dimensions(normalized),
        codes=codes,
        code_variants=frozenset().union(*(code_variants(code) for code in codes)) if codes else frozenset(),
        qualifiers=_extract_qualifiers(normalized),
        quantities=_extract_quantities(normalized),
        numbers=_extract_numbers(normalized),
        pack_count=_extract_pack_count(normalized),
    )
