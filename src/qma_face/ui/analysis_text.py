STRINGS = {
    "en": {
        "review_eye_points": (
            "Review eye points: the measured openings differ strongly or are unusually large. "
            "This may be a point, pose or expression issue; it is not a conclusion about your face."
        ),
        "review_outline_points": (
            "Review forehead, chin and side points: the measured height/width needs a visual "
            "check. The check is a heuristic, not a judgment of face shape."
        ),
        "exposure_stability": "Exposure stress test (±10% brightness; not confidence)",
        "exposure_warning": (
            "This score changes substantially with lighting. Retake under even lighting; "
            "do not treat the number as a stable personal trait."
        ),
        "analyse": "Check & analyse",
        "view_analysis": "View analysis",
        "analysis_title": "A closer look.",
        "step_photo": "1 · Photo",
        "step_points": "2 · Face map",
        "step_result": "3 · Result",
        "crop_hint": (
            "Drag a close frame around one face, from forehead to chin and cheek to cheek. "
            "Keep the whole face inside; leave out the shoulders and most background. "
            "Framing can change the model estimate."
        ),
        "research_note": (
            "Local research preview. Scores reflect model/rater preferences; component "
            "beauty scores are unavailable."
        ),
        "confirm_face": "This selection contains one front-facing face with visible features.",
        "check_photo": "Check selection",
        "rotate": "Rotate 90°",
        "reset": "Reset",
        "improve": "Adjust lighting",
        "denoise": "Also reduce noise (may soften details)",
        "original": "Original crop",
        "prepared": "Prepared crop",
        "use_original": "Use original crop",
        "quality_usable": "Photo checks passed. Review the selected face before continuing.",
        "quality_adjustable": "Lighting could be improved. Compare the result with the original.",
        "quality_retake": "Choose a clearer photo. Lost detail cannot be restored for measurement.",
        "too_small": "The face selection is too small (minimum 96 pixels per side).",
        "limited_resolution": "A larger face image would give more detail.",
        "no_detail": "There is too little visible image detail.",
        "blurred": "The selection appears blurred.",
        "clipped": "A large area has lost shadow or highlight detail.",
        "dark": "The crop is dark.",
        "bright": "The crop is bright.",
        "next_points": "Find face points",
        "finding": "Preparing your face map…",
        "points_hint": (
            "Drag misplaced points. Uncheck a hidden group. Measurements are estimates in "
            "this photo."
        ),
        "confirm_points": "I reviewed the points against the visible face.",
        "next_result": "See the result",
        "explaining": "Checking how the model responds…",
        "outline": "Face outline",
        "brows": "Eyebrows",
        "eyes": "Eyes",
        "nose": "Nose",
        "mouth": "Lips",
        "research_score": "Research model score",
        "withheld": "Score unavailable",
        "withheld_note": "Overall scoring is withheld when a facial group is marked hidden.",
        "points_layer": "Face map",
        "attention_layer": "Model attention",
        "no_attention": "No positive attention signal available.",
        "save_analysis": "Add result to chat",
        "export_analysis": "Export result…",
        "cancel_analysis": "Cancel",
        "analysis_failed": "This analysis could not finish. Your original photo is unchanged.",
        "analysis_saved": "Analysis added to this chat.",
        "export_filter": "JSON report (*.json)",
        "export_failed": "The report could not be saved.",
        "geometry_title": "Geometry in this photo — ratios, not beauty scores",
        "geometry_warning": (
            "Automatic eye and lip points can be inaccurate. Treat these ratios as rough "
            "estimates and check the map."
        ),
        "sensitivity_title": "Change in model score after blurring each region",
        "sensitivity_note": (
            "Negative means the blurred version scored lower; positive means it scored higher. "
            "This is sensitivity to an edited input, not a beauty score for that feature. Effects "
            "overlap, do not add up, and do not prove a cause."
        ),
        "ceiling_note": (
            "The gap to 100 is a distance to the model scale ceiling. No evidence assigns "
            "those missing points to specific features."
        ),
        "score_note": (
            "Mapping: (rating on the 1–5 scale − 1) × 25. This is not an objective beauty "
            "standard or an accuracy percentage."
        ),
        "palette_note": (
            "Photo palette includes hair and background; lighting affects these colors."
        ),
        "adjustment_note": "Change after preparation",
        "component_note": (
            "Beauty scores for eyes, brows, nose, lips and jaw: unavailable (not trained)."
        ),
        "confidence_note": (
            "Calibrated confidence: unavailable. Pose and occlusion were confirmed by the "
            "user, not detected."
        ),
        "privacy_analysis": (
            "Adding or exporting saves measurements. The photo is kept only under your "
            "separate photo setting."
        ),
        "face_height_to_width": "Face height / width",
        "eye_separation_to_face_width": "Eye separation / face width",
        "nose_width_to_face_width": "Nose width / face width",
        "mouth_width_to_face_width": "Mouth width / face width",
        "nose_to_mouth_width": "Nose width / mouth width",
        "image_left_eye_opening": "Image-left eye opening / width",
        "image_right_eye_opening": "Image-right eye opening / width",
        "brow_span_to_face_width": "Brow span / face width",
        "lip_height_to_mouth_width": "Lip height / mouth width",
        "jaw_span_to_face_width": "Jaw span / face width",
        "paired_image_asymmetry": "Paired asymmetry / face width",
        "eye_line_roll": "Eye-line angle (degrees)",
    },
    "fr": {
        "review_eye_points": (
            "Vérifiez les points des yeux : les ouvertures mesurées diffèrent fortement ou sont "
            "très grandes. Cela peut venir des points, de la pose ou de l’expression, sans "
            "conclusion sur votre visage."
        ),
        "review_outline_points": (
            "Vérifiez les points du front, du menton et des côtés : le rapport hauteur/largeur "
            "demande un contrôle visuel. Ce contrôle est heuristique, sans jugement sur la forme "
            "du visage."
        ),
        "exposure_stability": "Test d’éclairage (luminosité ±10 % ; pas une confiance)",
        "exposure_warning": (
            "Ce score varie fortement avec l’éclairage. Reprenez la photo sous une lumière "
            "uniforme ; ce chiffre n’est pas un trait stable de la personne."
        ),
        "analyse": "Vérifier et analyser",
        "view_analysis": "Voir l’analyse",
        "analysis_title": "Un regard plus précis.",
        "step_photo": "1 · Photo",
        "step_points": "2 · Repères",
        "step_result": "3 · Résultat",
        "crop_hint": (
            "Encadrez un seul visage, du front au menton et d’une joue à l’autre. "
            "Gardez tout le visage, sans les épaules ni trop d’arrière-plan. "
            "Le cadrage peut changer l’estimation du modèle."
        ),
        "research_note": (
            "Aperçu de recherche local. Le score reflète les préférences du modèle et des "
            "évaluateurs ; les scores de beauté des parties sont indisponibles."
        ),
        "confirm_face": "La sélection contient un seul visage de face, avec des traits visibles.",
        "check_photo": "Vérifier la sélection",
        "rotate": "Tourner de 90°",
        "reset": "Réinitialiser",
        "improve": "Ajuster la lumière",
        "denoise": "Réduire aussi le bruit (peut adoucir les détails)",
        "original": "Cadrage original",
        "prepared": "Cadrage préparé",
        "use_original": "Utiliser l’original",
        "quality_usable": (
            "Les vérifications photo sont passées. Vérifiez le cadrage du visage avant de "
            "continuer."
        ),
        "quality_adjustable": "La lumière pourrait être améliorée. Comparez avec l’original.",
        "quality_retake": (
            "Choisissez une photo plus nette. Les détails perdus ne peuvent pas être "
            "recréés pour mesurer."
        ),
        "too_small": "La sélection du visage est trop petite (96 pixels minimum par côté).",
        "limited_resolution": "Une image du visage plus grande offrirait davantage de détails.",
        "no_detail": "L’image contient trop peu de détails visibles.",
        "blurred": "La sélection semble floue.",
        "clipped": "Une grande zone a perdu ses détails dans les ombres ou les hautes lumières.",
        "dark": "Le cadrage est sombre.",
        "bright": "Le cadrage est clair.",
        "next_points": "Trouver les repères",
        "finding": "Préparation des repères du visage…",
        "points_hint": (
            "Déplacez les points mal placés. Décochez une zone masquée. Les mesures "
            "restent des estimations sur cette photo."
        ),
        "confirm_points": "J’ai vérifié les points sur les traits visibles.",
        "next_result": "Voir le résultat",
        "explaining": "Analyse des variations du modèle…",
        "outline": "Contour",
        "brows": "Sourcils",
        "eyes": "Yeux",
        "nose": "Nez",
        "mouth": "Lèvres",
        "research_score": "Score du modèle de recherche",
        "withheld": "Score indisponible",
        "withheld_note": (
            "Le score global est masqué lorsqu’une zone du visage est indiquée comme cachée."
        ),
        "points_layer": "Repères du visage",
        "attention_layer": "Attention du modèle",
        "no_attention": "Aucun signal d’attention positif disponible.",
        "save_analysis": "Ajouter à la discussion",
        "export_analysis": "Exporter le résultat…",
        "cancel_analysis": "Annuler",
        "analysis_failed": "L’analyse n’a pas pu aboutir. La photo originale est inchangée.",
        "analysis_saved": "Analyse ajoutée à cette discussion.",
        "export_filter": "Rapport JSON (*.json)",
        "export_failed": "Le rapport n’a pas pu être enregistré.",
        "geometry_title": "Géométrie sur cette photo — rapports, pas des scores de beauté",
        "geometry_warning": (
            "Les points des yeux et des lèvres peuvent être imprécis. Ces rapports sont "
            "approximatifs : vérifiez les repères."
        ),
        "sensitivity_title": "Variation du score après floutage de chaque zone",
        "sensitivity_note": (
            "Une valeur négative indique un score plus bas après floutage ; positive, plus haut. "
            "C’est une sensibilité à une image modifiée, pas un score de beauté de la zone. "
            "Les effets se "
            "recouvrent, ne s’additionnent pas et ne prouvent pas une cause."
        ),
        "ceiling_note": (
            "L’écart à 100 est une distance au maximum de l’échelle du modèle. Aucune "
            "preuve n’attribue ces points à des traits précis."
        ),
        "score_note": (
            "Conversion : (note de 1 à 5 − 1) × 25. Ce n’est ni une norme objective de "
            "beauté ni un pourcentage de précision."
        ),
        "palette_note": (
            "La palette inclut les cheveux et l’arrière-plan ; la lumière influence ces couleurs."
        ),
        "adjustment_note": "Variation après préparation",
        "component_note": (
            "Scores de beauté des yeux, sourcils, nez, lèvres et mâchoire : indisponibles "
            "(non entraînés)."
        ),
        "confidence_note": (
            "Confiance calibrée : indisponible. La pose et la visibilité ont été "
            "confirmées par l’utilisateur, pas détectées."
        ),
        "privacy_analysis": (
            "L’ajout ou l’export enregistre les mesures. La photo suit votre réglage de "
            "conservation séparé."
        ),
        "face_height_to_width": "Hauteur / largeur du visage",
        "eye_separation_to_face_width": "Écart des yeux / largeur du visage",
        "nose_width_to_face_width": "Largeur du nez / largeur du visage",
        "mouth_width_to_face_width": "Largeur de la bouche / du visage",
        "nose_to_mouth_width": "Largeur du nez / de la bouche",
        "image_left_eye_opening": "Ouverture / largeur de l’œil à gauche de l’image",
        "image_right_eye_opening": "Ouverture / largeur de l’œil à droite de l’image",
        "brow_span_to_face_width": "Étendue des sourcils / largeur du visage",
        "lip_height_to_mouth_width": "Hauteur des lèvres / largeur de la bouche",
        "jaw_span_to_face_width": "Étendue de la mâchoire / largeur du visage",
        "paired_image_asymmetry": "Asymétrie appariée / largeur du visage",
        "eye_line_roll": "Angle de la ligne des yeux (degrés)",
    },
}


