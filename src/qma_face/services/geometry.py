"""SCUT's official 1-based 86-point ordering, measured in image coordinates."""

import numpy as np

GROUPS = {
    "outline": tuple(range(1, 23)),
    "brows": tuple(range(23, 43)),
    "eyes": tuple(range(43, 61)),
    "nose": tuple(range(61, 74)),
    "mouth": tuple(range(74, 87)),
}
LANDMARK_REFERENCE = "https://github.com/HCIILAB/SCUT-FBP5500-Database-Release"


def validate_points(points) -> np.ndarray:
    points = np.asarray(points, dtype=np.float64)
    if points.shape != (86, 2) or not np.isfinite(points).all():
        raise ValueError("Expected 86 finite normalized landmark coordinates")
    if (points < 0).any() or (points > 1).any():
        raise ValueError("Landmarks must remain inside the selected crop")
    return points


def measurements(points, size: tuple[int, int], visible: dict[str, bool]) -> dict:
    normalized = validate_points(points)
    if min(size) <= 0 or set(visible) != set(GROUPS):
        raise ValueError("Image size and visibility of all five groups are required")
    points = normalized * np.asarray(size)
    metrics = []

    def point(number):
        return points[number - 1]

    def distance(first, second):
        return float(np.linalg.norm(point(first) - point(second)))

    def ratio(name, numerator, denominator, required):
        if all(visible[group] for group in required) and denominator > 1e-5:
            value = round(numerator / denominator, 5)
        else:
            value = None
        metrics.append(
            {
                "name": name,
                "value": value,
                "unit": "ratio",
                "required_groups": required,
                "kind": "geometry_not_beauty",
            }
        )

    width = distance(6, 18)
    ratio("face_height_to_width", distance(1, 12), width, ["outline"])
    ratio("eye_separation_to_face_width", distance(59, 60), width, ["eyes", "outline"])
    ratio("nose_width_to_face_width", distance(65, 69), width, ["nose", "outline"])
    ratio("mouth_width_to_face_width", distance(74, 80), width, ["mouth", "outline"])
    ratio("nose_to_mouth_width", distance(65, 69), distance(74, 80), ["nose", "mouth"])
    ratio("image_left_eye_opening", distance(45, 49), distance(43, 47), ["eyes"])
    ratio("image_right_eye_opening", distance(53, 57), distance(51, 55), ["eyes"])
    ratio("brow_span_to_face_width", distance(27, 33), width, ["brows", "outline"])
    ratio("lip_height_to_mouth_width", distance(77, 83), distance(74, 80), ["mouth"])
    ratio("jaw_span_to_face_width", distance(9, 15), width, ["outline"])
    symmetry = None
    roll = None
    if visible["eyes"]:
        axis = point(60) - point(59)
        length = np.linalg.norm(axis)
        if length > 1e-5:
            roll = float(np.degrees(np.arctan2(axis[1], axis[0])))
            horizontal = axis / length
            vertical = np.array([-horizontal[1], horizontal[0]])
            center = (point(59) + point(60)) / 2
            aligned = np.stack(
                ((points - center) @ horizontal, (points - center) @ vertical), axis=1
            )
            if visible["outline"] and visible["nose"] and visible["mouth"]:
                pairs = [(6, 18), (9, 15), (10, 14), (65, 69), (66, 68), (74, 80)]
                differences = []
                for first, second in pairs:
                    left, right = aligned[first - 1], aligned[second - 1]
                    differences.append(np.linalg.norm(left - right * [-1, 1]))
                if width > 1e-5:
                    symmetry = round(float(np.mean(differences) / width), 5)
    metrics.extend(
        [
            {
                "name": "paired_image_asymmetry",
                "value": symmetry,
                "unit": "fraction_of_face_width",
                "kind": "geometry_not_beauty",
            },
            {
                "name": "eye_line_roll",
                "value": round(roll, 3) if roll is not None else None,
                "unit": "degrees",
                "kind": "geometry_not_beauty",
            },
        ]
    )
    values = {metric["name"]: metric["value"] for metric in metrics}
    review = []
    left, right = values["image_left_eye_opening"], values["image_right_eye_opening"]
    if left is not None and right is not None and (
        max(left, right) > 0.45 or max(left, right) > 2.5 * max(min(left, right), 0.03)
    ):
        review.append("review_eye_points")
    height = values["face_height_to_width"]
    if height is not None and not 1.05 <= height <= 1.9:
        review.append("review_outline_points")
    return {
        "metrics": metrics,
        "visibility": visible,
        "visibility_source": "user_review_not_automatic_detection",
        "coordinate_space": "selected_crop_2d_image",
        "landmark_reference": LANDMARK_REFERENCE,
        "confidence": None,
        "beauty_component_scores": None,
        "review_flags": review,
        "review_flags_are_heuristics_not_diagnoses": True,
        "limitations": [
            "Image-plane estimates; camera angle and landmark error affect ratios.",
            "Asymmetry is a distance, not an attractiveness or health score.",
            "Eye opening is image geometry, not emotional-state evidence.",
        ],
    }


def photo_palette(image) -> dict:
    sample = image.convert("RGB").copy()
    sample.thumbnail((160, 160))
    reduced = sample.quantize(colors=5)
    palette = reduced.getpalette()
    colors = []
    total = sample.width * sample.height
    for count, index in sorted(reduced.getcolors(), reverse=True):
        rgb = palette[index * 3 : index * 3 + 3]
        colors.append(
            {
                "hex": "#" + "".join(f"{c:02X}" for c in rgb),
                "pixel_fraction": round(count / total, 4),
            }
        )
    return {
        "colors": colors,
        "scope": "whole_selected_photo_including_background_and_hair",
        "calibrated_skin_color": False,
        "lighting_dependent": True,
    }
