"""
FASTAPI BACKEND for the bowling analysis app.

Endpoints:
    POST /signup                    - create an account
    POST /login                     - get a JWT token
    POST /analyze                   - upload a video, kicks off analysis in the background
    GET  /deliveries                - your own past deliveries
    GET  /deliveries/{id}           - one delivery's full report (yours, or any if you're a coach)
    GET  /coach/deliveries          - EVERY user's deliveries (coach only)
    GET  /coach/users               - list of all users (coach only)
    GET  /files/{path}              - serves the actual video/report files

HOW TO RUN:
    pip install -r requirements.txt
    Also requires ffmpeg installed on the system (NOT a pip package -
    used to convert the analysis video to a browser-playable format).
    Check with: ffmpeg -version
    If missing: Windows - download from ffmpeg.org and add to PATH;
    Mac - brew install ffmpeg; Linux - apt install ffmpeg
    uvicorn main:app --reload --port 8000

    Then the API is at http://localhost:8000 and interactive docs
    (auto-generated, very useful for testing without the frontend yet)
    are at http://localhost:8000/docs
"""

import os
import json
import shutil
import datetime
from dotenv import load_dotenv
load_dotenv()  # reads a .env file in the app/ folder if one exists, so
                # DATABASE_URL and BOWLING_APP_SECRET_KEY don't need to
                # be retyped into the terminal every time

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .database import init_db, get_db, User, Delivery, SessionLocal
from .auth import hash_password, verify_password, create_access_token, get_current_user, require_coach
from .schemas import SignupRequest, TokenResponse, DeliverySummary, DeliveryDetail
from .run_pipeline import analyze_video

UPLOAD_ROOT = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_ROOT, exist_ok=True)

app = FastAPI(title="Bowling Analysis API")

# CORS: wide open for local development. TIGHTEN THIS before deploying
# publicly - restrict allow_origins to your actual frontend's domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

# Serves uploaded videos, skeleton output videos, and reports directly
# by path, e.g. GET /files/videos/user_3/delivery_12/output_pipeline_side.mp4
app.mount("/files", StaticFiles(directory=UPLOAD_ROOT), name="files")


@app.delete("/deliveries/{delivery_id}")
def delete_delivery(delivery_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    d = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if d is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if d.owner_id != current_user.id and current_user.role != "coach":
        raise HTTPException(status_code=403, detail="Not your delivery")

    folder = os.path.join(UPLOAD_ROOT, f"user_{d.owner_id}", f"delivery_{d.id}")
    if os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)

    db.delete(d)
    db.commit()
    return {"deleted": True}

