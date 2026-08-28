import { useState, useRef } from "react";
import SeamDivider from "../components/SeamDivider";

function speedZoneColor(kmh) {
  if (kmh < 100) return "bg-green-950 border-green-500";
  if (kmh < 125) return "bg-blue-950 border-blue-500";
  return "bg-red-950 border-red-500 shadow-[0_0_30px_rgba(239,68,68,0.35)]";
}

export default function SpeedCheck() {
  const [videoUrl, setVideoUrl] = useState(null);
  const [distance, setDistance] = useState(20.12);
  const [fps, setFps] = useState(30);
  const [releaseT, setReleaseT] = useState(null);
  const [reachT, setReachT] = useState(null);
  const [unit, setUnit] = useState("kmh");
  const videoRef = useRef(null);

  function handleFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setVideoUrl(URL.createObjectURL(file));
    setReleaseT(null);
    setReachT(null);
  }

  function nudge(deltaSeconds) {
    const v = videoRef.current;
    if (!v) return;
    v.pause();
    v.currentTime = Math.max(0, v.currentTime + deltaSeconds);
  }

  // Forward frame-stepping: uses the browser's actual decoded-frame
  // callback (when available) instead of guessing off an assumed FPS -
  // this is the real fix for imprecise marking, since a manual
  // "currentTime += 1/fps" nudge can land mid-frame or drift if the
  // FPS you typed doesn't exactly match the video's real FPS.
  // Backward stepping has no browser equivalent (no native "previous
  // frame" API), so it still uses the FPS-based estimate.
  function stepForwardFrame() {
    const v = videoRef.current;
    if (!v) return;
    v.pause();
    if ("requestVideoFrameCallback" in v) {
      v.requestVideoFrameCallback(() => v.pause());
      v.play();
    } else {
      v.currentTime = Math.min(v.duration || Infinity, v.currentTime + 1 / fps);
    }
  }

  const deltaSeconds = releaseT != null && reachT != null ? reachT - releaseT : null;
  const valid = deltaSeconds != null && deltaSeconds > 0;
  const speedKmh = valid ? (distance / deltaSeconds) * 3.6 : null;
  const speedMph = speedKmh != null ? speedKmh * 0.621371 : null;

  const nudgeBtn = "px-3 py-1.5 rounded-md bg-pitch-700 text-cream font-mono text-[11px] shadow-sm active:translate-y-0.5 active:shadow-none transition-all";

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
      <h1 className="font-display text-2xl sm:text-3xl text-cream tracking-wide">Speed Check</h1>
      <p className="text-sage text-sm mt-1">Mark release and reach points, get speed instantly.</p>
      <SeamDivider className="max-w-xs my-4" />

      {!videoUrl && (
        <label className="btn-3d btn-3d-upload block cursor-pointer rounded-2xl py-14 text-center text-white font-bold text-lg tracking-wide">
  <input type="file" accept="video/*" className="hidden" onChange={handleFile} />
  ⬆ Upload Delivery Video
</label>
      )}

      {videoUrl && (
        <>
          <video
            ref={videoRef}
            src={videoUrl}
            controls
            className="w-full max-h-[50vh] sm:max-h-[60vh] object-contain rounded-xl bg-black mx-auto"
          />

          <div className="flex items-center justify-center gap-48 mt-3">
            <div className="flex gap-1.5">
              <button onClick={() => nudge(-1 / fps)} className={nudgeBtn}>&laquo; frame</button>
              <button onClick={() => nudge(-0.05)} className={nudgeBtn}>-50ms</button>
            </div>
            <div className="flex gap-1.5">
              <button onClick={() => nudge(0.05)} className={nudgeBtn}>+50ms</button>
              <button onClick={stepForwardFrame} className={nudgeBtn}>frame &raquo;</button>
            </div>
          </div>

          <div className="flex items-center gap-2 mt-3">
            <label className="text-sage text-xs font-mono">Source FPS</label>
            <input
              type="number" value={fps} onChange={(e) => setFps(Number(e.target.value) || 30)}
              className="w-14 bg-pitch-800 rounded px-2 py-1 text-cream text-xs"
            />
            <span className="text-sage/50 text-[11px]">used for backward stepping only - forward uses exact decoded frames</span>
          </div>

          <div className="grid grid-cols-2 gap-3 mt-5">
            <button onClick={() => setReleaseT(videoRef.current?.currentTime)} className="btn-3d btn-3d-blue py-2.5 rounded-lg text-cream font-semibold text-sm">
              Mark Release
              {releaseT != null && <div className="font-mono text-[10px] mt-0.5 opacity-90">{releaseT.toFixed(3)}s</div>}
            </button>
            <button onClick={() => setReachT(videoRef.current?.currentTime)} className="btn-3d btn-3d-yellow py-2.5 rounded-lg text-pitch-950 font-semibold text-sm">
              Mark Reach
              {reachT != null && <div className="font-mono text-[10px] mt-0.5 opacity-90">{reachT.toFixed(3)}s</div>}
            </button>
          </div>

          <div className="flex items-center gap-2 mt-5">
            <label className="text-sage text-sm">Distance (m)</label>
            <input
              type="number" step="0.01" value={distance}
              onChange={(e) => setDistance(Number(e.target.value) || 0)}
              className="w-24 bg-pitch-800 rounded px-2 py-1.5 text-cream"
            />
          </div>

          {releaseT != null && reachT != null && (
            <div className={`mt-6 p-6 rounded-xl border-2 text-center transition-all ${valid ? speedZoneColor(speedKmh) : "bg-pitch-800 border-pitch-600"}`}>
              {!valid ? (
                <p className="text-sage">Reach point must be after the release point.</p>
              ) : (
                <>
                  <p className="font-display text-5xl text-cream">
                    {unit === "kmh" ? speedKmh.toFixed(1) : speedMph.toFixed(1)}
                    <span className="text-lg text-sage ml-2">{unit === "kmh" ? "km/h" : "mph"}</span>
                  </p>
                  <p className="text-sage text-xs font-mono mt-2">{distance}m / {deltaSeconds.toFixed(3)}s</p>
                  <button onClick={() => setUnit(unit === "kmh" ? "mph" : "kmh")} className="mt-3 text-xs text-sage hover:text-cream underline">
                    switch to {unit === "kmh" ? "mph" : "km/h"}
                  </button>
                </>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}