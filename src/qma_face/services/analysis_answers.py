"""Deterministic numeric explanations: a language model cannot reverse measured signs."""

import re

from qma_face.core.i18n import tr


def analysis_answer(messages, language: str, has_image: bool) -> dict | None:
    latest = next((m for m in reversed(messages) if m["role"] == "user"), {})
    metadata = latest.get("metadata", {})
    data = metadata.get("_active_analysis")
    photo_hash = metadata.get("_photo_sha256")
    if not has_image or not photo_hash or not isinstance(data, dict):
        return None
    if data.get("status") != "research_preview" or data.get("photo_sha256") != photo_hash:
        return None
    question = latest["content"].casefold()
    if re.search(r"\b(pdf|book|livre|article|paper|sources)\b", question):
        return None
    if re.search(r"trustworth|honest|moral|personality|honnêt|personnalit", question):
        answer = (
            "A face or its model score cannot establish honesty, trustworthiness, morality "
            "or personality. I can discuss behavior you describe instead."
            if language == "en"
            else "Un visage ou son score ne permet pas d’établir l’honnêteté, la fiabilité morale "
            "ou la personnalité. Je peux discuter des comportements que vous décrivez."
        )
        return {
            "text": answer,
            "answer_kind": "appearance_trait_boundary",
            "model": None,
            "device": "local",
            "sources": [],
            "analysis_photo_sha256": photo_hash,
        }
    if not re.search(
        r"score|\b100\b|\bnote\b|points|sensitiv|blur|flou|ratio|geometry|géométr|beau|attract|ugly|rapport|confidence|confiance",
        question,
    ):
        return None

    def t(key):
        return tr(key, language)

    score = data["score_0_to_100"]
    lines = []
    if score is None:
        lines.append(t("withheld_note"))
    else:
        gap = 100 - score
        lines.append(f"{t('research_score')}: {score:.1f} / 100.")
        lines.append(
            (
                f"Distance to the scale ceiling: {gap:.1f}. "
                if language == "en"
                else f"Écart au maximum de l’échelle : {gap:.1f}. "
            )
            + t("ceiling_note")
        )
        lines.append(t("score_note"))
    lines.extend(["", t("component_note"), "", t("sensitivity_title")])
    for region in data["blur_sensitivity"]:
        delta = region["delta_score_100_after_blur"]
        direction = (
            ("higher" if delta > 0 else "lower" if delta < 0 else "unchanged")
            if language == "en"
            else ("plus élevé" if delta > 0 else "plus bas" if delta < 0 else "inchangé")
        )
        lines.append(f"{t(region['region'])}: {delta:+.3f} ({direction}).")
    lines.extend([t("sensitivity_note"), "", t("confidence_note")])
    if re.search(r"ratio|geometry|géométr|rapport|angle|distance", question):
        lines.extend(["", t("geometry_title")])
        for metric in data["metrics"]:
            value = metric["value"]
            lines.append(t(metric["name"]) + (f": {value:.3f}" if value is not None else ": —"))
    if metadata.get("_answer_style") == "casual" and not re.search(
        r"blur|flou|ratio|geometry|géométr|rapport|sensitiv", question
    ):
        lines = lines[:4] + ["", t("component_note"), t("confidence_note")]
    stability = data.get("exposure_stability") or {}
    if stability.get("trials"):
        lines.extend(
            ["", t("exposure_stability") + f": max |Δ| {stability['largest_abs_change']:.2f} / 100"]
        )
        if stability.get("unstable_heuristic"):
            lines.append(t("exposure_warning"))
    lines.extend(t(flag) for flag in data.get("landmark_review_flags", []))
    lines = [t("evidence_math"), ""] + lines + ["", t("next_result")]
    return {
        "text": "\n".join(lines),
        "answer_kind": "structured_analysis_explanation",
        "model": None,
        "device": "local",
        "analysis_photo_sha256": photo_hash,
        "sources": [],
        "component_scores": None,
    }