def text_report(report, language):
    t = STRINGS[language].__getitem__
    value = report["score_0_to_100"]
    lines = [
        t("research_score") + (f": {value:.2f} / 100" if value is not None else ": —"),
        t("research_note"),
        "",
        t("score_note") if value is not None else t("withheld_note"),
        t("ceiling_note"),
        "",
        t("geometry_title"),
    ]
    stability = report.get("exposure_stability", {})
    if report.get("points_manually_reviewed") is False:
        lines.append(
            "Points automatiques non vérifiés ; vérifiez la carte avant d’utiliser ces mesures."
            if language == "fr"
            else "Automatic landmark points have not been manually reviewed; "
            "check the map before using these measurements."
        )
    lines.extend(t(flag) for flag in report["geometry"].get("review_flags", []))
    if stability.get("trials"):
        lines.extend(
            [t("exposure_stability") + f": max |Δ| {stability['largest_abs_change']:.2f} / 100"]
        )
        if stability["unstable_heuristic"]:
            lines.append(t("exposure_warning"))
    for metric in report["geometry"]["metrics"]:
        value = metric["value"]
        lines.append(t(metric["name"]) + (f": {value:.4f}" if value is not None else ": —"))
    lines.append(t("geometry_warning"))
    lines.extend(["", t("component_note"), "", t("sensitivity_title")])
    for region in report["regions"]:
        lines.append(f"{t(region['region'])}: {region['delta_score_100_after_blur']:+.3f}")
    lines.extend([t("sensitivity_note"), "", t("confidence_note"), "", t("palette_note")])
    if report.get("adjustment_delta_100") is not None:
        lines.extend(["", f"{t('adjustment_note')}: {report['adjustment_delta_100']:+.3f}"])
    return "\n".join(lines)
