"""
STEP 4: FAULT DETECTION ENGINE

Takes the tracked keypoints + detected phase frames (back foot contact,
front foot contact, release) from the pipeline and turns them into the
actual biomechanics numbers from docs/pace_loss_research_notes_v2.md.

Every metric here is tagged with a confidence level, matching the
research notes:
    "flag"    = high confidence, has a real threshold -> worded as a
                genuine coaching flag if it's outside range
    "trend"   = high confidence the metric matters, but no fixed
                universal threshold -> reported as a number/trend, not
                pass/fail
    "info"    = descriptive only, not confidently linked to a specific
                good/bad cutoff yet -> shown for interest, no verdict

IMPORTANT HONESTY NOTE ON UNITS: none of these speeds are real-world
km/h or m/s. Without a calibration reference (a known real-world
distance visible in frame, or a fixed/tripod camera with a known
distance-per-pixel), everything here is in PIXELS PER FRAME - only
meaningful for comparing one delivery against another from the SAME
camera position, not as an absolute speed. This gets fixed once we
add real calibration (Step 6/8 in the roadmap).
"""

import numpy as np

LEFT_SHOULDER, RIGHT_SHOULDER = 5, 6
LEFT_ELBOW, RIGHT_ELBOW = 7, 8
LEFT_WRIST, RIGHT_WRIST = 9, 10
LEFT_HIP, RIGHT_HIP = 11, 12
LEFT_KNEE, RIGHT_KNEE = 13, 14
LEFT_ANKLE, RIGHT_ANKLE = 15, 16


def _xy(kpts, idx):
    if kpts is None or kpts[idx][2] < 0.3:
        return None
    return np.array([kpts[idx][0], kpts[idx][1]])


def joint_angle_deg(kpts, a_idx, b_idx, c_idx):
    """Angle at point B, formed by A-B-C, in degrees. Returns None if
    any of the three points isn't confidently detected in this frame."""
    a, b, c = _xy(kpts, a_idx), _xy(kpts, b_idx), _xy(kpts, c_idx)
    if a is None or b is None or c is None:
        return None
    v1 = a - b
    v2 = c - b
    if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
        return None
    cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_angle)))


def compute_front_knee_angle_at_release(all_keypoints, release_frame, front_leg_side):
    """Metric #1 - FLAG. Research: knee angle AT RELEASE (not at
    landing) is what correlates with speed. ~150 degrees+ is the
    commonly cited "braced" threshold.

    Includes a physical plausibility check as a safety net: a bowler's
    knee cannot legitimately be near a full squat (well under 90 deg)
    at the moment of release - if we see that, it's virtually certain
    to be a leftover tracking glitch, not a real reading, so we widen
    the search to the nearest few frames around release instead of
    trusting a single implausible value."""
    if release_frame is None or front_leg_side is None:
        return None
    if front_leg_side == "left":
        hip, knee, ankle = LEFT_HIP, LEFT_KNEE, LEFT_ANKLE
    else:
        hip, knee, ankle = RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE

    PLAUSIBLE_MIN_DEG = 90  # a real release-frame knee angle is never a near-full squat

    def angle_at(frame_idx):
        if frame_idx < 0 or frame_idx >= len(all_keypoints):
            return None
        kpts = all_keypoints[frame_idx]
        if kpts is None:
            return None
        return joint_angle_deg(kpts, hip, knee, ankle)

    angle = angle_at(release_frame)
    if angle is not None and angle >= PLAUSIBLE_MIN_DEG:
        return angle

    # Implausible or missing - check the frame right before and after;
    # release-frame motion blur is the most likely cause of a bad
    # single-frame reading here.
    for offset in (-1, 1, -2, 2):
        candidate = angle_at(release_frame + offset)
        if candidate is not None and candidate >= PLAUSIBLE_MIN_DEG:
            return candidate

    return angle  # give up and return whatever we had, even if implausible


