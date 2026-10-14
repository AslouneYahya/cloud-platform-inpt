import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage.jsx';
import DashboardPage from './pages/DashboardPage.jsx';

/**
 * App — root routing component.
 *
 * Routes:
 *   /login      → LoginPage
 *   /dashboard  → DashboardPage (access enforced inside the component via getMe())
 *   /           → redirect to /login (catch-all also redirects)
 */
function App() {
  return (
    <Routes>
      {/* Default: redirect root to login */}
      <Route path="/" element={<Navigate to="/login" replace />} />

      {/* Authentication */}
      <Route path="/login" element={<LoginPage />} />

      {/* Protected area — component self-guards via API call on mount */}
      <Route path="/dashboard" element={<DashboardPage />} />

      {/* Catch-all: redirect unknown paths to login */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

export default App;
