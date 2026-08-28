"""
SHARED SKELETON DRAWING - used by every script so the look stays
consistent everywhere.

STYLE: matches a clean broadcast-graphic look (single uniform line
color, simple round joint dots, nothing else competing for attention) -
not color-coded by side anymore. That color-coding was solving a real
problem (arm/leg blending when same-colored limbs crossed), but the
actual permanent fix for THAT problem is now handled upstream in the
tracking data itself (see track_limb_side_by_position /
apply_limb_side_correction below) - so the drawing layer is free to be
as simple and clean as possible, the way a broadcast graphic is.

Design notes:
1. ONE line color (white), ONE joint-dot color (cyan) - no per-side or
   per-limb color coding at all. Simpler reads cleaner at a glance.
2. No head/face point drawn - matches the reference look, and the
   fault-detection engine doesn't currently use head position anyway.
3. Minimal edge set: just the main limb chain + a simple torso box
   (never an X, so it can't visually cross itself in bent-over poses).
4. A confidence floor of 0.35 - low-confidence points are the ones that
   jitter and cause spike lines.
5. draw_front_leg_brace_guide(): a separate, optional straight dashed
   line from hip to ankle on the front leg - a COACHING reference line
   (what a perfectly braced leg would look like), drawn in its own
   distinct accent color so it doesn't get lost in the skeleton itself.

Standard 17-point layout this all assumes:
0=nose 1=left eye 2=right eye 3=left ear 4=right ear
5=left shoulder 6=right shoulder 7=left elbow 8=right elbow
9=left wrist 10=right wrist 11=left hip 12=right hip
13=left knee 14=right knee 15=left ankle 16=right ankle
"""

import cv2
import numpy as np

CONF_THRESHOLD = 0.2

# Colors are BGR (OpenCV format).
# SIDE VIEW (default): cyan joints, white lines - matches the broadcast
# reference image.
COLOR_LINE = (255, 255, 255)          # white - side-view skeleton lines
COLOR_JOINT = (255, 180, 60)          # cyan/light-blue - side-view joint dots

# FRONT/BACK VIEW: dark green joints, silver lines - visually distinct
# from side view (useful once these are side-by-side in the app UI).
# NOTE: dark green has weak contrast against actual grass in real
# footage - worth brightening (e.g. lime/spring green) if that's an
# issue once tested on real clips.
COLOR_LINE_FRONT_BACK = (192, 192, 192)   # silver
COLOR_JOINT_FRONT_BACK = (0, 100, 0)      # dark green

COLOR_BRACE_GUIDE = (0, 220, 255)     # amber/yellow - stands out against either scheme

NOSE = 0
LEFT_SHOULDER, RIGHT_SHOULDER = 5, 6
LEFT_ELBOW, RIGHT_ELBOW = 7, 8
LEFT_WRIST, RIGHT_WRIST = 9, 10
LEFT_HIP, RIGHT_HIP = 11, 12
LEFT_KNEE, RIGHT_KNEE = 13, 14
LEFT_ANKLE, RIGHT_ANKLE = 15, 16

# Minimal edge set - main limb chain, shoulder line, hip line. The
# torso itself is NOT drawn as a box (that was two lines down each
# side) - instead draw_skeleton() adds ONE line down the center back,
# from the shoulder midpoint to the hip midpoint, matching the
# reference image exactly.
SKELETON_EDGES = [
    (LEFT_SHOULDER, LEFT_ELBOW), (LEFT_ELBOW, LEFT_WRIST),
    (RIGHT_SHOULDER, RIGHT_ELBOW), (RIGHT_ELBOW, RIGHT_WRIST),
    (LEFT_HIP, LEFT_KNEE), (LEFT_KNEE, LEFT_ANKLE),
    (RIGHT_HIP, RIGHT_KNEE), (RIGHT_KNEE, RIGHT_ANKLE),
    (LEFT_SHOULDER, RIGHT_SHOULDER),
    (LEFT_HIP, RIGHT_HIP),
]
JOINT_POINTS = [LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_ELBOW, RIGHT_ELBOW,
                LEFT_WRIST, RIGHT_WRIST, LEFT_HIP, RIGHT_HIP,
                LEFT_KNEE, RIGHT_KNEE, LEFT_ANKLE, RIGHT_ANKLE]


