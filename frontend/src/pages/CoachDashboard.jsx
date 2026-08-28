import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import SeamDivider from "../components/SeamDivider";

const STATUS_STYLE = {
  done: "text-bail",
  processing: "text-sage",
  failed: "text-seam-light",
};

export default function CoachDashboard() {
  const [deliveries, setDeliveries] = useState(null);
  const [users, setUsers] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.coachDeliveries(), api.coachUsers()])
      .then(([d, u]) => { setDeliveries(d); setUsers(u); })
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div className="max-w-5xl mx-auto px-6 py-12">
      <p className="font-mono text-xs tracking-[0.3em] text-bail uppercase mb-2">Coach Access</p>
      <h1 className="font-display text-3xl text-cream tracking-wide">All Players</h1>
      <SeamDivider className="max-w-xs my-4" />

      {error && <p className="text-seam-light text-sm">{error}</p>}

      <div className="grid sm:grid-cols-3 gap-4 mb-12">
        {users?.map((u) => (
          <div key={u.id} className="px-5 py-4 rounded-lg bg-pitch-800 border border-pitch-600">
            <p className="text-cream font-medium">{u.username}</p>
            <p className="text-sage text-xs font-mono mt-1 uppercase tracking-wide">{u.role}</p>
            <p className="text-sage text-xs font-mono mt-2">{u.delivery_count} deliveries</p>
          </div>
        ))}
      </div>

      <h2 className="font-display text-2xl text-cream tracking-wide mb-4">All Deliveries</h2>
      <div className="space-y-3">
        {deliveries?.map((d) => (
          <Link
            key={d.id}
            to={`/results/${d.id}`}
            className="block px-5 py-4 rounded-lg bg-pitch-800 border border-pitch-600 hover:border-bail transition-colors"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-cream font-medium">
                  {d.owner_username} <span className="text-sage font-normal">— {d.original_filename}</span>
                </p>
                <p className="text-sage text-xs font-mono mt-1">
                  {d.view} view · {new Date(d.created_at).toLocaleString()}
                </p>
              </div>
              <span className={`font-mono text-xs uppercase tracking-wide ${STATUS_STYLE[d.status]}`}>
                {d.status}
              </span>
            </div>
            {d.status === "done" && (
              <div className="flex gap-4 mt-3 font-mono text-xs text-sage">
                {d.front_knee_angle_release_deg != null && (
                  <span>Knee @ release: {d.front_knee_angle_release_deg.toFixed(0)}°</span>
                )}
                {d.trunk_bend_angle_release_deg != null && (
                  <span>Trunk bend: {d.trunk_bend_angle_release_deg.toFixed(0)}°</span>
                )}
              </div>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
