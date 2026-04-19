import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./Components/Layout";
import RequireAuth from "./Components/RequireAuth";

// Public pages
import Home from "./Pages/Home";
import About from "./Pages/About";
import Contact from "./Pages/Contact";
import Login from "./Pages/Login";

// Admin pages (these wrap themselves in AdminLayout)
import Dashboard from "./Pages/Dashboard";
import LiveMonitoring from "./Pages/LiveMonitoring";
import ViolationDetection from "./Pages/ViolationDetection";
import ViolationRecords from "./Pages/ViolationRecords";
import EvidenceManagement from "./Pages/EvidenceManagement";

function App() {
  return (
    <Routes>
      {/* Public routes (wrapped with top-navbar Layout) */}
      <Route path="/" element={<Layout><Home /></Layout>} />
      <Route path="/about" element={<Layout><About /></Layout>} />
      <Route path="/contact" element={<Layout><Contact /></Layout>} />
      <Route path="/login" element={<Layout><Login /></Layout>} />

      {/* Admin routes (self-wrapped in AdminLayout) */}
      <Route
        path="/dashboard"
        element={<RequireAuth><Dashboard /></RequireAuth>}
      />
      <Route
        path="/live-monitoring"
        element={<RequireAuth><LiveMonitoring /></RequireAuth>}
      />
      <Route
        path="/violation-detection"
        element={<RequireAuth><ViolationDetection /></RequireAuth>}
      />
      <Route
        path="/violation-records"
        element={<RequireAuth><ViolationRecords /></RequireAuth>}
      />
      <Route
        path="/evidence"
        element={<RequireAuth><EvidenceManagement /></RequireAuth>}
      />

      {/* Legacy redirects */}
      <Route path="/webcam" element={<Navigate to="/violation-detection" replace />} />
      <Route path="/violations" element={<Navigate to="/violation-records" replace />} />

      {/* 404 fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
