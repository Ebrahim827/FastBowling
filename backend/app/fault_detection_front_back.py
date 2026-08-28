"""
STEP 7 (partial): FRONT/BACK VIEW BIOMECHANICS

Side-view metrics (fault_detection.py) mostly rely on angles that are
only visible in profile - front knee flexion, arm arc, leading arm
elevation. From front-on or back-on, those same joints mostly just look
like they're getting shorter/longer as they move toward/away from
camera, so those checks don't transfer.

What DOES transfer to front/back view, with the keypoints we actually
have (17-point COCO - no toe/foot-orientation keypoint):

    - Shoulder alignment angle: how side-on vs chest-on the action is
      at release - visible face-on, invisible in profile.
    - Head lateral stability: side-to-side head sway through the
      delivery - works from any angle, but especially easy to see from
      front/back since the sway is directly toward/away from the
      camera's horizontal axis.

HONEST LIMITATION: front-foot landing alignment (open/closed relative
to the crease) was on the original front/back-view list, but it can't
actually be measured with this pose model - there's no toe or foot-
orientation keypoint, only a single ankle point, which has no
"facing direction" to compute an angle from. This would need either a
custom-trained foot-keypoint model or a different approach (e.g. shoe
bounding-box orientation) - flagged here rather than faked with a
number that doesn't mean anything.
"""

import numpy as np

LEFT_SHOULDER, RIGHT_SHOULDER = 5, 6
NOSE = 0


def _xy(kpts, idx):
    if kpts is None or kpts[idx][2] < 0.3:
        return None
    return np.array([kpts[idx][0], kpts[idx][1]])


def compute_shoulder_alignment_angle(all_keypoints, frame_idx):
    """TREND. Angle of the shoulder line relative to horizontal, at a
    given frame (typically release). 0 deg = shoulders level with the
    camera (fully chest-on/front-on to camera), larger = more rotated/
    side-on. No fixed "correct" threshold - action type (side-on,
    front-on, mixed) changes what's normal, and we're not classifying
    action type yet (see docs/pace_loss_research_notes_v2.md, point 4:
    "Bowling action type matters and we haven't accounted for it yet").
    Report as a number/trend, not a verdict."""
    if frame_idx is None or frame_idx >= len(all_keypoints):
        return None
    kpts = all_keypoints[frame_idx]
    ls, rs = _xy(kpts, LEFT_SHOULDER), _xy(kpts, RIGHT_SHOULDER)
    if ls is None or rs is None:
        return None
    vec = rs - ls
    angle = np.degrees(np.arctan2(vec[1], vec[0]))
    return float(abs(angle))


def compute_head_lateral_stability(all_keypoints, start_frame, end_frame):
    """INFO. How much the head sways side-to-side (horizontal nose
    position) across a window of frames - typically back-foot-contact
    to release. Reported as pixel range (relative units, same caveat
    as everything else pre-calibration) - lower range = more stable.
    No fixed threshold in the research reviewed; this is descriptive,
    same tier as arm arc/wrist snap in the side-view report."""
    if start_frame is None or end_frame is None or end_frame <= start_frame:
        return None
    xs = []
    for i in range(start_frame, end_frame + 1):
        kpts = all_keypoints[i] if i < len(all_keypoints) else None
        pos = _xy(kpts, NOSE)
        if pos is not None:
            xs.append(pos[0])
    if len(xs) < 2:
        return None
    return {
        "head_lateral_range_px": float(max(xs) - min(xs)),
    }


def build_front_back_report(all_keypoints, back_foot_frame, release_frame):
    """Runs the front/back-view metrics and returns a report dict, in
    the same shape/spirit as fault_detection.build_report() for the
    side view - so run_pipeline.py and the report writer can handle
    either view without much branching."""
    report = {}

    shoulder_angle = compute_shoulder_alignment_angle(all_keypoints, release_frame)
    report["shoulder_alignment_angle_release_deg"] = shoulder_angle

    head_stability = compute_head_lateral_stability(all_keypoints, back_foot_frame, release_frame) or {}
    report.update(head_stability)

    # Documented gap, not a computed value - shows up in the report so
    # it's clear this was considered and excluded on purpose, not
    # forgotten.
    report["front_foot_alignment_note"] = (
        "Not measurable with the current pose model - no toe/foot-orientation "
        "keypoint available, only a single ankle point. Would need a custom "
        "foot-keypoint model or bounding-box-orientation approach."
    )

    return report


def categorize_front_back_report(report):
    """Same three-section shape as fault_detection.categorize_report()
    (improvements / plus_points / stats), so the report writer doesn't
    need view-specific logic. Front/back metrics are all TREND/INFO
    tier right now (no established pass/fail threshold), so everything
    lands in stats - nothing here is confident enough yet to call an
    improvement or a plus point."""
    stats = []

    shoulder_angle = report.get("shoulder_alignment_angle_release_deg")
    if shoulder_angle is not None:
        stats.append(f"Shoulder alignment at release: {shoulder_angle:.1f} deg from horizontal (no fixed target - depends on action type)")

    head_range = report.get("head_lateral_range_px")
    if head_range is not None:
        stats.append(f"Head lateral sway (back-foot-contact to release): {head_range:.1f} px range (relative units)")

    note = report.get("front_foot_alignment_note")
    if note:
        stats.append(f"Front-foot landing alignment: NOT MEASURED - {note}")

    return {
        "improvements": [],
        "plus_points": [],
        "stats": stats,
    }