def compute_leading_arm_profile(all_keypoints, front_foot_frame, release_frame, bowling_arm_side):
    """Metric #3 - INFO/qualitative flag. Research is split on the exact
    ideal path, but both schools agree the leading arm should stay
    ACTIVE (not collapse low) from front foot contact through release.
    We track the shoulder-elbow-wrist angle across that window and
    report the minimum (most collapsed) value."""
    if front_foot_frame is None or release_frame is None or release_frame <= front_foot_frame:
        return None
    leading_side = "left" if bowling_arm_side == "right" else "right"
    if leading_side == "left":
        shoulder, elbow, wrist = LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST
    else:
        shoulder, elbow, wrist = RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST

    angles = []
    for i in range(front_foot_frame, release_frame + 1):
        kpts = all_keypoints[i]
        if kpts is None:
            continue
        a = joint_angle_deg(kpts, shoulder, elbow, wrist)
        if a is not None:
            angles.append(a)

    if not angles:
        return None
    return {
        "min_angle": min(angles),
        "angle_at_release": angles[-1],
        "leading_side": leading_side,
    }


def compute_bowling_arm_arc(all_keypoints, back_foot_frame, release_frame, bowling_arm_side):
    """Metric #4 - INFO only (no established threshold in the research
    reviewed). Tracks the shoulder-to-wrist vector's angle over time
    across the delivery stride and reports the total sweep in degrees,
    as a rough proxy for "how big/free the arm circle is"."""
    if back_foot_frame is None or release_frame is None or release_frame <= back_foot_frame:
        return None
    if bowling_arm_side == "left":
        shoulder, wrist = LEFT_SHOULDER, LEFT_WRIST
    else:
        shoulder, wrist = RIGHT_SHOULDER, RIGHT_WRIST

    angles_deg = []
    for i in range(back_foot_frame, release_frame + 1):
        kpts = all_keypoints[i]
        s, w = _xy(kpts, shoulder), _xy(kpts, wrist)
        if s is None or w is None:
            continue
        vec = w - s
        angles_deg.append(np.degrees(np.arctan2(vec[1], vec[0])))

    if len(angles_deg) < 2:
        return None

    # Unwrap so the angle doesn't jump +/-180 as the arm swings past
    # straight down/up - without this, a genuine big swing can look
    # like several small ones.
    unwrapped = np.degrees(np.unwrap(np.radians(angles_deg)))
    sweep = float(np.max(unwrapped) - np.min(unwrapped))
    return {"arc_sweep_degrees": sweep}


def compute_wrist_snap(wrist_speed, release_frame, fps, lookback_frames=4):
    """Metric #5 - INFO (descriptive, "broadcast graphic" style). Peak
    wrist speed at release, plus how sharply it ramped up just before
    release (a real "snap" is a late, sharp spike - not a gradual
    ramp). Speed is in pixels/frame (see module docstring on units)."""
    if release_frame is None or release_frame >= len(wrist_speed):
        return None
    peak_speed = float(wrist_speed[release_frame])
    lookback_idx = max(0, release_frame - lookback_frames)
    speed_before = float(wrist_speed[lookback_idx])
    frames_elapsed = max(1, release_frame - lookback_idx)
    snap_ramp = (peak_speed - speed_before) / frames_elapsed  # accel-like measure
    return {
        "peak_wrist_speed_px_per_frame": peak_speed,
        "snap_ramp_px_per_frame_squared": snap_ramp,
    }


