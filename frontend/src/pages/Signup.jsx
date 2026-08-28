import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import SeamDivider from "../components/SeamDivider";

export default function Signup() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("user");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { signup } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await signup(username, password, role);
      navigate("/");
    } catch (err) {
      setError(err.message || "Could not create account");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-[calc(100vh-73px)] flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <h1 className="font-display text-3xl text-cream text-center">Create your account</h1>
        <SeamDivider className="my-4" />
        <p className="text-sage text-sm text-center mb-8">Start tracking your bowling action.</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-sage mb-1.5" htmlFor="username">Username</label>
            <input
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="w-full px-4 py-2.5 rounded bg-pitch-800 border border-pitch-600 text-cream placeholder-sage/50 focus:border-bail outline-none"
              placeholder="pick a username"
            />
          </div>
          <div>
            <label className="block text-sm text-sage mb-1.5" htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              className="w-full px-4 py-2.5 rounded bg-pitch-800 border border-pitch-600 text-cream placeholder-sage/50 focus:border-bail outline-none"
              placeholder="at least 6 characters"
            />
          </div>

          <fieldset>
            <legend className="block text-sm text-sage mb-1.5">Account type</legend>
            <div className="flex gap-3">
              <label className={`flex-1 text-center px-3 py-2 rounded border cursor-pointer transition-colors ${role === "user" ? "border-bail bg-pitch-700 text-cream" : "border-pitch-600 text-sage"}`}>
                <input type="radio" name="role" value="user" checked={role === "user"} onChange={() => setRole("user")} className="sr-only" />
                Player
              </label>
              <label className={`flex-1 text-center px-3 py-2 rounded border cursor-pointer transition-colors ${role === "coach" ? "border-bail bg-pitch-700 text-cream" : "border-pitch-600 text-sage"}`}>
                <input type="radio" name="role" value="coach" checked={role === "coach"} onChange={() => setRole("coach")} className="sr-only" />
                Coach
              </label>
            </div>
            <p className="text-xs text-sage/70 mt-1.5">
              Coach accounts can view every player's deliveries and reports.
            </p>
          </fieldset>

          {error && <p className="text-seam-light text-sm">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded bg-seam hover:bg-seam-light disabled:opacity-50 text-cream font-medium transition-colors"
          >
            {loading ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p className="text-sage text-sm text-center mt-6">
          Already have an account?{" "}
          <Link to="/login" className="text-bail hover:text-bail-light">Log in</Link>
        </p>
      </div>
    </div>
  );
}
