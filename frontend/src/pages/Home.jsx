import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import SeamDivider from "../components/SeamDivider";
import CricketStumpsBg from "../components/CricketStumpsBg";


const VIEWS = [
  { id: "side", label: "Side View", desc: "Best for front-leg brace, arm swing, and release mechanics.", example: "/assets/side.png" },
  { id: "front", label: "Front View", desc: "Checks shoulder alignment and head stability facing the camera.", example: "assets/front.png" },
  { id: "back", label: "Back View", desc: "Checks shoulder alignment and head stability from behind.", example: "/assets/back.png" },
];

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" className="w-7 h-7" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 16V4M12 4l-4 4M12 4l4 4" />
      <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
    </svg>
  );
}

export default function Home() {
  const [selectedView, setSelectedView] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);
  const navigate = useNavigate();

  function triggerUpload(viewId) {
    setSelectedView(viewId);
    fileInputRef.current?.click();
  }

  async function handleFileChange(e) {
    const file = e.target.files?.[0];
    if (!file || !selectedView) return;
    setError("");
    setUploading(true);
    try {
      const delivery = await api.analyze(file, selectedView);
      navigate(`/results/${delivery.id}`);
    } catch (err) {
      setError(err.message || "Upload failed");
      setUploading(false);
    }
  }

  return (
    <div className="relative min-h-[calc(100vh-73px)] overflow-hidden">
      <input ref={fileInputRef} type="file" accept="video/*" onChange={handleFileChange} className="hidden" />

      {/* Background video - loops muted, dimmed so text stays readable.
          Drop your own clip at frontend/public/assets/hero-bg.mp4
          (e.g. a short muted loop of a bowling action - your Archer
          clip trimmed to a few seconds works well). If the file is
          missing, this just shows the plain dark background - nothing
          breaks. */}
     <CricketStumpsBg className="absolute inset-0 w-full h-full opacity-70" />
      <div className="absolute inset-0 bg-gradient-to-b from-pitch-950/40 via-pitch-950/60 to-pitch-950" />

      <div className="relative max-w-5xl mx-auto px-6 py-16">
        <div className="text-center mb-14">
          <p className="font-mono text-xs tracking-[0.3em] text-bail uppercase mb-3">Delivery Analysis</p>
          <h1 className="font-display text-5xl md:text-6xl text-cream tracking-wide">
            Analyse Your Bowling
          </h1>
          <SeamDivider className="max-w-xs mx-auto my-6" />
          <p className="text-sage max-w-lg mx-auto">
            Upload a delivery and get a skeleton-tracked breakdown of your action,
            grounded in real biomechanics research.
          </p>
        </div>

        {error && (
          <div className="max-w-lg mx-auto mb-8 px-4 py-3 rounded-xl border border-seam/40 bg-seam/10 backdrop-blur text-seam-light text-sm text-center">
            {error}
          </div>
        )}

        {uploading ? (
          <div className="text-center py-20">
            <div className="inline-block w-8 h-8 border-2 border-bail border-t-transparent rounded-full animate-spin mb-4" />
            <p className="text-sage font-mono text-sm">Uploading and starting analysis...</p>
          </div>
        ) : (
          <div className="grid md:grid-cols-3 gap-6">
            {VIEWS.map((v) => (
              <div
                key={v.id}
                className="rounded-2xl overflow-hidden bg-white/[0.04] backdrop-blur-xl border border-white/10 shadow-[0_8px_30px_rgba(0,0,0,0.3)] flex flex-col items-center text-center"
              >
                {/* Example reference photo - drop your own images at
                    frontend/public/assets/example-side.jpg (and -front, -back).
                    Falls back to a plain gradient block if missing. */}
                <div className="w-full h-60 bg-gradient-to-br from-pitch-700 to-pitch-800">
                  <img
                    src={v.example}
                    alt={`Example ${v.label.toLowerCase()} camera angle`}
                    className="w-full h-60 object-cover object-top"
                    onError={(e) => { e.target.style.display = "none"; }}
                  />
                </div>

                <div className="p-7 flex flex-col items-center">
                  <h3 className="font-display text-xl text-cream tracking-wide mb-2">{v.label}</h3>
                  <p className="text-sage text-sm mb-6 min-h-[40px]">{v.desc}</p>

                  <button
                    onClick={() => triggerUpload(v.id)}
                    aria-label={`Upload video for ${v.label}`}
                    className="w-16 h-16 rounded-full flex items-center justify-center
                               bg-white/5 border border-white/15 text-bail
                               hover:bg-seam/20 hover:border-seam/50 hover:text-seam-light
                               hover:scale-105 active:scale-95
                               transition-all duration-200 cursor-pointer"
                  >
                    <UploadIcon />
                  </button>
                  <p className="text-sage/60 text-xs font-mono mt-4 tracking-wide">UPLOAD VIDEO</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}