def compute_run_up_speed(all_keypoints, back_foot_frame, fps, window_seconds=1.0):
    """Metric #2 - TREND (high-confidence that it matters, but NOT
    calibrated to real-world units here - see module docstring). Uses
    the hip midpoint's horizontal displacement per frame, averaged over
    the ~1 second before back foot contact."""
    if back_foot_frame is None:
        return None
    window_frames = int(fps * window_seconds)
    start = max(1, back_foot_frame - window_frames)

    speeds = []
    for i in range(start, back_foot_frame):
        prev_kpts = all_keypoints[i - 1]
        curr_kpts = all_keypoints[i]
        lh_prev, rh_prev = _xy(prev_kpts, LEFT_HIP), _xy(prev_kpts, RIGHT_HIP)
        lh_curr, rh_curr = _xy(curr_kpts, LEFT_HIP), _xy(curr_kpts, RIGHT_HIP)
        if lh_prev is None or rh_prev is None or lh_curr is None or rh_curr is None:
            continue
        prev_mid = (lh_prev + rh_prev) / 2
        curr_mid = (lh_curr + rh_curr) / 2
        speeds.append(abs(curr_mid[0] - prev_mid[0]))  # horizontal only

    if not speeds:
        return None
    return {
        "avg_run_up_speed_px_per_frame": float(np.mean(speeds)),
        "accelerating": speeds[-1] > speeds[0] if len(speeds) > 1 else None,
    }


def compute_trunk_bend_angle(all_keypoints, frame_idx):
    """Metric #6 - TREND (moderate confidence). The "back bend" number:
    angle of the trunk (shoulder-midpoint to hip-midpoint line - the
    same line drawn on the skeleton) relative to straight-up vertical.
    0 deg = perfectly upright, larger = more lean/bend.

    This is what the research doc calls trunk lateral flexion - roughly
    20 deg at release has been associated with faster deliveries in
    some sources, BUT it's paired with a real lower-back stress
    association, not a free upgrade. Report this as a number, not a
    pass/fail verdict."""
    if frame_idx is None or frame_idx >= len(all_keypoints):
        return None
    kpts = all_keypoints[frame_idx]
    ls, rs = _xy(kpts, LEFT_SHOULDER), _xy(kpts, RIGHT_SHOULDER)
    lh, rh = _xy(kpts, LEFT_HIP), _xy(kpts, RIGHT_HIP)
    if ls is None or rs is None or lh is None or rh is None:
        return None

    shoulder_mid = (ls + rs) / 2
    hip_mid = (lh + rh) / 2
    trunk_vec = shoulder_mid - hip_mid  # points from hip up to shoulder
    vertical_vec = np.array([0, -1])    # "up" in image coordinates (y decreases upward)

    norm = np.linalg.norm(trunk_vec)
    if norm == 0:
        return None
    cos_angle = np.dot(trunk_vec, vertical_vec) / norm
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_angle)))


def build_report(all_keypoints, fps, bowling_arm, back_foot_frame, front_foot_frame,
                  release_frame, left_ankle_vspeed, right_ankle_vspeed,
                  left_wrist_speed, right_wrist_speed, front_leg_side):
    """Runs every metric and returns one dict - this is what gets
    printed and written to the report/CSV. front_leg_side comes from
    the caller (pipeline determines it as "opposite the bowling arm" -
    a fixed bowling-mechanics fact, not something this module should
    be guessing from noisy pixels)."""
    wrist_speed = right_wrist_speed if bowling_arm == "right" else left_wrist_speed

    report = {}

    knee_angle = compute_front_knee_angle_at_release(all_keypoints, release_frame, front_leg_side)
    report["front_knee_angle_release_deg"] = knee_angle
    report["front_leg_side"] = front_leg_side
    if knee_angle is not None:
        report["front_knee_flag"] = "BRACED (good)" if knee_angle >= 150 else "LESS BRACED - may indicate reduced transfer from run-up"

    run_up = compute_run_up_speed(all_keypoints, back_foot_frame, fps) or {}
    report.update({f"run_up_{k}": v for k, v in run_up.items()})

    leading_arm = compute_leading_arm_profile(all_keypoints, front_foot_frame, release_frame, bowling_arm) or {}
    report.update({f"leading_arm_{k}": v for k, v in leading_arm.items()})
    if "min_angle" in leading_arm:
        report["leading_arm_flag"] = "STAYED ACTIVE (good)" if leading_arm["min_angle"] >= 90 else "COLLAPSED LOW - both schools of thought flag this as a fault"

    arc = compute_bowling_arm_arc(all_keypoints, back_foot_frame, release_frame, bowling_arm) or {}
    report.update({f"bowling_arm_{k}": v for k, v in arc.items()})

    snap = compute_wrist_snap(wrist_speed, release_frame, fps) or {}
    report.update(snap)


    return report