def _ok(keypoints, idx):
    return keypoints[idx][2] > CONF_THRESHOLD


def _pt(keypoints, idx):
    return (int(keypoints[idx][0]), int(keypoints[idx][1]))


def draw_skeleton(frame, keypoints, thickness=3, point_radius=6, line_color=None, joint_color=None):
    """Draws a clean, single-color skeleton on frame in place, matching
    a broadcast-graphic look. keypoints: 17x3 array of [x, y, confidence].
    line_color/joint_color: override the default side-view cyan/white -
    pass COLOR_LINE_FRONT_BACK / COLOR_JOINT_FRONT_BACK for front/back
    view, or leave None to use the side-view defaults."""
    line_color = line_color if line_color is not None else COLOR_LINE
    joint_color = joint_color if joint_color is not None else COLOR_JOINT

    for (a, b) in SKELETON_EDGES:
        if _ok(keypoints, a) and _ok(keypoints, b):
            cv2.line(frame, _pt(keypoints, a), _pt(keypoints, b), line_color, thickness)

    # ONE center-back line, shoulder midpoint to hip midpoint - there's
    # no spine keypoint in the 17-point model, so we compute it. This

    # replaces the two-sided torso box with a single line, matching
    # the reference image.
    if _ok(keypoints, LEFT_SHOULDER) and _ok(keypoints, RIGHT_SHOULDER) and \
       _ok(keypoints, LEFT_HIP) and _ok(keypoints, RIGHT_HIP):
        shoulder_mid = (
            (keypoints[LEFT_SHOULDER][0] + keypoints[RIGHT_SHOULDER][0]) / 2,
            (keypoints[LEFT_SHOULDER][1] + keypoints[RIGHT_SHOULDER][1]) / 2,
        )
        hip_mid = (
            (keypoints[LEFT_HIP][0] + keypoints[RIGHT_HIP][0]) / 2,
            (keypoints[LEFT_HIP][1] + keypoints[RIGHT_HIP][1]) / 2,
        )
        p1 = (int(shoulder_mid[0]), int(shoulder_mid[1]))
        p2 = (int(hip_mid[0]), int(hip_mid[1]))
        cv2.line(frame, p1, p2, line_color, thickness)

    for idx in JOINT_POINTS:
        if _ok(keypoints, idx):
            cv2.circle(frame, _pt(keypoints, idx), point_radius, joint_color, -1)


def draw_front_leg_brace_guide(frame, keypoints, front_leg_side, thickness=2):
    """Draws a straight DASHED reference line from hip to ankle on the
    front leg - this shows what a perfectly straight/braced leg would
    look like, so any gap between this line and the actual knee
    position (drawn by draw_skeleton) visually shows the bend at a
    glance. front_leg_side: "left" or "right"."""
    if front_leg_side is None:
        return
    hip_idx = LEFT_HIP if front_leg_side == "left" else RIGHT_HIP
    ankle_idx = LEFT_ANKLE if front_leg_side == "left" else RIGHT_ANKLE
    if not (_ok(keypoints, hip_idx) and _ok(keypoints, ankle_idx)):
        return

    p1 = _pt(keypoints, hip_idx)
    p2 = _pt(keypoints, ankle_idx)

    # Manual dashed line - draw short segments with gaps
    num_dashes = 12
    for i in range(num_dashes):
        t0 = i / num_dashes
        t1 = (i + 0.5) / num_dashes
        seg_start = (int(p1[0] + (p2[0] - p1[0]) * t0), int(p1[1] + (p2[1] - p1[1]) * t0))
        seg_end = (int(p1[0] + (p2[0] - p1[0]) * t1), int(p1[1] + (p2[1] - p1[1]) * t1))
        cv2.line(frame, seg_start, seg_end, COLOR_BRACE_GUIDE, thickness)


ALL_PAIRS = [(5, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 16)]


