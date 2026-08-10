from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from sklearn.feature_extraction.text import TfidfVectorizer

from app.catalog import Catalog, CatalogItem
from app.normalization import (
    QueryFeatures,
    code_variants,
    contains_negative_number,
    is_one_edit_apart,
    parse_query,
    token_key,
)
from app.schemas import Candidate, MatchResult


@dataclass(frozen=True, slots=True)
class _Ranked:
    item: CatalogItem
    score: float
    noise_tokens: int


class ProductMatcher:
    """Conservative offline matcher: char n-gram retrieval + hard constraints."""

    MATCH_THRESHOLD = 0.46
    AMBIGUOUS_THRESHOLD = 0.18
    MATCH_MARGIN = 0.06
    AMBIGUOUS_WINDOW = 0.10
    MAX_AMBIGUOUS_CANDIDATES = 3
    LEXICAL_TOKEN_SIMILARITY_THRESHOLD = 0.76
    MIN_FUZZY_TOKEN_LENGTH = 4
    NOISE_TOKEN_PENALTY = 0.92
    HEAD_NOISE_PENALTY = 0.6

    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog
        self.vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            lowercase=False,
            sublinear_tf=True,
            norm="l2",
            min_df=1,
        )
        self.catalog_matrix = self.vectorizer.fit_transform(
            item.normalized_name for item in catalog.items
        ).tocsr()
        self.catalog_lexical_tokens = [
            tuple(token for token in item.lexical_name.split() if len(token) >= 3)
            for item in catalog.items
        ]
        self.catalog_family_tokens = tuple(
            dict.fromkeys(tokens[0] for tokens in self.catalog_lexical_tokens if tokens)
        )
        self.catalog_vocabulary = {
            token_key(token)
            for tokens in self.catalog_lexical_tokens
            for token in tokens
        }
        self.families_by_key = {
            token_key(family): family
            for family in self.catalog_family_tokens
        }
        self.catalog_codes_by_variant: dict[str, str] = {}
        for item in catalog.items:
            for code in item.codes:
                for variant in code_variants(code):
                    self.catalog_codes_by_variant.setdefault(variant, code)

    def match_many(self, messages: list[str]) -> list[MatchResult]:
        return [self.match(message) for message in messages]

    def match(self, message: str) -> MatchResult:
        if not message.strip() or contains_negative_number(message):
            return self._not_found(message)

        features = parse_query(message)
        if len(features.normalized) < 2:
            return self._not_found(message)

        # Вопрос про доставку или возврат отсекаем, только если товар не назван:
        # `когда доставите кабель?` - не заказ, а `кабель ввгнг 3х1.5 с
        # доставкой` - вполне.
        if features.non_product and not self._names_a_product(features):
            return self._not_found(message)

        lexical_tokens = tuple(
            token for token in features.lexical.split() if len(token) >= 3
        )
        family_match = self._find_explicit_family(lexical_tokens)
        explicit_family = family_match[1] if family_match else None
        query_text = self._anchor_codes(features.retrieval, features.codes)
        anchored_tokens = lexical_tokens

        if family_match is not None:
            query_family, catalog_family = family_match
            if query_family != catalog_family:
                query_text = f"{query_text} {catalog_family}"
                anchored_tokens = tuple(
                    catalog_family if token == query_family else token
                    for token in lexical_tokens
                )

        similarities = (self.catalog_matrix @ self.vectorizer.transform([query_text]).T).toarray().ravel()
        if not similarities.size or float(similarities.max()) < self.AMBIGUOUS_THRESHOLD:
            return self._not_found(message)

        ranked = self._rank_candidates(
            similarities,
            lexical_tokens,
            anchored_tokens,
            explicit_family,
            features,
        )
        if not ranked or ranked[0].score < self.AMBIGUOUS_THRESHOLD:
            return self._not_found(message)

        top = ranked[0]
        has_constraints = bool(
            features.dimensions
            or features.codes
            or features.qualifiers
            or features.quantities
            or features.numbers
            or features.pack_count is not None
            or features.unit_hint is not None
        )
        if (
            explicit_family is not None
            and len(anchored_tokens) - top.noise_tokens == 1
            and not has_constraints
            and len(ranked) >= 2
        ):
            return self._ambiguous(message, ranked[: self.MAX_AMBIGUOUS_CANDIDATES])

        exact_name_is_unique = not any(
            query_text == candidate.item.normalized_name for candidate in ranked[1:]
        )
        if query_text == top.item.normalized_name and exact_name_is_unique:
            return self._matched(message, top)

        second_score = ranked[1].score if len(ranked) > 1 else 0.0
        if (
            top.score >= self.MATCH_THRESHOLD
            and top.score - second_score >= self.MATCH_MARGIN
        ):
            if not self._competes_by_unasked_application(ranked, features):
                return self._matched(message, top)
            # Отрыв лидера ничего не доказывает, поэтому окно близости здесь
            # не применяем: показываем сами варианты назначения.
            return self._ambiguous(message, ranked[: self.MAX_AMBIGUOUS_CANDIDATES])

        candidates = [
            candidate
            for candidate in ranked
            if candidate.score >= self.AMBIGUOUS_THRESHOLD
            and candidate.score >= top.score - self.AMBIGUOUS_WINDOW
        ][: self.MAX_AMBIGUOUS_CANDIDATES]
        return self._ambiguous(message, candidates) if len(candidates) >= 2 else self._not_found(message)

    def _rank_candidates(
        self,
        similarities,
        lexical_tokens: tuple[str, ...],
        anchored_tokens: tuple[str, ...],
        explicit_family: str | None,
        features: QueryFeatures,
    ) -> list[_Ranked]:
        ranked = []
        for index, raw_score in enumerate(similarities):
            text_score = float(raw_score)
            if text_score < self.AMBIGUOUS_THRESHOLD:
                continue

            item = self.catalog.items[index]
            item_tokens = self.catalog_lexical_tokens[index]
            noise_tokens = 0
            head_conflict = False
            if lexical_tokens:
                if explicit_family is not None:
                    if not item_tokens or not self._tokens_are_similar(explicit_family, item_tokens[0]):
                        continue
                else:
                    first_key = token_key(lexical_tokens[0])
                    if not any(first_key == token_key(token) for token in item_tokens):
                        continue
                counted = self._count_noise_tokens(
                    anchored_tokens, item_tokens, explicit_family, bool(features.codes)
                )
                if counted is None:
                    continue
                noise_tokens, head_conflict = counted

            if self._hard_compatible(item, features):
                score = (
                    self._rerank(text_score, features)
                    * self.NOISE_TOKEN_PENALTY**noise_tokens
                    * (self.HEAD_NOISE_PENALTY if head_conflict else 1.0)
                )
                ranked.append(_Ranked(item, score, noise_tokens))
        return sorted(ranked, key=lambda candidate: candidate.score, reverse=True)

    @staticmethod
    def _names_a_product(features: QueryFeatures) -> bool:
        return bool(features.dimensions or features.codes or features.quantities)

    @staticmethod
    def _competes_by_unasked_application(
        ranked: list[_Ranked],
        features: QueryFeatures,
    ) -> bool:
        """Спорят ли лидер и конкурент назначением, о котором не спрашивали.

        `сверло 10 мм` одинаково описывает сверло по дереву, по бетону и по
        металлу. Отрыв лидера здесь создаёт не запрос, а частотность слов в
        каталоге, поэтому честнее вернуть кандидатов, чем угадать назначение
        за покупателя.
        """
        if len(ranked) < 2 or any(
            qualifier.startswith("application:") for qualifier in features.qualifiers
        ):
            return False

        applications = [
            {
                qualifier
                for qualifier in candidate.item.qualifiers
                if qualifier.startswith("application:")
            }
            for candidate in ranked[:2]
        ]
        return all(applications) and applications[0] != applications[1]

    def _anchor_codes(self, query_text: str, codes: frozenset[str]) -> str:
        # Кириллическая запись кода (`т30`, `рн2`) не даёт общих n-грамм с
        # каталожной (`t30`, `ph2`), поэтому дописываем каталожное написание.
        catalog_codes = []
        for code in sorted(codes):
            if code in self.catalog_codes_by_variant:
                continue
            catalog_code = next(
                (
                    self.catalog_codes_by_variant[variant]
                    for variant in sorted(code_variants(code))
                    if variant in self.catalog_codes_by_variant
                ),
                None,
            )
            if catalog_code is not None:
                catalog_codes.append(catalog_code)
        return " ".join([query_text, *catalog_codes]) if catalog_codes else query_text

    def _find_explicit_family(
        self,
        query_tokens: tuple[str, ...],
    ) -> tuple[str, str] | None:
        for query in query_tokens:
            if family := self.families_by_key.get(token_key(query)):
                return query, family

        for query in query_tokens:
            for family in self.catalog_family_tokens:
                if self._tokens_are_similar(query, family):
                    return query, family
        return None

    def _count_noise_tokens(
        self,
        query_tokens: tuple[str, ...],
        item_tokens: tuple[str, ...],
        family: str | None,
        code_pinned: bool,
    ) -> tuple[int, bool] | None:
        """Необъяснённые слова запроса: сколько их и есть ли среди них вершина.

        Требовать, чтобы каждое слово запроса нашлось в названии товара,
        нельзя: покупатель пишет живым языком и добавляет `самовывоз`,
        `в бухте`, `спасибо`. Но и игнорировать всё подряд опасно.

        Возвращает `None`, если слово прямо противоречит товару, иначе —
        число необъяснённых слов и признак того, что одно из них стоит перед
        названием семейства.
        """
        anchor = query_tokens.index(family) if family in query_tokens else 0
        noise = 0
        head_conflict = False
        for position, token in enumerate(query_tokens):
            if any(self._tokens_are_similar(token, item) for item in item_tokens):
                continue
            # Каталог знает это слово, но у данного товара его нет — значит,
            # оно товару противоречит (`саморез мебельный`, `уровень лазерный`).
            if token_key(token) in self.catalog_vocabulary:
                return None
            # Сразу справа от семейства стоит уточнение типа (`дюбель
            # бабочка`, `диск алмазный`). Исключение — названная маркировка:
            # она определяет товар точнее любого слова (`отвертка PH2`).
            if position == anchor + 1 and not code_pinned:
                return None
            # Слева от семейства стоит либо вежливый оборот (`посмотрите
            # дрель`), либо вершина словосочетания (`унитаз подвесной`,
            # `напильник круглый`). Отличить их без морфологии нельзя,
            # поэтому кандидата не отбрасываем, но сильно штрафуем: пережить
            # штраф может только совпадение с прочими доказательствами.
            head_conflict = head_conflict or position < anchor
            noise += 1
        return noise, head_conflict

    @classmethod
    def _tokens_are_similar(cls, left: str, right: str) -> bool:
        left_key = token_key(left)
        right_key = token_key(right)
        if left_key == right_key:
            return True
        # Для коротких основ одна правка меняет слишком многое: иначе `дела`
        # сойдёт за опечатку в `дрель`.
        if min(len(left_key), len(right_key)) < cls.MIN_FUZZY_TOKEN_LENGTH:
            return False
        if left_key[:1] == right_key[:1] and is_one_edit_apart(left_key, right_key):
            return True
        if (
            len(left_key) >= 4
            and len(right_key) >= 4
            and left_key[:3] != right_key[:3]
        ):
            return False
        return SequenceMatcher(None, left_key, right_key).ratio() >= cls.LEXICAL_TOKEN_SIMILARITY_THRESHOLD

    @staticmethod
    def _hard_compatible(item: CatalogItem, query: QueryFeatures) -> bool:
        if query.unit_hint is not None and item.unit != query.unit_hint:
            return False
        if query.pack_count is not None and item.pack_count != query.pack_count:
            return False
        if any(
            not (code_variants(code) & item.code_variants) for code in query.codes
        ):
            return False

        query_colors = {value for value in query.qualifiers if value.startswith("color:")}
        item_colors = {value for value in item.qualifiers if value.startswith("color:")}
        if query_colors and query_colors != item_colors:
            return False
        if not (query.qualifiers - query_colors).issubset(item.qualifiers):
            return False

        quantity_values = {value for value, _ in query.quantities}
        if not (query.numbers - quantity_values).issubset(item.numbers):
            return False
        if any(
            not any(ProductMatcher._dimension_prefix_match(requested, actual) for actual in item.dimensions)
            for requested in query.dimensions
        ):
            return False

        dimension_values = {value for dimension in query.dimensions for value in dimension}
        item_quantities = set(item.quantities)
        item_dimension_values = {value for dimension in item.dimensions for value in dimension}
        item_lengths_mm = {
            converted
            for value, unit in item.quantities
            if (converted := ProductMatcher._length_in_mm(value, unit)) is not None
        }

        for value, unit in query.quantities:
            if value in dimension_values:
                if unit == "мм":
                    continue
                return False
            if unit == item.unit or (value, unit) in item_quantities:
                continue
            length_mm = ProductMatcher._length_in_mm(value, unit)
            if length_mm is not None and (
                length_mm in item_dimension_values or length_mm in item_lengths_mm
            ):
                continue
            return False
        return True

    @staticmethod
    def _length_in_mm(value: float, unit: str) -> float | None:
        factor = {"мм": 1.0, "см": 10.0, "м": 1000.0}.get(unit)
        return value * factor if factor is not None else None

    @staticmethod
    def _dimension_prefix_match(
        requested: tuple[float, ...],
        actual: tuple[float, ...],
    ) -> bool:
        return len(requested) <= len(actual) and requested == actual[: len(requested)]

    @staticmethod
    def _rerank(text_score: float, query: QueryFeatures) -> float:
        dimension_values = {value for dimension in query.dimensions for value in dimension}
        has_independent_quantity = any(
            value not in dimension_values for value, _ in query.quantities
        )
        structural_strength = sum(
            bonus
            for condition, bonus in (
                (bool(query.dimensions), 0.30),
                (bool(query.codes), 0.25),
                (bool(query.qualifiers), 0.12),
                (has_independent_quantity, 0.15),
                (
                    bool(query.numbers)
                    and not (query.dimensions or query.codes or has_independent_quantity),
                    0.16,
                ),
                (query.pack_count is not None, 0.15),
                (query.unit_hint is not None, 0.08),
            )
            if condition
        )
        strength = min(structural_strength, 0.55)
        return text_score + (1.0 - text_score) * strength

    @staticmethod
    def _candidate(result: _Ranked) -> Candidate:
        return Candidate(sku=result.item.sku, confidence=round(result.score, 3))

    @classmethod
    def _matched(cls, message: str, result: _Ranked) -> MatchResult:
        return MatchResult(message=message, status="matched", candidates=[cls._candidate(result)])

    @classmethod
    def _ambiguous(cls, message: str, results: list[_Ranked]) -> MatchResult:
        return MatchResult(
            message=message,
            status="ambiguous",
            candidates=[cls._candidate(result) for result in results],
        )

    @staticmethod
    def _not_found(message: str) -> MatchResult:
        return MatchResult(message=message, status="not_found", candidates=[])
