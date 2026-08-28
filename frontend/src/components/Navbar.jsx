import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <nav className="border-b border-pitch-700 bg-pitch-900/80 backdrop-blur sticky top-0 z-10">
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        <Link to="/" className="font-display text-xl tracking-wide text-cream">
          PACE<span className="text-seam">CHECK</span>
        </Link>
        <div className="flex items-center gap-6 font-body text-sm">
          {user ? (
            <>
              <Link to="/" className="text-sage hover:text-cream transition-colors">Analyse</Link>
              <Link to="/history" className="text-sage hover:text-cream transition-colors">My Deliveries</Link>
              <Link to="/speed-check" className="text-sage hover:text-cream transition-colors">Speed Check</Link>
              {user.role === "coach" && (
                <Link to="/coach" className="text-bail hover:text-bail-light transition-colors">Coach Dashboard</Link>
              )}
              <span className="text-sage">|</span>
              <span className="text-cream">{user.username}</span>
              <button
                onClick={() => { logout(); navigate("/login"); }}
                className="px-3 py-1.5 rounded border border-pitch-600 text-sage hover:text-cream hover:border-sage transition-colors"
              >
                Log out
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="text-sage hover:text-cream transition-colors">Log in</Link>
              <Link to="/signup" className="px-4 py-1.5 rounded bg-seam hover:bg-seam-light text-cream transition-colors">
                Sign up
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
