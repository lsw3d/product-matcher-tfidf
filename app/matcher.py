from __future__ import annotations

from dataclasses import dataclass

from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer

from app.catalog import Catalog, CatalogItem
from app.normalization import QueryFeatures, is_explicitly_non_product, parse_query, retrieval_text
from app.schemas import Candidate, MatchResult


@dataclass(frozen=True, slots=True)
class _Ranked:
    item: CatalogItem
    text_score: float
    score: float


class ProductMatcher:
    MATCH_THRESHOLD = 0.46
    AMBIGUOUS_THRESHOLD = 0.18
    MATCH_MARGIN = 0.06
    AMBIGUOUS_WINDOW = 0.10
    MAX_AMBIGUOUS_CANDIDATES = 3

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
        self.catalog_matrix: csr_matrix = self.vectorizer.fit_transform(
            [item.normalized_name for item in catalog.items]
        ).tocsr()

    def match(self, message: str) -> MatchResult:
        if not message.strip() or is_explicitly_non_product(message):
            return self._not_found(message)

        features = parse_query(message)
        if len(features.normalized) < 2:
            return self._not_found(message)

        query_vector = self.vectorizer.transform([retrieval_text(message)])
        similarities = (self.catalog_matrix @ query_vector.T).toarray().ravel()

        if similarities.size == 0 or float(similarities.max()) < self.AMBIGUOUS_THRESHOLD:
            return self._not_found(message)

        ranked: list[_Ranked] = []
        for idx, text_score_raw in enumerate(similarities):
            item = self.catalog.items[idx]
            text_score = float(text_score_raw)
            if text_score < self.AMBIGUOUS_THRESHOLD:
                continue
            if not self._hard_compatible(item, features):
                continue
            ranked.append(
                _Ranked(
                    item=item,
                    text_score=text_score,
                    score=self._rerank(text_score, item, features),
                )
            )

        ranked.sort(key=lambda result: result.score, reverse=True)
        if not ranked or ranked[0].score < self.AMBIGUOUS_THRESHOLD:
            return self._not_found(message)

        top = ranked[0]
        second = ranked[1].score if len(ranked) > 1 else 0.0
        margin = top.score - second

        if top.score >= self.MATCH_THRESHOLD and margin >= self.MATCH_MARGIN:
            return MatchResult(
                message=message,
                status="matched",
                candidates=[self._candidate(top)],
            )

        candidates = [
            result
            for result in ranked
            if result.score >= self.AMBIGUOUS_THRESHOLD
            and result.score >= top.score - self.AMBIGUOUS_WINDOW
        ][: self.MAX_AMBIGUOUS_CANDIDATES]

        if len(candidates) >= 2:
            return MatchResult(
                message=message,
                status="ambiguous",
                candidates=[self._candidate(candidate) for candidate in candidates],
            )

        return self._not_found(message)

    def match_many(self, messages: list[str]) -> list[MatchResult]:
        return [self.match(message) for message in messages]

    @staticmethod
    def _hard_compatible(item: CatalogItem, query: QueryFeatures) -> bool:
        if query.unit_hint is not None and item.unit != query.unit_hint:
            return False

        if query.pack_count is not None and item.pack_count != query.pack_count:
            return False

        if query.codes and not query.codes.issubset(item.codes):
            return False

        if query.numbers and not query.numbers.issubset(item.numbers):
            return False

        for requested in query.dimensions:
            if not any(ProductMatcher._dimension_prefix_match(requested, actual) for actual in item.dimensions):
                return False

        dimension_values = {value for dimension in query.dimensions for value in dimension}
        item_quantity_set = set(item.quantities)
        for value, unit in query.quantities:
            if value in dimension_values:
                continue
            if (value, unit) not in item_quantity_set:
                return False

        return True

    @staticmethod
    def _dimension_prefix_match(requested: tuple[float, ...], actual: tuple[float, ...]) -> bool:
        if len(requested) > len(actual):
            return False
        return requested == actual[: len(requested)]

    @staticmethod
    def _rerank(text_score: float, item: CatalogItem, query: QueryFeatures) -> float:
        score = text_score

        if query.dimensions:
            score += 0.16
        if query.codes:
            score += 0.14
        if query.quantities:
            score += 0.08
        if query.numbers:
            score += 0.08
        if query.pack_count is not None:
            score += 0.08
        if query.unit_hint is not None:
            score += 0.04

        return score

    @staticmethod
    def _candidate(result: _Ranked) -> Candidate:
        return Candidate(sku=result.item.sku, confidence=round(min(1.0, result.score), 3))

    @staticmethod
    def _not_found(message: str) -> MatchResult:
        return MatchResult(message=message, status="not_found", candidates=[])
