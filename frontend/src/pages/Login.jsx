import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import SeamDivider from "../components/SeamDivider";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      setError(err.message || "Could not log in");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-[calc(100vh-73px)] flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <h1 className="font-display text-3xl text-cream text-center">Welcome back</h1>
        <SeamDivider className="my-4" />
        <p className="text-sage text-sm text-center mb-8">Log in to review your deliveries.</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-sage mb-1.5" htmlFor="username">Username</label>
            <input
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="w-full px-4 py-2.5 rounded bg-pitch-800 border border-pitch-600 text-cream placeholder-sage/50 focus:border-bail outline-none"
              placeholder="your username"
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
              className="w-full px-4 py-2.5 rounded bg-pitch-800 border border-pitch-600 text-cream placeholder-sage/50 focus:border-bail outline-none"
              placeholder="••••••••"
            />
          </div>

          {error && <p className="text-seam-light text-sm">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded bg-seam hover:bg-seam-light disabled:opacity-50 text-cream font-medium transition-colors"
          >
            {loading ? "Logging in..." : "Log in"}
          </button>
        </form>

        <p className="text-sage text-sm text-center mt-6">
          No account yet?{" "}
          <Link to="/signup" className="text-bail hover:text-bail-light">Sign up</Link>
        </p>
      </div>
    </div>
  );
}
