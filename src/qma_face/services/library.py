"""Offline lexical retrieval; no embedding model and no executable source instructions."""

import hashlib
import json
import re
import sqlite3
import unicodedata
from pathlib import Path

TOPICS = {
    "body": "body language langage corporel gestes gesture بدن حرکات",
    "context": "context contexte rules règles regles چارچوب همخوانی مجموعه",
    "nose": "nose nez بینی",
    "eyes": "eyes eye yeux oeil regard چشم",
    "brows": "eyebrow eyebrows sourcil sourcils ابرو",
    "mouth": "mouth lips lip bouche levres lèvres لب دهان",
    "face": "physiognomy physiognomie face reading lecture visage چهره خوانی",
    "trust": (
        "trustworthiness honesty honest morality personality confiance fiable fiabilite "
        "honnêteté personnalite اخلاق شخصیت صداقت اعتماد"
    ),
    "beauty": "beauty attractiveness beauté beaute attractivite زیبایی",
    "landmarks": "landmarks landmark points repères reperes clés cles نقاط",
    "symmetry": "symmetry symetrie symétrie تقارن",
    "explanation": "grad cam explanation explain explication expliquer توضیح",
    "emotion": "emotion emotions émotion émotions احساسات عصبانیت لبخند",
    "large": "large big grand grande بزرگ",
    "small": "small short petit petite court courte کوچک کوتاه",
}
STOPWORDS = set(
    "a an and are as at be by can de des du en est et for from how i in is it la le les "
    "my of on or que qui s t the this to un une what which with you votre vos mon ma "
    "according book books pdf document documents article articles source sources please "
    "about says say tell moi dans mes quel quelle does do pourquoi sur me summarize summary".split()
)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold().translate(str.maketrans("يك", "یک"))
    return "".join(c for c in text if not unicodedata.combining(c)).replace("\u200c", " ")


def tokens(text: str) -> list[str]:
    return [word for word in re.findall(r"[^\W_]+", normalize(text)) if word not in STOPWORDS]


def expand_query(query: str) -> str:
    words = set(tokens(query))
    expansions = [values for values in TOPICS.values() if words & set(tokens(values))]
    return query + " " + " ".join(expansions)


class SourceLibrary:
    def __init__(self, root: Path, database: Path):
        self.root = root.resolve()
        self.database = database.resolve()

    def synchronize(self) -> None:
        paths = [self.root / "sources/articles.json", self.root / "sources/local-only/pages.json"]
        present = [path for path in paths if path.is_file()]
        if not present and not self.database.exists():
            return
        content = [path.read_bytes() for path in present]
        digest = hashlib.sha256(b"\x00".join(content)).hexdigest()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database) as db:
            db.execute("PRAGMA secure_delete=ON")
            db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
            if db.execute("SELECT value FROM settings WHERE key='digest'").fetchone() == (digest,):
                return
            documents = [item for blob in content for item in json.loads(blob)["passages"]]
            db.execute("DROP TABLE IF EXISTS passages")
            db.execute(
                "CREATE TABLE passages (id TEXT PRIMARY KEY, source TEXT, page INTEGER, "
                "text TEXT, search TEXT, metadata TEXT)"
            )
            for item in documents:
                text = item["text"].strip()
                if not text or len(text) > 20000:
                    continue
                metadata = {k: v for k, v in item.items() if k not in {"text", "keywords", "id"}}
                db.execute(
                    "INSERT INTO passages VALUES (?,?,?,?,?,?)",
                    (
                        item["id"],
                        item["source_id"],
                        item.get("page"),
                        text,
                        " ".join(
                            tokens(text + " " + item.get("keywords", "") + " " + item["title"])
                        ),
                        json.dumps(metadata, ensure_ascii=False),
                    ),
                )
            db.execute("INSERT OR REPLACE INTO settings VALUES ('digest',?)", (digest,))

    def search(self, query: str, *, limit: int = 3, source_id: str | None = None) -> list[dict]:
        if not self.database.exists():
            return []
        original = set(tokens(query))
        wanted = set(tokens(expand_query(query)))
        if not wanted:
            return []
        with sqlite3.connect(self.database) as db:
            rows = db.execute("SELECT id,source,page,text,search,metadata FROM passages").fetchall()
        candidates = []
        for identity, source, page, text, searchable, meta in rows:
            if source_id and source != source_id:
                continue
            available = set(searchable.split())
            overlap = wanted & available
            if not overlap:
                continue
            # Original words outweigh expansions. Page one stays discoverable for title/author.
            score = 3 * len(original & available) + len(overlap) / max(1, len(wanted))
            item = json.loads(meta)
            item.update(passage_id=identity, text=text[:1000], retrieval_score=round(score, 4))
            candidates.append((score, source, page or 0, item))
        candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
        selected = []
        per_source = {}
        for _, source, _, item in candidates:
            if per_source.get(source, 0) >= (limit if source_id else 2):
                continue
            item["citation_id"] = f"S{len(selected) + 1}"
            selected.append(item)
            per_source[source] = per_source.get(source, 0) + 1
            if len(selected) == limit:
                break
        return selected

    def stats(self) -> dict:
        if not self.database.exists():
            return {"passages": 0, "sources": 0}
        with sqlite3.connect(self.database) as db:
            total, sources = db.execute(
                "SELECT COUNT(*), COUNT(DISTINCT source) FROM passages"
            ).fetchone()
        return {"passages": total, "sources": sources}