@app.patch("/deliveries/{delivery_id}/rename")
def rename_delivery(
    delivery_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = db.query(Delivery).filter(Delivery.id == delivery_id).first()

    if d is None:
        raise HTTPException(status_code=404, detail="Delivery not found")

    if d.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your delivery")

    new_name = str(payload.get("name", "")).strip()

    if not new_name:
        raise HTTPException(status_code=400, detail="Name cannot be empty")

    if len(new_name) > 255:
        raise HTTPException(status_code=400, detail="Name is too long")

    d.original_filename = new_name
    db.commit()
    db.refresh(d)

    return {
        "id": d.id,
        "original_filename": d.original_filename,
    }    


@app.post("/signup", response_model=TokenResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")

    # NOTE: this MVP lets anyone sign up as "coach" by just passing
    # role="coach" in the signup request. Fine while it's just you
    # testing, but before real users touch this: remove the role field
    # from signup entirely, default everyone to "user", and promote
    # specific accounts to "coach" manually (e.g. directly in the
    # database, or a separate admin-only endpoint you protect yourself).
    role = payload.role if payload.role in ("user", "coach") else "user"

    user = User(username=payload.username, hashed_password=hash_password(payload.password), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.username})
    return TokenResponse(access_token=token, role=user.role, username=user.username)


@app.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = create_access_token({"sub": user.username})
    return TokenResponse(access_token=token, role=user.role, username=user.username)


def _run_analysis_job(delivery_id: int, video_path: str, view: str, output_dir: str):
    """Runs in the background after /analyze returns - this is what
    actually calls the (potentially slow, CPU-bound) pose-detection
    pipeline, so the upload request itself returns immediately instead
    of the user's browser hanging for however long processing takes."""
    db = SessionLocal()
    try:
        result = analyze_video(video_path, view=view, output_dir=output_dir)
        delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
        if delivery is None:
            return

        if not result.get("success"):
            delivery.status = "failed"
            delivery.error_message = result.get("error", "Unknown error during analysis")
            db.commit()
            return

        def rel(p):
            # Store paths relative to UPLOAD_ROOT so /files/... URLs
            # can be built consistently regardless of absolute paths.
            return os.path.relpath(p, UPLOAD_ROOT) if p else None

        delivery.status = "done"
        delivery.output_video_path = rel(result["output_video_path"])
        delivery.report_path = rel(result["report_path"])
        delivery.phase_graph_path = rel(result["phase_graph_path"])
        delivery.bowling_arm = result.get("bowling_arm")
        delivery.front_leg_side = result.get("front_leg_side")

        raw = result.get("raw_metrics", {}) or {}
        delivery.front_knee_angle_release_deg = raw.get("front_knee_angle_release_deg")
        delivery.trunk_bend_angle_release_deg = raw.get("trunk_bend_angle_release_deg")
        delivery.peak_wrist_speed_px_per_frame = raw.get("peak_wrist_speed_px_per_frame")

        delivery.report_json = json.dumps(result.get("report", {}))
        delivery.raw_metrics_json = json.dumps(raw, default=str)

        db.commit()
    except Exception as e:
        delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
        if delivery is not None:
            delivery.status = "failed"
            delivery.error_message = str(e)
            db.commit()
    finally:
        db.close()


@app.post("/analyze", response_model=DeliverySummary)
def analyze(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    view: str = Form("side"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if view not in ("side", "front", "back"):
        raise HTTPException(status_code=400, detail="view must be 'side', 'front', or 'back'")

    # Create the DB record first (status=processing) so we have an id
    # to build a per-delivery output folder from, and so the frontend
    # can immediately start polling for status.
    delivery = Delivery(owner_id=current_user.id, original_filename=file.filename, view=view, status="processing")
    db.add(delivery)
    db.commit()
    db.refresh(delivery)

    user_dir = os.path.join(UPLOAD_ROOT, f"user_{current_user.id}", f"delivery_{delivery.id}")
    os.makedirs(user_dir, exist_ok=True)
    video_path = os.path.join(user_dir, file.filename)
    with open(video_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    background_tasks.add_task(_run_analysis_job, delivery.id, video_path, view, user_dir)

    return delivery


def _delivery_to_summary(d: Delivery, owner_username: str = None) -> DeliverySummary:
    return DeliverySummary(
        id=d.id, original_filename=d.original_filename, view=d.view, status=d.status,
        bowling_arm=d.bowling_arm, front_knee_angle_release_deg=d.front_knee_angle_release_deg,
        trunk_bend_angle_release_deg=d.trunk_bend_angle_release_deg,
        peak_wrist_speed_px_per_frame=d.peak_wrist_speed_px_per_frame,
        created_at=d.created_at, owner_username=owner_username,
    )


@app.get("/deliveries", response_model=list[DeliverySummary])
def my_deliveries(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    deliveries = db.query(Delivery).filter(Delivery.owner_id == current_user.id).order_by(Delivery.created_at.desc()).all()
    return [_delivery_to_summary(d) for d in deliveries]


@app.get("/deliveries/{delivery_id}", response_model=DeliveryDetail)
def get_delivery(delivery_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    d = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if d is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if d.owner_id != current_user.id and current_user.role != "coach":
        raise HTTPException(status_code=403, detail="Not your delivery")

    return DeliveryDetail(
        **_delivery_to_summary(d, owner_username=d.owner.username).dict(),
        output_video_path=d.output_video_path,
        error_message=d.error_message,
        report=json.loads(d.report_json) if d.report_json else None,
        raw_metrics=json.loads(d.raw_metrics_json) if d.raw_metrics_json else None,
    )


@app.get("/coach/deliveries", response_model=list[DeliverySummary])
def all_deliveries(db: Session = Depends(get_db), coach: User = Depends(require_coach)):
    deliveries = db.query(Delivery).order_by(Delivery.created_at.desc()).all()
    return [_delivery_to_summary(d, owner_username=d.owner.username) for d in deliveries]


@app.get("/coach/users")
def all_users(db: Session = Depends(get_db), coach: User = Depends(require_coach)):
    users = db.query(User).all()
    return [{"id": u.id, "username": u.username, "role": u.role, "created_at": u.created_at,
             "delivery_count": len(u.deliveries)} for u in users]


@app.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "role": current_user.role}