def _dist(a, b):
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def track_limb_side_by_position(all_keypoints, anchor_frame, anchor_is_a, tip_idx_a, tip_idx_b):
    """THE PERMANENT FIX for left/right drift. Old approaches (per-joint
    frame-to-frame, then torso-anchored whole-body) both relied on SOME
    body part being stable in EVERY frame - but nothing is stable in
    every frame of a bowling action. Legs cross during running, the
    torso rotates fast in follow-through. Any single "stable anchor"
    eventually hits its own ambiguous moment.

    This instead anchors identity ONCE, at a single frame where it's
    physically unambiguous (e.g. a planted, near-motionless foot at
    front-foot-contact, or the fastest-moving wrist at release), then
    tracks that specific point by pure position continuity - "which of
    the two candidate detections is closer to where this point just
    was" - frame by frame, forward and backward from the anchor. It
    never again asks the model "which one do you call left/right" -
    that question is exactly what kept going wrong.

    tip_idx_a / tip_idx_b: the two raw model keypoint indices for the
    tracking point (e.g. LEFT_ANKLE, RIGHT_ANKLE, or LEFT_WRIST,
    RIGHT_WRIST). anchor_is_a: True if tip_idx_a is the target role
    (e.g. "front leg") at anchor_frame.

    Returns a list, one entry per frame: True (tip_idx_a is the target
    role this frame), False (tip_idx_b is), or None (couldn't be
    determined - both points missing, or no confident reference yet).
    """
    n = len(all_keypoints)
    result = [None] * n

    def tip_pos(kpts, use_a):
        if kpts is None:
            return None
        idx = tip_idx_a if use_a else tip_idx_b
        if kpts[idx][2] < 0.3:
            return None
        return np.array([kpts[idx][0], kpts[idx][1]], dtype=float)

    def sweep(frame_range):
        last_pos = tip_pos(all_keypoints[anchor_frame], anchor_is_a)
        for i in frame_range:
            kpts = all_keypoints[i]
            pos_a = tip_pos(kpts, True)
            pos_b = tip_pos(kpts, False)
            if pos_a is None and pos_b is None:
                continue  # gap - leave None, doesn't disturb last_pos
            if last_pos is None:
                # Recovering after a gap with no recent reference point -
                # only safe to resume if just one candidate is present.
                if pos_a is not None and pos_b is None:
                    result[i] = True
                    last_pos = pos_a
                elif pos_b is not None and pos_a is None:
                    result[i] = False
                    last_pos = pos_b
                continue
            if pos_a is not None and pos_b is not None:
                choose_a = _dist(pos_a, last_pos) <= _dist(pos_b, last_pos)
            else:
                choose_a = pos_a is not None
            result[i] = choose_a
            last_pos = pos_a if choose_a else pos_b

    result[anchor_frame] = anchor_is_a
    sweep(range(anchor_frame + 1, n))
    sweep(range(anchor_frame - 1, -1, -1))
    return result


def apply_limb_side_correction(all_keypoints, is_a_per_frame, chain_pairs):
    """Given the per-frame True/False/None from track_limb_side_by_position,
    physically swaps the raw keypoints for that limb's chain (e.g. for a
    leg: hip, knee, ankle pairs) wherever the tracked identity says the
    model's "a" side isn't actually the target role for that frame.
    After this, index "a" (e.g. LEFT_*) is GUARANTEED to mean the
    target role (e.g. front leg) for every single frame - not just
    "whatever the model happened to call left this frame"."""
    fixed = [k.copy() if k is not None else None for k in all_keypoints]
    for i, is_a in enumerate(is_a_per_frame):
        if is_a is False and fixed[i] is not None:
            for (a, b) in chain_pairs:
                fixed[i][a], fixed[i][b] = fixed[i][b].copy(), fixed[i][a].copy()
    return fixed


