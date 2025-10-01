import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { Toaster } from 'react-hot-toast';

// Pages
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import SintaDosen from './pages/SintaDosen';
import SintaPublikasi from './pages/SintaPublikasi';
import ScholarDosen from './pages/ScholarDosen';
import ScholarPublikasi from './pages/ScholarPublikasi';
import Scraping from './pages/Scraping';

// Components
import Navbar from './components/Navbar';
import ProtectedRoute from './components/ProtectedRoute';

// Services
import authService from './services/authService';

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if user is logged in
    const token = authService.getToken();
    const userData = authService.getCurrentUser();
    
    if (token && userData) {
      setUser(userData);
    }
    
    setLoading(false);
  }, []);

  const handleLogin = (userData) => {
    setUser(userData);
  };

  const handleLogout = () => {
    authService.logout();
    setUser(null);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <Router future={{
      v7_startTransition: true,
      v7_relativeSplatPath: true
    }}>
      <div className="min-h-screen bg-gray-50">
        <Toaster 
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              background: '#363636',
              color: '#fff',
            },
            success: {
              duration: 3000,
              theme: {
                primary: 'green',
                secondary: 'black',
              },
            },
          }}
        />

        {user && <Navbar user={user} onLogout={handleLogout} />}

        <Routes>
          {/* Public Routes */}
          <Route 
            path="/login" 
            element={
              user ? <Navigate to="/dashboard" replace /> : 
              <Login onLogin={handleLogin} />
            } 
          />
          <Route 
            path="/register" 
            element={
              user ? <Navigate to="/dashboard" replace /> : 
              <Register />
            } 
          />

          {/* Protected Routes */}
          <Route 
            path="/dashboard" 
            element={
              <ProtectedRoute user={user}>
                <Dashboard />
              </ProtectedRoute>
            } 
          />

          {/* SINTA Routes */}
          <Route 
            path="/sinta/dosen" 
            element={
              <ProtectedRoute user={user}>
                <SintaDosen />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/sinta/publikasi" 
            element={
              <ProtectedRoute user={user}>
                <SintaPublikasi />
              </ProtectedRoute>
            } 
          />

          {/* Google Scholar Routes */}
          <Route 
            path="/scholar/dosen" 
            element={
              <ProtectedRoute user={user}>
                <ScholarDosen />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/scholar/publikasi" 
            element={
              <ProtectedRoute user={user}>
                <ScholarPublikasi />
              </ProtectedRoute>
            } 
          />

          {/* Scraping Route */}
          <Route 
            path="/scraping" 
            element={
              <ProtectedRoute user={user}>
                <Scraping />
              </ProtectedRoute>
            } 
          />

          {/* Default Routes */}
          <Route 
            path="/" 
            element={
              user ? <Navigate to="/dashboard" replace /> : 
              <Navigate to="/login" replace />
            } 
          />
          <Route 
            path="*" 
            element={<Navigate to="/" replace />} 
          />
        </Routes>
      </div>
    </Router>
  );
}

export default App;