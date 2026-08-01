import React, { useEffect, useState } from 'react';
import './App.css';
import axios from 'axios';

const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const featureGroups = [
  {
    title: 'Operations',
    items: ['Stock inventory', 'Estimates', 'Client management'],
  },
  {
    title: 'Team',
    items: ['Attendance tracking', 'Interviews', 'Role-aware workflows'],
  },
  {
    title: 'Insights',
    items: ['Analytics dashboard', 'AI assistant', 'Backend API health checks'],
  },
];

const laptopSteps = [
  'Start the FastAPI backend on port 8000.',
  'Start the React web app on port 3000.',
  'Open the app in any modern browser on Windows or macOS.',
];

function App() {
  const [apiStatus, setApiStatus] = useState('checking');
  const [appInfo, setAppInfo] = useState(null);

  useEffect(() => {
    checkBackendConnection();
  }, []);

  const checkBackendConnection = async () => {
    try {
      const response = await axios.get(`${apiUrl}/api/health`, {
        timeout: 5000
      });
      setApiStatus('connected');
      setAppInfo(response.data);
    } catch (error) {
      console.error('Backend connection error:', error);
      setApiStatus('disconnected');
    }
  };

  return (
    <div className="App">
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Web application preview</p>
          <h1>Woodful Creations</h1>
          <p className="hero-text">
            A laptop-friendly operations dashboard for inventory, client work, team activity,
            and future mobile expansion.
          </p>
          <div className="hero-actions">
            <button type="button" className="primary-action" onClick={checkBackendConnection}>
              Refresh backend status
            </button>
            <a className="secondary-action" href={`${apiUrl}/docs`} target="_blank" rel="noreferrer">
              Open API docs
            </a>
          </div>
        </div>

        <aside className="status-panel">
          <div className={`status-badge ${apiStatus}`}>
            API Status: {apiStatus.toUpperCase()}
          </div>
          <p className="status-label">Backend URL</p>
          <p className="status-value">{apiUrl}</p>
          {appInfo && (
            <div className="app-info">
              <p>Service: {appInfo.service}</p>
              <p>Version: {appInfo.version}</p>
            </div>
          )}
          {apiStatus === 'disconnected' && (
            <div className="error-message">
              Backend unavailable. Start the API server and refresh to verify the web app is fully connected.
            </div>
          )}
        </aside>
      </header>

      <main className="App-main">
        <section className="feature-section">
          <div className="section-heading">
            <h2>What you can preview on your laptop now</h2>
            <p>
              The repository is set up so the web frontend remains the first-class experience,
              while the codebase is also prepared for a native iPhone app later.
            </p>
          </div>

          <div className="features-grid">
            {featureGroups.map((group) => (
              <article key={group.title} className="feature-card">
                <h3>{group.title}</h3>
                <ul>
                  {group.items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>

        <section className="details-grid">
          <article className="detail-card">
            <h2>Web launch path</h2>
            <ol>
              {laptopSteps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
            <p className="helper-text">Recommended preview URL: http://localhost:3000</p>
          </article>

          <article className="detail-card">
            <h2>Native iPhone preparation</h2>
            <p>
              A dedicated Expo-based <code>mobile/</code> app scaffold sits alongside the web app,
              ready to connect to the same backend API without changing the laptop workflow.
            </p>
            <p className="helper-text">
              When testing on an iPhone later, replace localhost with your computer&apos;s LAN IP in
              the mobile app environment file.
            </p>
          </article>
        </section>
      </main>
    </div>
  );
}

export default App;