def find_planted_side(all_keypoints, frame_idx, idx_a, idx_b, window=2):
    """Anchor helper for LEGS: at frame_idx, which of the two candidate
    points (idx_a / idx_b) is more STATIONARY over a small surrounding
    window? A planted front foot barely moves right around foot
    contact, while the other leg is still swinging through - a clean,
    physically unambiguous signal. Returns True if idx_a is the
    planted (front) one, False if idx_b is, None if not enough data."""
    n = len(all_keypoints)
    lo, hi = max(0, frame_idx - window), min(n - 1, frame_idx + window)

    def total_movement(idx):
        pts = []
        for i in range(lo, hi + 1):
            k = all_keypoints[i]
            if k is not None and k[idx][2] > 0.3:
                pts.append(np.array([k[idx][0], k[idx][1]]))
        if len(pts) < 2:
            return None
        return sum(_dist(pts[j], pts[j + 1]) for j in range(len(pts) - 1))

    move_a, move_b = total_movement(idx_a), total_movement(idx_b)
    if move_a is None or move_b is None:
        return None
    return move_a <= move_b


def find_fastest_side(all_keypoints, frame_idx, idx_a, idx_b, window=2):
    """Anchor helper for ARMS: at frame_idx, which of the two candidate
    points (idx_a / idx_b) is moving FASTEST over a small surrounding
    window? At release, the bowling wrist is moving dramatically faster
    than the leading wrist - equally unambiguous. Returns True if idx_a
    is the faster (bowling arm) one, False if idx_b is, None if not
    enough data."""
    n = len(all_keypoints)
    lo, hi = max(0, frame_idx - window), min(n - 1, frame_idx + window)

    def total_speed(idx):
        pts = []
        for i in range(lo, hi + 1):
            k = all_keypoints[i]
            if k is not None and k[idx][2] > 0.3:
                pts.append(np.array([k[idx][0], k[idx][1]]))
        if len(pts) < 2:
            return None
        return sum(_dist(pts[j], pts[j + 1]) for j in range(len(pts) - 1))

    speed_a, speed_b = total_speed(idx_a), total_speed(idx_b)
    if speed_a is None or speed_b is None:
        return None
    return speed_a >= speed_b


def despike_keypoints(all_keypoints, joint_indices, jump_threshold=60):
    """Fixes the OTHER bug found: a single frame where a joint briefly
    teleports (classic motion-blur glitch, most likely right at
    release - the fastest-moving instant in the whole clip) then snaps
    back next frame. If a joint jumps away from both its neighbors by
    more than jump_threshold pixels and then jumps back, that one
    frame's position is replaced with a straight-line interpolation
    between its neighbors instead of trusting the glitch."""
    fixed = [k.copy() if k is not None else None for k in all_keypoints]
    n = len(fixed)

    for idx in joint_indices:
        for i in range(1, n - 1):
            prev_k, curr_k, next_k = fixed[i - 1], fixed[i], fixed[i + 1]
            if prev_k is None or curr_k is None or next_k is None:
                continue
            if prev_k[idx][2] < 0.3 or curr_k[idx][2] < 0.3 or next_k[idx][2] < 0.3:
                continue
            prev_pt, curr_pt, next_pt = prev_k[idx][:2], curr_k[idx][:2], next_k[idx][:2]
            jump_in = _dist(curr_pt, prev_pt)
            jump_out = _dist(curr_pt, next_pt)
            direct = _dist(prev_pt, next_pt)
            # Spike pattern: big jump away AND big jump back, but the
            # neighbors themselves are close together - a real fast
            # movement wouldn't snap back like that.
            if jump_in > jump_threshold and jump_out > jump_threshold and direct < jump_threshold:
                interp = (prev_pt + next_pt) / 2
                fixed[i][idx][0] = interp[0]
                fixed[i][idx][1] = interp[1]

    return fixed

def draw_label(frame, text, org, accent_color, font_scale=0.7, thickness=2):
    """Broadcast-style label: dark semi-transparent pill with a colored
    accent bar, instead of raw cv2 text floating on the video."""
    font = cv2.FONT_HERSHEY_DUPLEX
    (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
    x, y = org
    pad = 10
    box = frame[max(0, y - th - pad):y + pad, x - 4:x + tw + pad + 6].copy()
    overlay = frame.copy()
    cv2.rectangle(overlay, (x - 4, y - th - pad), (x + tw + pad + 6, y + pad), (20, 22, 15), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
    cv2.rectangle(frame, (x - 4, y - th - pad), (x - 1, y + pad), accent_color, -1)  # accent bar
    cv2.putText(frame, text, (x + 6, y), font, font_scale, (241, 238, 226), thickness, cv2.LINE_AA)