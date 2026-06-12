import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Navigation from './components/Navigation';
import Dashboard from './pages/Dashboard';
import StockInventory from './pages/StockInventory';
import Estimates from './pages/Estimates';
import Attendance from './pages/Attendance';
import Interviews from './pages/Interviews';
import Clients from './pages/Clients';
import Payments from './pages/Payments';
import Analytics from './pages/Analytics';
import Login from './pages/Login';
import ChatBox from './components/ChatBox';
import './styles/App.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userRole, setUserRole] = useState(null);
  const [showChat, setShowChat] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('authToken');
    if (token) {
      setIsAuthenticated(true);
      const role = localStorage.getItem('userRole');
      setUserRole(role);
    }
  }, []);

  const handleLogin = (token, role) => {
    localStorage.setItem('authToken', token);
    localStorage.setItem('userRole', role);
    setIsAuthenticated(true);
    setUserRole(role);
  };

  const handleLogout = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('userRole');
    setIsAuthenticated(false);
    setUserRole(null);
  };

  if (!isAuthenticated) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <Router>
      <div className="app">
        <Navigation onLogout={handleLogout} userRole={userRole} />
        <div className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard userRole={userRole} />} />
            <Route path="/inventory" element={<StockInventory userRole={userRole} />} />
            <Route path="/estimates" element={<Estimates userRole={userRole} />} />
            <Route path="/attendance" element={<Attendance userRole={userRole} />} />
            <Route path="/interviews" element={<Interviews userRole={userRole} />} />
            <Route path="/clients" element={<Clients userRole={userRole} />} />
            <Route path="/payments" element={<Payments userRole={userRole} />} />
            <Route path="/analytics" element={<Analytics userRole={userRole} />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </div>
        <button 
          className="chat-toggle"
          onClick={() => setShowChat(!showChat)}
          title="Open AI Chat"
        >
          Chat
        </button>
        {showChat && <ChatBox onClose={() => setShowChat(false)} />}
      </div>
    </Router>
  );
}

export default App;