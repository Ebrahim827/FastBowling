from pydantic import BaseModel
from typing import Optional, List
import datetime


class SignupRequest(BaseModel):
    username: str
    password: str
    # Anyone can technically request the coach role at signup for this
    # MVP - see note in main.py's /signup endpoint about locking this
    # down before real users are on the app.
    role: str = "user"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class DeliverySummary(BaseModel):
    id: int
    original_filename: Optional[str]
    view: Optional[str]
    status: str
    bowling_arm: Optional[str]
    front_knee_angle_release_deg: Optional[float]
    trunk_bend_angle_release_deg: Optional[float]
    peak_wrist_speed_px_per_frame: Optional[float]
    created_at: datetime.datetime
    owner_username: Optional[str] = None  # filled in for coach view only

    class Config:
        from_attributes = True


class DeliveryDetail(DeliverySummary):
    output_video_path: Optional[str] = None
    error_message: Optional[str]
    report: Optional[dict]
    raw_metrics: Optional[dict]
