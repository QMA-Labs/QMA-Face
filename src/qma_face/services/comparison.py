"""Within-collection comparisons, with no identity matching or rarity estimates."""

import math
from datetime import date
from statistics import mean, median

from qma_face.core.i18n import tr


def compare_reports(items: list[dict], *, same_person_confirmed: bool) -> dict:
    if not same_person_confirmed or not 2 <= len(items) <= 8:
        raise ValueError("Confirm the same person and provide 2–8 reviewed photos")
    hashes, engines = set(), set()
    rows = []
    for item in items:
        report = item["report"]
        digest = report["source_photo_sha256"]
        if digest in hashes or report.get("status") != "research_preview":
            raise ValueError("Duplicate or unreviewed photo")
        hashes.add(digest)
        engines.add(report["checkpoint_sha256"])
        if item.get("date"):
            date.fromisoformat(item["date"])
        score = report["score_0_to_100"]
        if score is not None and (not math.isfinite(score) or not 0 <= score <= 100):
            raise ValueError("Invalid score")
        quality = report.get("preparation", {}).get("after", {})
        rows.append(
            {
                "label": str(item["label"])[:80],
                "date": item.get("date") or None,
                "angle": item.get("angle", "unknown"),
                "expression": item.get("expression", "unknown"),
                "photo_sha256": digest,
                "score": score,
                "quality_status": quality.get("status", "unknown"),
                "metrics": report["geometry"]["metrics"],
            }
        )
    if len(engines) != 1:
        raise ValueError("Different engine versions cannot be compared")
    scores = [row["score"] for row in rows if row["score"] is not None]
    signature = []
    names = sorted({m["name"] for row in rows for m in row["metrics"]})
    for name in names:
        values = [
            m["value"]
            for row in rows
            for m in row["metrics"]
            if m["name"] == name and m["value"] is not None and math.isfinite(m["value"])
        ]
        if len(values) >= 2:
            signature.append(
                {
                    "name": name,
                    "n": len(values),
                    "median": median(values),
                    "min": min(values),
                    "max": max(values),
                    "observed_range": max(values) - min(values),
                }
            )
    # Never select by score. Equal quality returns the first item in user order.
    quality_order = {"usable": 2, "adjustable": 1}
    usable = [r for r in rows if r["quality_status"] in quality_order]
    pick = max(usable, key=lambda r: quality_order[r["quality_status"]]) if usable else None
    groups = []
    for kind in ("angle", "expression"):
        candidates = []
        for value in sorted({r[kind] for r in rows} - {"unknown"}):
            values = [r["score"] for r in rows if r[kind] == value and r["score"] is not None]
            if len(values) >= 2:
                candidates.append({"label": value, "n": len(values), "mean": mean(values)})
        if len(candidates) >= 2:
            groups.append({"kind": kind, "groups": candidates})
    dated = sorted(
        [r for r in rows if r["date"] and r["score"] is not None], key=lambda r: r["date"]
    )
    if len({r["date"] for r in dated}) < 2:
        dated = []
    return {
        "schema_version": 1,
        "kind": "within_person_collection_research",
        "same_person": "user_declared_not_verified",
        "checkpoint_sha256": engines.pop(),
        "photos": rows,
        "quality_pick": pick["label"] if pick else None,
        "score_summary": {
            "n": len(scores),
            "min": min(scores),
            "max": max(scores),
            "range": max(scores) - min(scores),
        }
        if len(scores) >= 2
        else None,
        "signature": signature,
        "labeled_groups": groups,
        "timeline": [{"date": r["date"], "label": r["label"], "score": r["score"]} for r in dated],
        "apparent_age": None,
        "rarity": None,
        "calibrated_confidence": None,
        "identity_verified": False,
    }


def comparison_text(report: dict, language: str) -> str:
    def t(key):
        return tr(key, language)

    lines = [
        t("comparison_title"),
        "",
        t("evidence_math"),
        f"{t('quality_pick')}: {report['quality_pick'] or '—'}",
        "",
    ]
    for row in report["photos"]:
        number = f"{row['score']:.2f}" if row["score"] is not None else "—"
        lines.append(f"{row['label']}: {number} / 100 · {row['date'] or '—'}")
    summary = report["score_summary"]
    if summary:
        lines.extend(
            [
                "",
                f"{t('score_range')}: {summary['min']:.2f}–{summary['max']:.2f} "
                f"(Δ {summary['range']:.2f}, n={summary['n']})",
            ]
        )
    lines.extend(["", t("signature")])
    for item in report["signature"]:
        lines.append(
            f"{t(item['name'])}: {item['median']:.3f} "
            f"[{item['min']:.3f}, {item['max']:.3f}] · n={item['n']}"
        )
    if report["labeled_groups"]:
        lines.extend(["", t("angle_effect")])
        for group in report["labeled_groups"]:
            for item in group["groups"]:
                lines.append(
                    f"{t(group['kind'] + '_label')} · {t(item['label'])}: "
                    f"{item['mean']:.2f} / 100 · n={item['n']}"
                )
    if report["timeline"]:
        lines.extend(["", t("timeline")])
        for row in report["timeline"]:
            lines.append(f"{row['date']} · {row['label']}: {row['score']:.2f}")
    lines.extend(["", t("collection_limits"), "", t("age_unavailable")])
    return "\n".join(lines)


def comparison_answer(messages: list[dict], language: str) -> dict | None:
    import re

    latest = next((m for m in reversed(messages) if m["role"] == "user"), {})
    question = latest.get("content", "").casefold()
    if not re.search(
        r"compar|differ|différ|stable|stabili|signature|timeline|best angle|meilleur angle",
        question,
    ):
        return None
    # A collection is explicitly selected for this request, never inferred from old history.
    report = latest.get("metadata", {}).get("_active_comparison")
    if not report:
        return None
    if re.search(r"honest|moral|trust|personnal|personality|pdf|source|article", question):
        return None
    return {
        "text": comparison_text(report, language),
        "comparison": report,
        "answer_kind": "collection_calculation",
        "model": None,
        "sources": [],
        "device": "local",
    }