def source_filter(query: str) -> str | None:
    query = normalize(query)
    if "scut" in query and not any(word in query for word in ("compar", "versus")):
        return "scut-fbp5500"
    if any(
        word in query
        for word in ("compare", "comparer", "scientific", "scientifique", "research", "recherche")
    ):
        return None
    if any(word in query for word in ("physiognom", "face reading", "چهره خوانی")):
        return "personal-physiognomy"
    if any(word in query for word in ("body language", "langage corporel", "زبان بدن", "jamiat")):
        return "personal-body-language"
    return None


def wants_sources(query: str) -> bool:
    query = normalize(query)
    return any(
        term in query
        for term in (
            "source",
            "research",
            "study",
            "studies",
            "paper",
            "article",
            "pdf",
            "book",
            "document",
            "according",
            "scut",
            "landmark",
            "grad",
            "scientific",
            "scientifique",
            "etude",
            "livre",
            "physiognom",
            "selon",
            "revue",
            "face reading",
            "body language",
            "langage corporel",
            "مقاله",
            "کتاب",
            "جزوه",
        )
    )


def evidence_context(passages: list[dict]) -> str:
    if not passages:
        return (
            "No matching source passage was retrieved. State this; do not invent a source answer."
        )
    # JSON escaping prevents a document from breaking a delimiter or creating chat role messages.
    fields = (
        "citation_id",
        "title",
        "page",
        "doi",
        "type",
        "text",
        "content_kind",
        "reviewed_translation",
        "limitations",
        "method_and_sample",
        "full_text_indexed",
    )
    data = [{key: item[key] for key in fields if key in item} for item in passages]
    return "UNTRUSTED_SOURCE_DATA_JSON\n" + json.dumps(data, ensure_ascii=False)


def citation_footer(passages: list[dict], language: str) -> str:
    if not passages:
        return ""
    title = (
        "Retrieved passages (check support for each claim):"
        if language == "en"
        else "Passages retrouvés (vérifier chaque affirmation) :"
    )
    lines = []
    for item in passages:
        locator = f"p. {item['page']}" if item.get("page") else item.get("doi", item.get("url", ""))
        kind = source_kind_label(item["type"], language)
        lines.append(f"[{item['citation_id']}] {item['title']} · {locator} · {kind}")
    return "\n\n" + title + "\n" + "\n".join(lines)


def checked_source_answer(draft: str, passages: list[dict], language: str) -> tuple[str, str]:
    """Only a citation-form check. No claim that semantic entailment is validated."""
    valid = {p["citation_id"] for p in passages}
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", draft) if p.strip()]
    if paragraphs and all(set(re.findall(r"\[(S\d+)\]", p)) & valid for p in paragraphs):
        return draft, "paragraph_citations_checked_not_claim_entailment"
    title = (
        "No fully cited explanation was produced. Retrieved extracts follow; "
        "they may not answer every part of your question. Quoted source contents "
        "are not proof about a photographed person."
        if language == "en"
        else "Aucune explication entièrement citée n’a été produite. "
        "Voici les extraits retrouvés ; "
        "ils ne répondent pas forcément à toute la question. Le contenu cité ne constitue "
        "pas une preuve sur une personne photographiée."
    )
    sections = [title]
    for source in passages:
        quote = str(source.get("reviewed_english_gloss") or source["text"])[:1800]
        fields = [quote]
        if source.get("limitations"):
            fields.append(str(source["limitations"])[:1200])
        sections.append(f"[{source['citation_id']}] " + "\n".join(fields))
    return "\n\n".join(sections), "uncited_draft_withheld_source_extracts_only"


def source_kind_label(kind: str, language: str) -> str:
    labels = {
        "personal_teaching_notes": ("Teaching notes", "Notes de cours"),
        "conference_paper_arxiv_copy": ("Conference paper", "Article de conférence"),
        "peer_reviewed_conference_summary": ("Conference summary", "Résumé de conférence"),
        "peer_reviewed_article_summary": ("Research summary", "Résumé de recherche"),
        "peer_reviewed_review_summary": ("Research review", "Synthèse scientifique"),
        "preprint_summary": ("Preprint", "Prépublication"),
        "critical_book_chapter_summary": ("Critical book chapter", "Chapitre critique"),
    }
    pair = labels.get(kind, ("Source", "Source"))
    return pair[0 if language == "en" else 1]
