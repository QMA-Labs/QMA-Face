"""Visual summaries of actual saved measurements, with no invented component ratings."""

from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QProgressBar, QVBoxLayout

from qma_face.core.i18n import tr


def analysis_cards(report, language, compact=False):
    french = language == "fr"
    panel = QFrame()
    panel.setObjectName("analysisCards")
    grid = QGridLayout(panel)
    for column in range(3):
        grid.setColumnStretch(column, 1)
    score = report.get("score_0_to_100")
    stability = report.get("exposure_stability") or {}
    cards = [
        (tr("research_score", language), "—" if score is None else f"{score:.1f} / 100"),
        (
            "Vérification des points" if french else "Landmark review",
            ("À vérifier" if french else "Check map")
            if report.get("geometry", {}).get("review_flags")
            or report.get("points_manually_reviewed") is False
            else ("Revue manuelle" if french else "Manual review"),
        ),
        (
            "Variation avec la lumière" if french else "Lighting variation",
            f"max |Δ| {stability['largest_abs_change']:.2f}"
            if isinstance(stability.get("largest_abs_change"), (int, float))
            else "—",
        ),
    ]
    for index, (title, value) in enumerate(cards):
        box = QFrame()
        box.setStyleSheet("QFrame { background: #F0ECFA; border-radius: 12px; }")
        layout = QVBoxLayout(box)
        heading = QLabel(title)
        heading.setWordWrap(True)
        layout.addWidget(heading)
        number = QLabel(value)
        number.setStyleSheet("font-size: 23px; color: #7867C7;")
        layout.addWidget(number)
        if index == 0 and score is not None:
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(round(score * 10))
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            layout.addWidget(bar)
        grid.addWidget(box, 0, index)
    note = QLabel(
        "Le cadrage et les points influencent le résultat. Aucun pourcentage de précision validé."
        if french
        else "Framing and landmark placement affect this result. "
        "Calibrated accuracy is unavailable."
    )
    note.setWordWrap(True)
    grid.addWidget(note, 1, 0, 1, 3)
    if compact:
        return panel
    for index, region in enumerate(report.get("regions", [])):
        region_card = QFrame()
        region_layout = QVBoxLayout(region_card)
        region_layout.setContentsMargins(8, 5, 8, 5)
        text = QLabel(
            f"{tr(region['region'], language)}   {region['delta_score_100_after_blur']:+.2f}"
        )
        region_layout.addWidget(text)
        bar = QProgressBar()
        bar.setRange(0, 10000)
        bar.setValue(min(10000, round(abs(region["delta_score_100_after_blur"]) * 100)))
        bar.setTextVisible(False)
        bar.setFixedHeight(5)
        bar.setStyleSheet(
            "QProgressBar { background: #EDE8F8; border: none; border-radius: 2px; }"
            "QProgressBar::chunk { background: #A18BDC; border-radius: 2px; }"
        )
        region_layout.addWidget(bar)
        grid.addWidget(region_card, 2 + index // 3, index % 3)
    note = QLabel(tr("sensitivity_note", language))
    note.setWordWrap(True)
    grid.addWidget(note, 4, 0, 1, 3)
    return panel
