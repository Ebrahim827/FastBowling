import { useEffect, useState, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import { api, fileUrl } from "../api";
import SeamDivider from "../components/SeamDivider";

function ReportSection({ title, items, tone }) {
  if (!items || items.length === 0) return null;
  const toneClasses = {
    good: "border-bail/40 bg-bail/5",
    warn: "border-seam/40 bg-seam/5",
    neutral: "border-pitch-600 bg-pitch-800",
  }[tone];
  return (
    <div className="mb-6">
      <h3 className="font-display text-lg text-cream tracking-wide mb-3">{title}</h3>
      <div className="space-y-2">
        {items.map((line, i) => (
          <div key={i} className={`px-4 py-3 rounded border ${toneClasses} text-sm text-cream/90 font-mono`}>
            {line}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Results() {
  const { id } = useParams();
  const [delivery, setDelivery] = useState(null);
  const [error, setError] = useState("");
  const pollRef = useRef(null);

  useEffect(() => {
    async function poll() {
      try {
        const data = await api.deliveryDetail(id);
        setDelivery(data);
        if (data.status === "processing") {
          pollRef.current = setTimeout(poll, 2000);
        }
      } catch (err) {
        setError(err.message || "Could not load this delivery");
      }
    }
    poll();
    return () => clearTimeout(pollRef.current);
  }, [id]);

  if (error) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-16 text-center">
        <p className="text-seam-light">{error}</p>
        <Link to="/" className="text-bail hover:text-bail-light text-sm">Back to analyse</Link>
      </div>
    );
  }

  if (!delivery) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-16 text-center">
        <div className="inline-block w-8 h-8 border-2 border-bail border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (delivery.status === "processing") {
    return (
      <div className="max-w-3xl mx-auto px-6 py-24 text-center">
        <div className="inline-block w-8 h-8 border-2 border-bail border-t-transparent rounded-full animate-spin mb-5" />
        <p className="font-display text-2xl text-cream tracking-wide">Analysing your delivery...</p>
        <p className="text-sage text-sm mt-2 font-mono">
          Tracking the bowler, finding release, running biomechanics — this page updates automatically.
        </p>
      </div>
    );
  }

  if (delivery.status === "failed") {
    return (
      <div className="max-w-3xl mx-auto px-6 py-24 text-center">
        <p className="font-display text-2xl text-seam-light">Analysis failed</p>
        <p className="text-sage text-sm mt-3 font-mono">{delivery.error_message}</p>
        <Link to="/" className="inline-block mt-6 text-bail hover:text-bail-light text-sm">Try another video</Link>
      </div>
    );
  }

  const report = delivery.report || {};

  return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      <p className="font-mono text-xs tracking-[0.3em] text-bail uppercase mb-2">
        {delivery.view} view · {delivery.bowling_arm ? `${delivery.bowling_arm}-arm bowler` : ""}
      </p>
      <h1 className="font-display text-3xl text-cream tracking-wide mb-4">
        {delivery.original_filename}
      </h1>
      <SeamDivider className="max-w-xs mb-8" />

      <div className="rounded-lg overflow-hidden border border-pitch-600 mb-10 bg-black">
        <video
          src={fileUrl(delivery.output_video_path)}
          controls
          className="w-full max-h-[560px]"
        />
      </div>

      <ReportSection title="Improvements" items={report.improvements} tone="warn" />
      <ReportSection title="Plus Points" items={report.plus_points} tone="good" />
      <ReportSection title="Stats" items={report.stats} tone="neutral" />

      <div className="mt-10">
        <Link to="/" className="text-bail hover:text-bail-light text-sm font-mono">
          &larr; Analyse another delivery
        </Link>
      </div>
    </div>
  );
}
