# Bowling Analysis Web App

Full-stack app: upload a bowling delivery video (side, front, or back
view), get back a skeleton-tracked video and a biomechanics report.
Coach accounts can see every player's uploads.

## Structure

```
backend/     FastAPI + SQLite - auth, database, video analysis pipeline
frontend/    React + Tailwind - login/signup, upload UI, results, coach dashboard
```

## Running it locally

### 1. Backend

```
cd backend
pip install -r requirements.txt
cd app
uvicorn main:app --reload --port 8000
```

First run will download the pose-detection model (~6MB) automatically.
The API is now at http://localhost:8000 - interactive docs (useful for
testing without the frontend) are at http://localhost:8000/docs

By default (no setup needed) this uses a local SQLite file
(`backend/app/bowling_app.db`) - great for testing on your own machine.

**To use a real hosted database (e.g. Aiven) instead:**
1. Copy `backend/app/.env.example` to `backend/app/.env`
2. Paste your Aiven Postgres service's connection string into
   `DATABASE_URL` in that file (found in your Aiven console, on the
   service's overview page - "Service URI")
3. Set `BOWLING_APP_SECRET_KEY` to a random value (the file explains
   how to generate one)
4. Restart the backend - it now reads/writes to Aiven instead of the
   local file. Tables get created automatically on first run, same as
   with SQLite - nothing else to set up on Aiven's side beyond having
   the service running.

Note: **this only covers the database** (user accounts, delivery
records, report numbers). Uploaded video files and skeleton output
videos still get saved to `backend/uploads/` on whatever machine runs
the backend - Aiven doesn't provide file/video storage. That's fine
for a single server, but if you outgrow that, look at S3-compatible
object storage (AWS S3, Cloudflare R2, DigitalOcean Spaces) - ask if
you want that built in later.

### 2. Frontend

In a second terminal:

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 - the dev server automatically forwards API
calls to the backend on port 8000 (see `vite.config.js`).

## First-time use

1. Go to http://localhost:5173/signup
2. Create a **Coach** account for yourself (there's a toggle on the
   signup form) - this is the account that can see everyone's data.
3. Create a second account as a **Player** to test the normal flow
   (or just use your coach account for both - a coach account can
   also upload and analyze its own deliveries).
4. From the home page, pick a view (side/front/back) and upload a
   short video of a bowling delivery.
5. You'll land on the results page, which shows a spinner while
   analysis runs in the background, then automatically updates once
   it's done.

## Important things to know before showing this to real users

- **Coach signup is currently open to anyone** - the signup form lets
  you pick "Coach" freely. Before real players use this, remove that
  option from the signup form/API and instead promote specific
  accounts to coach manually (see the comment in `backend/app/main.py`
  above the `/signup` endpoint).
- **JWT secret key**: `backend/app/auth.py` uses a placeholder secret
  key by default. Set a real one via the `BOWLING_APP_SECRET_KEY`
  environment variable before deploying anywhere public.
- **CORS is wide open** (`allow_origins=["*"]`) for local development
  convenience - tighten this to your actual frontend's domain before
  deploying.
- **Speeds are relative, not real km/h.** Every number that looks like
  a "speed" (peak wrist speed, run-up speed) is in pixels/frame, not
  real-world units - there's no camera calibration yet. Only meaningful
  for comparing deliveries from the same camera position. See
  `backend/app/fault_detection.py`'s module docstring.
- **Video processing runs on CPU** by default and isn't instant - a
  several-second clip takes a similar number of seconds to process.
  It runs in the background so the upload itself returns immediately,
  but don't expect real-time results on a laptop without a GPU.
- **SQLite is fine for development/small use**, but for many
  concurrent users, switch `DATABASE_URL` in `backend/app/database.py`
  to Postgres (one line change - everything else stays the same).

## What's NOT built yet (roadmap)

- Real-world speed calibration (pixels -> km/h) - needs a known
  reference distance in frame, or a fixed camera setup.
- A custom-trained pose model (currently uses generic pretrained
  YOLOv8-Pose, which has tested well but a bowling-specific model
  would be more robust, especially for front-foot alignment, which
  isn't measurable with the current model at all - see
  `fault_detection_front_back.py`).
- Multi-delivery batch upload / spell-level analytics.
