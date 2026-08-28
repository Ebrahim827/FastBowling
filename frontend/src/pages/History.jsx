import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import SeamDivider from "../components/SeamDivider";

const STATUS_STYLE = {
  done: "text-bail",
  processing: "text-sage",
  failed: "text-seam-light",
};

function DeliveryCard({ d, onDeleted, onRenamed }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false);
  const [newName, setNewName] = useState(d.original_filename || "");
  const [renaming, setRenaming] = useState(false);
  const [actionError, setActionError] = useState("");
  const menuRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  async function handleDelete() {
    try {
      await api.deleteDelivery(d.id);
      onDeleted(d.id);
    } catch (err) {
      setActionError(err.message || "Could not delete this delivery");
      setConfirmOpen(false);
    }
  }

  function openRename() {
    setMenuOpen(false);
    setActionError("");
    setNewName(d.original_filename || "");
    setRenameOpen(true);
  }

  async function handleRename() {
    const trimmedName = newName.trim();

    if (!trimmedName) {
      setActionError("Please enter a name.");
      return;
    }

    if (trimmedName === d.original_filename) {
      setRenameOpen(false);
      return;
    }

    try {
      setRenaming(true);
      setActionError("");

      const updated = await api.renameDelivery(d.id, trimmedName);

      onRenamed(d.id, updated.original_filename);
      setRenameOpen(false);
    } catch (err) {
      setActionError(err.message || "Could not rename this delivery");
    } finally {
      setRenaming(false);
    }
  }

  return (
    <div className="relative block px-5 py-4 rounded-lg bg-pitch-800 border border-pitch-600 hover:border-bail transition-colors">

      {/* 3-dot menu */}
      <div ref={menuRef}>
        <button
          onClick={(e) => {
            e.preventDefault();
            setMenuOpen((v) => !v);
          }}
          className="absolute top-3 right-3 w-8 h-8 flex items-center justify-center rounded hover:bg-pitch-700 text-sage hover:text-cream"
          aria-label="Options"
        >
          ⋮
        </button>

        {menuOpen && (
          <div className="absolute top-11 right-3 bg-pitch-900 border border-pitch-600 rounded shadow-lg z-10 w-40">

            {/* Rename */}
            <button
              onClick={openRename}
              className="w-full text-left px-4 py-2.5 text-sm text-cream hover:bg-pitch-800 rounded flex items-center gap-2"
            >
              ✏️ Rename
            </button>

            {/* Delete */}
            <button
              onClick={() => {
                setMenuOpen(false);
                setConfirmOpen(true);
              }}
              className="w-full text-left px-4 py-2.5 text-sm text-seam-light hover:bg-pitch-800 rounded flex items-center gap-2"
            >
              🗑️ Delete
            </button>

          </div>
        )}
      </div>

      {/* Rename dialog */}
      {renameOpen && (
        <div className="absolute inset-0 bg-pitch-950/95 rounded-lg flex flex-col items-center justify-center gap-3 z-20 px-5">

          <p className="text-cream text-sm font-medium">
            Rename this analysis
          </p>

          <input
            autoFocus
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleRename();
              if (e.key === "Escape") setRenameOpen(false);
            }}
            className="w-full px-3 py-2 rounded bg-pitch-800 border border-pitch-600 text-cream text-sm outline-none focus:border-bail"
            placeholder="Enter a new name"
          />

          {actionError && (
            <p className="text-seam-light text-xs">
              {actionError}
            </p>
          )}

          <div className="flex gap-3">
            <button
              onClick={handleRename}
              disabled={renaming}
              className="px-4 py-1.5 rounded bg-bail hover:bg-bail-light text-pitch-950 text-sm disabled:opacity-50"
            >
              {renaming ? "Saving..." : "Save"}
            </button>

            <button
              onClick={() => setRenameOpen(false)}
              disabled={renaming}
              className="px-4 py-1.5 rounded border border-pitch-600 text-sage hover:text-cream text-sm"
            >
              Cancel
            </button>
          </div>

        </div>
      )}

      {/* Delete confirmation */}
      {confirmOpen && (
        <div className="absolute inset-0 bg-pitch-950/95 rounded-lg flex flex-col items-center justify-center gap-3 z-20 px-4 text-center">

          <p className="text-cream text-sm">
            Delete this analysis? This can't be undone.
          </p>

          {actionError && (
            <p className="text-seam-light text-xs">
              {actionError}
            </p>
          )}

          <div className="flex gap-3">
            <button
              onClick={handleDelete}
              className="px-4 py-1.5 rounded bg-seam hover:bg-seam-light text-cream text-sm"
            >
              Yes, delete
            </button>

            <button
              onClick={() => setConfirmOpen(false)}
              className="px-4 py-1.5 rounded border border-pitch-600 text-sage hover:text-cream text-sm"
            >
              Cancel
            </button>
          </div>

        </div>
      )}

      {/* Delivery */}
      <Link to={`/results/${d.id}`} className="block pr-8">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-cream font-medium">
              {d.original_filename}
            </p>

            <p className="text-sage text-xs font-mono mt-1">
              {d.view} view · {new Date(d.created_at).toLocaleString()}
            </p>
          </div>

          <span
            className={`font-mono text-xs uppercase tracking-wide ${STATUS_STYLE[d.status]}`}
          >
            {d.status}
          </span>
        </div>

        {d.status === "done" && (
          <div className="flex gap-4 mt-3 font-mono text-xs text-sage">
            {d.front_knee_angle_release_deg != null && (
              <span>
                Front leg brace:{" "}
                {d.front_knee_angle_release_deg.toFixed(0)}°
              </span>
            )}

            {d.trunk_bend_angle_release_deg != null && (
              <span>
                Body lean:{" "}
                {d.trunk_bend_angle_release_deg.toFixed(0)}°
              </span>
            )}
          </div>
        )}
      </Link>
    </div>
  );
}

export default function History() {
  const [deliveries, setDeliveries] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.myDeliveries()
      .then(setDeliveries)
      .catch((e) => setError(e.message));
  }, []);

  function handleDeleted(id) {
    setDeliveries((prev) => prev.filter((d) => d.id !== id));
  }

  function handleRenamed(id, newName) {
    setDeliveries((prev) =>
      prev.map((d) =>
        d.id === id
          ? { ...d, original_filename: newName }
          : d
      )
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      <h1 className="font-display text-3xl text-cream tracking-wide">
        My Deliveries
      </h1>

      <SeamDivider className="max-w-xs my-4" />

      {error && (
        <p className="text-seam-light text-sm">
          {error}
        </p>
      )}

      {deliveries && deliveries.length === 0 && (
        <p className="text-sage font-mono text-sm">
          Nothing here yet.{" "}
          <Link
            to="/"
            className="text-bail hover:text-bail-light"
          >
            Analyse your first delivery.
          </Link>
        </p>
      )}

      <div className="space-y-3">
        {deliveries?.map((d) => (
          <DeliveryCard
            key={d.id}
            d={d}
            onDeleted={handleDeleted}
            onRenamed={handleRenamed}
          />
        ))}
      </div>
    </div>
  );
}