def report_lines_for_display(report):
    """Turns the report dict into short human-readable lines for
    printing to console / drawing on the video."""
    lines = []
    if report.get("front_knee_angle_release_deg") is not None:
        lines.append(f"Front knee @ release: {report['front_knee_angle_release_deg']:.0f} deg - {report.get('front_knee_flag', '')}")
    if report.get("run_up_avg_run_up_speed_px_per_frame") is not None:
        acc = report.get("run_up_accelerating")
        acc_txt = "accelerating into BFC" if acc else ("NOT accelerating - check run-up rhythm" if acc is False else "")
        lines.append(f"Run-up speed (relative): {report['run_up_avg_run_up_speed_px_per_frame']:.1f} px/frame - {acc_txt}")
    if report.get("leading_arm_min_angle") is not None:
        lines.append(f"Leading arm min angle: {report['leading_arm_min_angle']:.0f} deg - {report.get('leading_arm_flag', '')}")
    if report.get("bowling_arm_arc_sweep_degrees") is not None:
        lines.append(f"Bowling arm arc sweep: {report['bowling_arm_arc_sweep_degrees']:.0f} deg (info only)")
    if report.get("peak_wrist_speed_px_per_frame") is not None:
        lines.append(f"Peak wrist speed: {report['peak_wrist_speed_px_per_frame']:.1f} px/frame (info only)")
    if report.get("trunk_bend_angle_release_deg") is not None:
        lines.append(f"Trunk bend @ release: {report['trunk_bend_angle_release_deg']:.1f} deg (info/trend - paired with injury-risk caveat)")
    return lines


def categorize_report(report):
    """Same three-section shape, now in plain, jargon-free language for
    first-time users with no sports-science background."""
    improvements = []
    plus_points = []
    stats = []

    knee = report.get("front_knee_angle_release_deg")
    if knee is not None:
        if knee >= 150:
            plus_points.append(
                f"Front leg brace: Good — your front leg is nearly straight when the ball leaves your hand "
                f"({knee:.0f} degrees). This helps turn your run-up speed into extra pace."
            )
        else:
            improvements.append(
                f"Front leg brace: Your front leg is quite bent when the ball leaves your hand ({knee:.0f} degrees). "
                f"A straighter front leg at this exact moment usually helps bowl faster — though this can also "
                f"just mean you need more speed coming in from your run-up, not just a straighter knee."
            )

    leading_min = report.get("leading_arm_min_angle")
    if leading_min is not None:
        if leading_min >= 90:
            plus_points.append("Non-bowling arm: Good — it stayed up and active through your action, which helps power your bowling arm.")
        else:
            improvements.append("Non-bowling arm: It dropped down too early during your action. Keeping this arm up for longer usually adds extra power to your bowling arm.")

    run_up_speed = report.get("run_up_avg_run_up_speed_px_per_frame")
    if run_up_speed is not None:
        acc = report.get("run_up_accelerating")
        if acc:
            stats.append("Run-up speed: Good — you're still speeding up right before you plant your back foot, which is one of the biggest things linked to bowling fast.")
        else:
            stats.append("Run-up speed: You don't seem to be speeding up much right before your back foot lands. Try building up speed gradually through your run so you're fastest right at the crease.")

    arc = report.get("bowling_arm_arc_sweep_degrees")
    if arc is not None:
        stats.append(
            f"Bowling arm swing: Your bowling arm swings through about {arc:.0f} degrees before you release the ball. "
            f"There's no fixed 'correct' number for this — it's most useful for comparing your own deliveries against each other over time."
        )

    peak_wrist = report.get("peak_wrist_speed_px_per_frame")
    if peak_wrist is not None:
        stats.append(f"Wrist speed at release: {peak_wrist:.1f} (a relative number, not real km/h yet — useful to track if it's going up or down across your own deliveries).")

    return {"improvements": improvements, "plus_points": plus_points, "stats": stats}
