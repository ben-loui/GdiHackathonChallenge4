"""Search/query API that can be imported from CLI, MCP, FastAPI etc."""
from __future__ import annotations
import re
from collections import defaultdict

from .index import document_text, es_search


class LocalMatcher:
    """Deterministic BM25-like lexical fallback (TF-IDF word + character ngrams).

    Does *not* pretend to be semantic search; use ES + embedding mode for that.
    """
    def __init__(self, docs: list[dict]):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.docs = [d for d in docs if d.get("behoerdenkategorien")]
        if not self.docs:
            raise ValueError("Keine kategorisierten Leistungen in den Quelldaten")
        corpus = [document_text(d) for d in self.docs]
        self.char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1,
                                    sublinear_tf=True, max_features=150000)
        self.word = TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=1,
                                    sublinear_tf=True, max_features=100000)
        self.char_matrix = self.char.fit_transform(corpus)
        self.word_matrix = self.word.fit_transform(corpus)

    def search(self, query: str, size: int = 12) -> list[tuple[dict, float]]:
        import numpy as np
        a = (self.char_matrix @ self.char.transform([query]).T).toarray().ravel()
        b = (self.word_matrix @ self.word.transform([query]).T).toarray().ravel()
        scores = .6 * a + .4 * b
        return [(self.docs[int(i)], round(float(scores[int(i)]), 6)) for i in
                np.argsort(-scores)[:size] if scores[int(i)] >= 0.035]


def match_authority(query: str, *, local: LocalMatcher | None = None, backend: str = "local",
                    es_url: str = "http://localhost:9200", es_index: str = "fim-authorities-v1",
                    semantic: bool = False, embedding_model: str = "intfloat/multilingual-e5-small",
                    top_k: int = 5, enrich=None) -> dict:
    """Public reusable entry point with optional PVOG evidence enrichment.

    Citizen queries are only sent to the search backend, not to PVOG.

    Scores are *ranking scores*, not calibrated probabilities.
    """
    query = re.sub(r"\s+", " ", query).strip()
    if not query or len(query) < 4:
        return {"status": "ungueltige_anfrage", "behoerdenkategorie": None, "score": None, "alternativen": [], "leistungen": []}
    if backend == "local":
        if local is None:
            raise ValueError("LocalMatcher muss für Backend 'local' übergeben werden")
        rows = local.search(query, size=max(top_k * 8, 40))
        min_score = .09
    elif backend == "elasticsearch":
        rows = es_search(query, url=es_url, index_name=es_index, semantic=semantic,
                         model_name=embedding_model, size=max(top_k * 8, 40))
        # ES RRF scores (~0.016 per retriever); threshold intentionally conservative.
        min_score = .013 if semantic else .012
    else:
        raise ValueError(f"Unbekanntes Backend: {backend}")
    if enrich and rows:
        rows = enrich(rows)
    relative_cutoff = (rows[0][1] * 0.58) if rows and backend == "local" else 0.0
    rows = [(doc, score) for doc, score in rows if score >= max(min_score, relative_cutoff)]
    if not rows:
        return {"status": "keine_zuordnung", "behoerdenkategorie": None, "score": None,
                "alternativen": [], "leistungen": [], "suchmodus": "hybrid" if semantic else "lexikalisch"}
    cat_scores: dict[str, float] = defaultdict(float)
    cat_best: dict[str, tuple[dict, float]] = {}
    for rank, (doc, score) in enumerate(rows):
        # Preserve ambiguity, but avoid overly broad documents dominating all categories.
        for cat in doc["behoerdenkategorien"]:
            weighted = float(score) * (0.6 if len(doc["behoerdenkategorien"]) > 1 else 1.0)
            cat_scores[cat] += weighted / (1 + .35 * rank)
            if cat not in cat_best or score > cat_best[cat][1]:
                cat_best[cat] = (doc, score)
    if not cat_scores:
        services = [{"id": doc["id"], "titel": doc["titel"], "leistungsschluessel": doc.get("leistungsschluessel"),
                     "score": round(float(score), 5), "behoerdenkategorien": [], "mapping_status": doc.get("mapping_status", "unbekannt"),
                     "quelle": doc.get("quelle", "fim"), "zustaendige_stelle_original": doc.get("zustaendige_stelle_original", []),
                     "zuordnung_belege": doc.get("zuordnung_belege", [])}
                    for doc, score in rows[:top_k]]
        return {"status": "behoerdenart_in_fim_nicht_ermittelbar", "behoerdenkategorie": None, "score": None,
                "top_kategorie": None, "alternativen": [], "leistungen": services,
                "suchmodus": "hybrid" if semantic else "lexikalisch"}
    ranked = sorted(cat_scores.items(), key=lambda x: x[1], reverse=True)
    best_cat, best_score = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0
    # Soft ambiguity criterion; never return a guaranteed/legal routing claim.
    ambiguous = second >= .86 * best_score
    if len(cat_best[best_cat][0]["behoerdenkategorien"]) > 1 and second >= .70 * best_score:
        ambiguous = True
    # If the best-scoring FIM service has no authority field, do not treat a
    # lower-ranked, differently named service as a verified authority.
    if not rows[0][0].get("behoerdenkategorien"):
        ambiguous = True
    status = "mehrdeutig" if ambiguous else "vorschlag"
    alternatives = [{"id": cat, "score": round(val, 5)} for cat, val in ranked[1:4]]
    services = [{"id": doc["id"], "titel": doc["titel"], "leistungsschluessel": doc.get("leistungsschluessel"),
                 "score": round(float(score), 5), "behoerdenkategorien": doc["behoerdenkategorien"],
                 "mapping_status": doc["mapping_status"], "quelle": doc["quelle"],
                 "zustaendige_stelle_original": doc.get("zustaendige_stelle_original", []),
                     "zuordnung_belege": doc.get("zuordnung_belege", [])}
                for doc, score in rows[:top_k]]
    return {"status": status, "behoerdenkategorie": best_cat if not ambiguous else None,
            "score": round(float(best_score), 5), "top_kategorie": best_cat, "alternativen": alternatives, "leistungen": services,
            "suchmodus": "hybrid" if semantic else "lexikalisch",
            "hinweis": "Scores sind relative Ranking-Werte, keine Zuverlässigkeitsprozente."}


def compact_result(result: dict) -> dict:
    """Public, location-independent result: one category and its ranking score.

    Full evidence stays in ``match_authority`` for troubleshooting; it is not
    serialized by default in the user-facing CLI or machine-readable output.
    A score is only exposed when the matcher selected a category.
    """
    category = result.get("behoerdenkategorie")
    score = result.get("score") if category is not None else None
    return {
        "behoerdenkategorie": category,
        "score": round(float(score), 5) if isinstance(score, (int, float)) else None,
    }
