import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Navbar from "./components/Navbar";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Home from "./pages/Home";
import Results from "./pages/Results";
import History from "./pages/History";
import CoachDashboard from "./pages/CoachDashboard";
import SpeedCheck from "./pages/SpeedCheck";   

function RequireAuth({ children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function RequireCoach({ children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "coach") return <Navigate to="/" replace />;
  return children;
}

function Shell() {
  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/" element={<RequireAuth><Home /></RequireAuth>} />
        <Route path="/results/:id" element={<RequireAuth><Results /></RequireAuth>} />
        <Route path="/history" element={<RequireAuth><History /></RequireAuth>} />
         <Route path="/speed-check" element={<RequireAuth><SpeedCheck /></RequireAuth>} />
        <Route path="/coach" element={<RequireCoach><CoachDashboard /></RequireCoach>} />
      </Routes>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Shell />
      </AuthProvider>
    </BrowserRouter>
  );
}
