"""
RUN PIPELINE: Does everything in one go - finds the bowler, tracks them,
draws the skeleton, figures out back foot / front foot / release, and
saves ONE labeled output video.

CHANGE LOG (perf attempts, most recent first):
- REVERTED torch.set_num_threads(os.cpu_count()) - on a hyperthreaded
  CPU this can cause thread oversubscription and made things SLOWER in
  testing, not faster. Removed.
- REVERTED auto-OpenVINO loading - OpenVINO's export defaults to a
  640x640 input, so feeding it 1536px frames added resize overhead
  instead of saving time. Made things slower in testing. Removed - if
  you want to revisit OpenVINO later, it needs to be exported/run at
  the SAME resolution you actually use, not left as a default mismatch.
- KEPT: model loaded once per process and cached (_MODEL_CACHE) - real,
  safe win, no accuracy cost. Avoids reloading from disk on every
  request under the web server.
- KEPT: Pass 2 reuses frames cached during Pass 1 instead of re-opening
  and re-decoding the video file a second time - real, safe I/O win,
  identical pixel data either way.
- KEPT: timing instrumentation (prints exactly where time goes: Pass 1
  tracking, Pass 2 rendering, ffmpeg transcode) - this is what actually
  tells us where to optimize next, instead of guessing.
- inference_max_dim default back to 1280 (was pushed to 1536 to help
  back-view accuracy, but that costs real time - 1280 is the more
  speed-reasonable default; raise it back to 1536 only if back-view
  detection quality specifically needs it, per its own tradeoff).

HOW TO RUN:
    python src/run_pipeline.py videos/raw/my_delivery.mp4
    python src/run_pipeline.py videos/raw/my_delivery.mp4 --id 3
    python src/run_pipeline.py videos/raw/my_delivery.mp4 --start 2 --end 6
    python src/run_pipeline.py videos/raw/my_delivery.mp4 --view front

OUTPUT:
    videos/output/output_pipeline_<view>.mp4
    results/phase_graph_<video name>_<view>.png
    results/report_<video name>_<view>.md
    results/all_deliveries.csv

NOTE ON UNITS: speeds are pixels/frame, not real km/h - no camera
calibration yet, only meaningful for comparing deliveries from the
same camera position.
"""

import sys
import os
import csv
import datetime
import time
import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")  # non-interactive backend - MUST be set before importing
                        # pyplot, or it can hang when called from a background
                        # worker thread (as it is here under the web server).
import matplotlib.pyplot as plt
from ultralytics import YOLO
from skeleton_utils import (
    draw_skeleton, draw_front_leg_brace_guide, despike_keypoints,
    track_limb_side_by_position, apply_limb_side_correction,
    find_planted_side, find_fastest_side,
)
import skeleton_utils as su
import fault_detection as fd
import fault_detection_front_back as fdfb

LEFT_WRIST, RIGHT_WRIST = 9, 10
LEFT_ELBOW, RIGHT_ELBOW = 7, 8
LEFT_SHOULDER, RIGHT_SHOULDER = 5, 6
LEFT_ANKLE, RIGHT_ANKLE = 15, 16
LEFT_KNEE, RIGHT_KNEE = 13, 14
LEFT_HIP, RIGHT_HIP = 11, 12


def box_center(box):
    x1, y1, x2, y2 = box
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def box_area(box):
    x1, y1, x2, y2 = box
    return max(0, x2 - x1) * max(0, y2 - y1)


def smooth(signal, window=3):
    signal = np.array(signal, dtype=float)
    kernel = np.ones(window) / window
    return np.convolve(signal, kernel, mode="same")


def get_xy(frame_kpts, idx):
    if frame_kpts is None or frame_kpts[idx][2] < 0.3:
        return None
    return frame_kpts[idx][0], frame_kpts[idx][1]


