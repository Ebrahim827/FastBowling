"""
Database setup. Uses an environment variable so you can point this at
either a local SQLite file (zero setup, great for development) or a
real hosted database like Aiven's managed PostgreSQL (what you want
once real users are on this app) - same code either way, just a
different connection string.

HOW TO USE AIVEN (or any hosted Postgres):
1. In your Aiven console, create a PostgreSQL service (or use an
   existing one).
2. Copy its "Service URI" / connection string - Aiven shows this
   directly in the service overview page. It looks like:
       postgres://avnadmin:PASSWORD@your-service-name.aivencloud.com:PORT/defaultdb?sslmode=require
3. Set it as an environment variable before starting the backend:
       export DATABASE_URL="postgres://avnadmin:...your full string..."
   (On Windows PowerShell: $env:DATABASE_URL = "postgres://...")
4. Start the backend as normal (uvicorn main:app ...) - it will now
   read/write to Aiven instead of the local SQLite file. Tables are
   created automatically on first run, same as with SQLite.

If DATABASE_URL isn't set at all, this falls back to a local SQLite
file (bowling_app.db) so local development still works with zero setup.
"""

import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Float
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import datetime

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./bowling_app.db")

# SQLAlchemy expects "postgresql://" - Aiven (and some other providers)
# give you a URI starting with "postgres://" instead. This handles
# both without you needing to edit the string yourself.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user")  # "user" or "coach"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    deliveries = relationship("Delivery", back_populates="owner")


class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    original_filename = Column(String)
    view = Column(String)  # "side", "front", "back"
    status = Column(String, default="processing")  # "processing", "done", "failed"
    error_message = Column(Text, nullable=True)

    output_video_path = Column(String, nullable=True)
    report_path = Column(String, nullable=True)
    phase_graph_path = Column(String, nullable=True)

    bowling_arm = Column(String, nullable=True)
    front_leg_side = Column(String, nullable=True)

    # A few headline numbers pulled out as real columns, so the coach
    # dashboard can sort/filter without parsing JSON every time.
    front_knee_angle_release_deg = Column(Float, nullable=True)
    trunk_bend_angle_release_deg = Column(Float, nullable=True)
    peak_wrist_speed_px_per_frame = Column(Float, nullable=True)

    report_json = Column(Text, nullable=True)      # full categorized report, as JSON text
    raw_metrics_json = Column(Text, nullable=True)  # full raw numbers dict, as JSON text

    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="deliveries")


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