def resize_for_inference(frame, max_dim):
    """Shrinks a frame before feeding it to YOLO, if larger than
    needed - inference time scales with pixel count. The ORIGINAL
    full-res frame is still used for drawing the skeleton later - only
    the copy fed to the model gets shrunk. Returns (frame_for_model,
    scale) - scale maps detected coordinates back to original size."""
    h, w = frame.shape[:2]
    longest = max(h, w)
    if longest <= max_dim:
        return frame, 1.0
    scale = max_dim / float(longest)
    resized = cv2.resize(frame, (int(round(w * scale)), int(round(h * scale))))
    return resized, scale


_MODEL_CACHE = {}


def get_model(model_name):
    """Loads the model once per process and reuses it - loading from
    disk on every single request added real, unnecessary delay under
    the web server. Plain .pt loading only now (no OpenVINO auto-swap -
    see change log above for why that was reverted)."""
    if model_name not in _MODEL_CACHE:
        print(f"Loading model ({model_name}) - first time this process has needed it...")
        _MODEL_CACHE[model_name] = YOLO(model_name)
    return _MODEL_CACHE[model_name]


def analyze_video(video_path, view="side", start_seconds=0.0, end_seconds=None,
                   manual_id=None, model_name="yolo11m-pose.pt", output_dir=".",
                   inference_max_dim=960):
    """
    The actual reusable pipeline function. Returns a dict with paths to
    the output video/report/graph, the categorized report, and the raw
    numbers.
    """
    pipeline_start_time = time.monotonic()

    if view not in ("side", "front", "back"):
        print(f"Unknown --view '{view}', defaulting to 'side'.")
        view = "side"
    print(f"View mode: {view}")

    print(f"Loading model ({model_name})...")
    model = get_model(model_name)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Could not open video: {video_path}")
        return {"success": False, "error": f"Could not open video: {video_path}"}

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    start_frame = int(start_seconds * fps)
    end_frame = int(end_seconds * fps) if end_seconds is not None else total_frames
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    print(f"Processing frames {start_frame} to {end_frame} (of {total_frames} total)...")

    # ---- PASS 1: track everyone, auto-pick the bowler, record joints ----
    pass1_start_time = time.monotonic()
    print("Pass 1: tracking people and finding the bowler...")
    all_keypoints = []
    raw_frames = []  # cached so Pass 2 doesn't have to re-decode the video from disk
    locked_id = manual_id
    center_history = []
    last_bowler_height = None
    frame_counter = start_frame

    while True:
        if frame_counter >= end_frame:
            break
        success, frame = cap.read()
        if not success:
            break
        raw_frames.append(frame)

        infer_frame, scale = resize_for_inference(frame, inference_max_dim) if inference_max_dim else (frame, 1.0)
        results = model.track(infer_frame, persist=True, tracker="botsort.yaml", verbose=False)
        r = results[0]
        chosen_idx = None

        if r.boxes is not None and r.boxes.id is not None:
            ids = r.boxes.id.int().tolist()
            boxes_xyxy = r.boxes.xyxy.cpu().numpy()
            if scale != 1.0:
                boxes_xyxy = boxes_xyxy / scale

            if locked_id is None:
                areas = [box_area(b) for b in boxes_xyxy]
                pick = int(np.argmax(areas))
                locked_id = ids[pick]
                chosen_idx = pick
                print(f"Auto-picked bowler as tracker ID {locked_id} "
                      f"(largest person in frame {frame_counter}). "
                      f"If this is wrong, rerun with --id N.")
            elif locked_id in ids:
                chosen_idx = ids.index(locked_id)
            elif len(center_history) >= 1:
                if len(center_history) >= 2:
                    (prev2_center, prev2_gap), (prev1_center, prev1_gap) = center_history[-2], center_history[-1]
                    velocity = (
                        (prev1_center[0] - prev2_center[0]) / max(1, prev1_gap),
                        (prev1_center[1] - prev2_center[1]) / max(1, prev1_gap),
                    )
                else:
                    velocity = (0.0, 0.0)

                last_center = center_history[-1][0]
                predicted_center = (last_center[0] + velocity[0], last_center[1] + velocity[1])

                candidates = []
                for j, b in enumerate(boxes_xyxy):
                    c = box_center(b)
                    box_h = b[3] - b[1]
                    dist = np.hypot(c[0] - predicted_center[0], c[1] - predicted_center[1])
                    size_ratio = (box_h / last_bowler_height) if last_bowler_height else 1.0
                    size_ok = 0.6 <= size_ratio <= 1.6
                    dist_ok = dist < box_h * 0.9
                    candidates.append((j, dist, size_ok, dist_ok))

                valid = [c for c in candidates if c[2] and c[3]]
                if valid:
                    min_idx = min(valid, key=lambda c: c[1])[0]
                    chosen_idx = min_idx
                    locked_id = ids[min_idx]
                    print(f"Recovered lost track at frame {frame_counter} - "
                          f"re-locked onto tracker ID {locked_id} (velocity-predicted position + size check)")

        if chosen_idx is not None:
            center = box_center(boxes_xyxy[chosen_idx])
            height = boxes_xyxy[chosen_idx][3] - boxes_xyxy[chosen_idx][1]
            center_history.append((center, 1))
            center_history = center_history[-5:]
            last_bowler_height = height
            kpts = r.keypoints.data[chosen_idx].cpu().numpy()
            if scale != 1.0:
                kpts = kpts.copy()
                kpts[:, 0] /= scale
                kpts[:, 1] /= scale
            all_keypoints.append(kpts)
        else:
            if center_history:
                last_center, last_gap = center_history[-1]
                center_history[-1] = (last_center, last_gap + 1)
            all_keypoints.append(None)

        frame_counter += 1

    cap.release()
    n_frames = len(all_keypoints)
    pass1_elapsed = time.monotonic() - pass1_start_time
    print(f"Pass 1 took {pass1_elapsed:.1f}s ({pass1_elapsed / max(1, n_frames):.3f}s/frame)")
    print(f"Tracked {n_frames} frames.")

    if n_frames == 0 or all(k is None for k in all_keypoints):
        print("No person was tracked at all - check the video path and try again.")
        return {"success": False, "error": "No person was detected/tracked in this video."}

    print("Fixing single-frame motion-blur spikes...")
    all_keypoints = despike_keypoints(all_keypoints, joint_indices=[LEFT_WRIST, RIGHT_WRIST, LEFT_ANKLE, RIGHT_ANKLE])

    left_wrist_speed = [0.0]
    right_wrist_speed = [0.0]
    left_ankle_vspeed = [0.0]
    right_ankle_vspeed = [0.0]

    for i in range(1, n_frames):
        for idx, storage, vertical_only in [
            (LEFT_WRIST, left_wrist_speed, False),
            (RIGHT_WRIST, right_wrist_speed, False),
            (LEFT_ANKLE, left_ankle_vspeed, True),
            (RIGHT_ANKLE, right_ankle_vspeed, True),
        ]:
            prev = get_xy(all_keypoints[i - 1], idx)
            curr = get_xy(all_keypoints[i], idx)
            if prev is None or curr is None:
                storage.append(storage[-1])
                continue
            if vertical_only:
                speed = abs(curr[1] - prev[1])
            else:
                speed = np.hypot(curr[0] - prev[0], curr[1] - prev[1])
            storage.append(speed)

    left_wrist_speed = smooth(left_wrist_speed)
    right_wrist_speed = smooth(right_wrist_speed)
    left_ankle_vspeed = smooth(left_ankle_vspeed)
    right_ankle_vspeed = smooth(right_ankle_vspeed)

    edge = min(3, n_frames // 2) if n_frames > 6 else 0
    search_lw = left_wrist_speed[edge:n_frames - edge] if n_frames - edge > edge else left_wrist_speed
    search_rw = right_wrist_speed[edge:n_frames - edge] if n_frames - edge > edge else right_wrist_speed
    max_lw, max_rw = max(search_lw), max(search_rw)

    if max_rw >= max_lw:
        bowling_arm = "right"
        release_frame = edge + int(np.argmax(search_rw))
    else:
        bowling_arm = "left"
        release_frame = edge + int(np.argmax(search_lw))

    print(f"Bowling arm detected as: {bowling_arm}")
    print(f"Release frame detected at: {release_frame} (time {release_frame / fps:.2f}s)")

    combined_ankle_speed = np.minimum(left_ankle_vspeed, right_ankle_vspeed)
    search_start = max(0, release_frame - int(fps * 1.5))
    window = combined_ankle_speed[search_start:release_frame]

    plant_candidates = []
    for i in range(2, len(window) - 2):
        if window[i] <= window[i - 1] and window[i] <= window[i + 1] and window[i] <= window[i - 2] and window[i] <= window[i + 2]:
            plant_candidates.append(search_start + i)

    plant_candidates = sorted(plant_candidates, key=lambda f: release_frame - f)
    front_foot_frame = plant_candidates[0] if len(plant_candidates) > 0 else None
    back_foot_frame = None
    if len(plant_candidates) > 1:
        for cand in plant_candidates[1:]:
            if front_foot_frame - cand > fps * 0.15:
                back_foot_frame = cand
                break

    print(f"Front foot contact detected at frame: {front_foot_frame}")
    print(f"Back foot contact detected at frame: {back_foot_frame}")

    if front_foot_frame is not None:
        leg_anchor_is_a = find_planted_side(all_keypoints, front_foot_frame, LEFT_ANKLE, RIGHT_ANKLE)
        if leg_anchor_is_a is None:
            leg_anchor_is_a = True
        print(f"Front leg anchored at front-foot-contact as: {'left' if leg_anchor_is_a else 'right'} (planted/stationary foot)")
        leg_is_a_per_frame = track_limb_side_by_position(all_keypoints, front_foot_frame, leg_anchor_is_a, LEFT_ANKLE, RIGHT_ANKLE)
        all_keypoints = apply_limb_side_correction(
            all_keypoints, leg_is_a_per_frame,
            chain_pairs=[(LEFT_HIP, RIGHT_HIP), (LEFT_KNEE, RIGHT_KNEE), (LEFT_ANKLE, RIGHT_ANKLE)],
        )

    arm_anchor_is_a = find_fastest_side(all_keypoints, release_frame, LEFT_WRIST, RIGHT_WRIST)
    if arm_anchor_is_a is None:
        arm_anchor_is_a = (bowling_arm == "left")
    print(f"Bowling arm anchored at release as: {'left' if arm_anchor_is_a else 'right'} (fastest-moving wrist)")
    bowling_arm = "left" if arm_anchor_is_a else "right"
    arm_is_a_per_frame = track_limb_side_by_position(all_keypoints, release_frame, arm_anchor_is_a, LEFT_WRIST, RIGHT_WRIST)
    all_keypoints = apply_limb_side_correction(
        all_keypoints, arm_is_a_per_frame,
        chain_pairs=[(LEFT_SHOULDER, RIGHT_SHOULDER), (LEFT_ELBOW, RIGHT_ELBOW), (LEFT_WRIST, RIGHT_WRIST)],
    )

    front_leg_side = "left"
    bowling_arm_for_computation = "left"

    corrected_bowling_wrist_speed = [0.0]
    for i in range(1, n_frames):
        prev = get_xy(all_keypoints[i - 1], LEFT_WRIST)
        curr = get_xy(all_keypoints[i], LEFT_WRIST)
        if prev is None or curr is None:
            corrected_bowling_wrist_speed.append(corrected_bowling_wrist_speed[-1])
        else:
            corrected_bowling_wrist_speed.append(np.hypot(curr[0] - prev[0], curr[1] - prev[1]))
    corrected_bowling_wrist_speed = smooth(corrected_bowling_wrist_speed)

    print("\nRunning fault-detection metrics...")
    if view == "side":
        report = fd.build_report(
            all_keypoints, fps, bowling_arm_for_computation, back_foot_frame, front_foot_frame,
            release_frame, left_ankle_vspeed, right_ankle_vspeed,
            corrected_bowling_wrist_speed, corrected_bowling_wrist_speed, front_leg_side,
        )
        categorized = fd.categorize_report(report)
    else:
        report = fdfb.build_front_back_report(all_keypoints, back_foot_frame, release_frame)
        categorized = fdfb.categorize_front_back_report(report)

    print("\n--- DELIVERY REPORT ---")
    for section, items in categorized.items():
        print(f"\n{section.upper()}:")
        for line in items:
            print(f"  - {line}")
    print("-----------------------\n")

    os.makedirs(os.path.join(output_dir, "results"), exist_ok=True)
    csv_path = os.path.join(output_dir, "results", "all_deliveries.csv")
    file_exists = os.path.exists(csv_path)
    row = {
        "video": os.path.basename(video_path),
        "view": view,
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "bowling_arm": bowling_arm,
        **report,
    }
    with open(csv_path, "a", newline="") as f:
        writer_csv = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not file_exists:
            writer_csv.writeheader()
        writer_csv.writerow(row)
    print(f"Appended this delivery's numbers to: {csv_path}")

    video_stem = os.path.splitext(os.path.basename(video_path))[0]
    report_path = os.path.join(output_dir, "results", f"report_{video_stem}_{view}.md")
    with open(report_path, "w") as f:
        f.write(f"# Delivery Report - {os.path.basename(video_path)} ({view} view)\n\n")
        if view == "side":
            f.write(f"Bowling arm: **{bowling_arm}** | Front leg: **{front_leg_side}**\n\n")
        for section, items in categorized.items():
            f.write(f"## {section.replace('_', ' ').title()}\n\n")
            if items:
                for line in items:
                    f.write(f"- {line}\n")
            else:
                f.write("- (nothing detected in this category for this delivery)\n")
            f.write("\n")
    print(f"Saved standalone report: {report_path}")

    # ---- PASS 2: render single labeled output video ----
    print("Pass 2: rendering labeled output video...")
    pass2_start_time = time.monotonic()
    height, width = raw_frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    os.makedirs(os.path.join(output_dir, "videos", "output"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "results"), exist_ok=True)
    output_video_path = os.path.join(output_dir, "videos", "output", f"output_pipeline_{view}.mp4")
    raw_temp_path = output_video_path + ".raw_temp.mp4"
    writer = cv2.VideoWriter(raw_temp_path, fourcc, fps, (width, height))

    skeleton_line_color = su.COLOR_LINE if view == "side" else su.COLOR_LINE_FRONT_BACK
    skeleton_joint_color = su.COLOR_JOINT if view == "side" else su.COLOR_JOINT_FRONT_BACK

    def phase_for_frame(i):
        if back_foot_frame is not None and i < back_foot_frame:
            return "RUN-UP"
        if back_foot_frame is not None and back_foot_frame <= i < (front_foot_frame or i + 1):
            return "DELIVERY STRIDE (back foot down)"
        if front_foot_frame is not None and front_foot_frame <= i < release_frame:
            return "FRONT FOOT DOWN - ARM COMING OVER"
        if i == release_frame:
            return "RELEASE"
        if release_frame is not None and i > release_frame:
            return "FOLLOW-THROUGH"
        return ""

    for i in range(n_frames):
        frame = raw_frames[i].copy()

        kpts = all_keypoints[i]
        if kpts is not None:
            draw_skeleton(frame, kpts, line_color=skeleton_line_color, joint_color=skeleton_joint_color)

        SEAM = (31, 50, 168)
        GOLD = (76, 162, 210)

        su.draw_label(frame, "BOWLER", (20, 35), GOLD, font_scale=0.6)
        label = phase_for_frame(i)
        if label:
            su.draw_label(frame, label, (20, 70), SEAM, font_scale=0.75)

        if i == back_foot_frame:
            su.draw_label(frame, "BACK FOOT CONTACT", (20, 105), GOLD, font_scale=0.6)
        if i == front_foot_frame:
            su.draw_label(frame, "FRONT FOOT CONTACT", (20, 105), GOLD, font_scale=0.6)
        if i == release_frame:
            su.draw_label(frame, "RELEASE", (20, 105), SEAM, font_scale=0.6)

        if view == "side" and front_foot_frame is not None and i >= front_foot_frame and kpts is not None:
            draw_front_leg_brace_guide(frame, kpts, front_leg_side)

        writer.write(frame)

    writer.release()
    pass2_elapsed = time.monotonic() - pass2_start_time
    print(f"Pass 2 (rendering) took {pass2_elapsed:.1f}s")

    transcode_start_time = time.monotonic()
    import subprocess
    import shutil as _shutil
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", raw_temp_path,
                "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                output_video_path,
            ],
            check=True, capture_output=True,
        )
        os.remove(raw_temp_path)
        transcode_elapsed = time.monotonic() - transcode_start_time
        print(f"Transcoded output video to browser-compatible H.264 in {transcode_elapsed:.1f}s: {output_video_path}")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"WARNING: ffmpeg transcode failed ({e}) - falling back to raw "
              f"output, which may not play in a browser. Install ffmpeg on "
              f"this server to fix video playback.")
        _shutil.move(raw_temp_path, output_video_path)
        transcode_elapsed = time.monotonic() - transcode_start_time

    plt.figure(figsize=(12, 6))
    plt.plot(right_wrist_speed, label="Right wrist speed")
    plt.plot(left_wrist_speed, label="Left wrist speed")
    plt.plot(combined_ankle_speed, label="Ankle vertical speed (lower of the two)")
    if back_foot_frame is not None:
        plt.axvline(back_foot_frame, color="cyan", linestyle="--", label="Back foot contact")
    if front_foot_frame is not None:
        plt.axvline(front_foot_frame, color="orange", linestyle="--", label="Front foot contact")
    plt.axvline(release_frame, color="red", linestyle="--", label="Release")
    plt.xlabel("Frame number")
    plt.ylabel("Speed (pixels/frame)")
    plt.title("Joint speed over time, with detected delivery events")
    plt.legend()
    plt.tight_layout()
    phase_graph_path = os.path.join(output_dir, "results", f"phase_graph_{video_stem}_{view}.png")
    plt.savefig(phase_graph_path)
    plt.close()

    total_elapsed = time.monotonic() - pipeline_start_time
    print("\nDone. Everything ran in one command.")
    print(f"TOTAL TIME: {total_elapsed:.1f}s (Pass 1: {pass1_elapsed:.1f}s, Pass 2: {pass2_elapsed:.1f}s, transcode: {transcode_elapsed:.1f}s)")
    print(f"Saved: {output_video_path}")
    print(f"Saved: {phase_graph_path}")
    print(f"Saved: {report_path}")
    print(f"Saved: {csv_path}")

    return {
        "success": True,
        "view": view,
        "bowling_arm": bowling_arm,
        "front_leg_side": front_leg_side if view == "side" else None,
        "output_video_path": output_video_path,
        "phase_graph_path": phase_graph_path,
        "report_path": report_path,
        "report": categorized,
        "raw_metrics": report,
        "back_foot_frame": back_foot_frame,
        "front_foot_frame": front_foot_frame,
        "release_frame": release_frame,
        "fps": fps,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_pipeline.py your_video.mp4 [--view side|front|back] [--id N] [--start SEC] [--end SEC]")
        return

    video_path = sys.argv[1]
    model_name = "yolo11m-pose.pt"
    start_seconds = 0.0
    end_seconds = None
    manual_id = None
    view = "side"

    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--start":
            start_seconds = float(args[i + 1]); i += 2
        elif args[i] == "--end":
            end_seconds = float(args[i + 1]); i += 2
        elif args[i] == "--id":
            manual_id = int(args[i + 1]); i += 2
        elif args[i] == "--view":
            view = args[i + 1].lower(); i += 2
        else:
            model_name = args[i]; i += 1

    analyze_video(video_path, view=view, start_seconds=start_seconds, end_seconds=end_seconds,
                  manual_id=manual_id, model_name=model_name, output_dir=".")


if __name__ == "__main__":
    main()