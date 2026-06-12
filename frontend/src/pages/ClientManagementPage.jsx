import React, { useState, useEffect } from 'react';
import axios from 'axios';
import '../styles/pages/ClientManagementPage.css';
import ClientList from '../components/clients/ClientList';
import ClientProfile from '../components/clients/ClientProfile';
import AddClientModal from '../components/clients/AddClientModal';

function ClientManagementPage({ user }) {
  const [clients, setClients] = useState([]);
  const [selectedClient, setSelectedClient] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    fetchClients();
  }, [searchTerm]);

  const fetchClients = async () => {
    try {
      const token = localStorage.getItem('authToken');
      const params = new URLSearchParams();
      if (searchTerm) params.append('search', searchTerm);

      const response = await axios.get(
        `${API_BASE_URL}/api/clients?${params.toString()}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setClients(response.data.clients);
    } catch (err) {
      setError('Failed to load clients');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddClient = async (clientData) => {
    try {
      const token = localStorage.getItem('authToken');
      await axios.post(
        `${API_BASE_URL}/api/clients`,
        clientData,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setShowAddModal(false);
      fetchClients();
    } catch (err) {
      setError('Failed to add client');
      console.error(err);
    }
  };

  const handleUpdateClient = async (clientId, updatedData) => {
    try {
      const token = localStorage.getItem('authToken');
      await axios.put(
        `${API_BASE_URL}/api/clients/${clientId}`,
        updatedData,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      fetchClients();
      setSelectedClient(null);
    } catch (err) {
      setError('Failed to update client');
      console.error(err);
    }
  };

  return (
    <div className="client-management-page">
      <div className="client-header">
        <div>
          <h1>Client Management</h1>
          <p>Manage all your clients and their projects</p>
        </div>
        {user?.role === 'master' && (
          <button 
            className="btn-primary"
            onClick={() => setShowAddModal(true)}
          >
            Add New Client
          </button>
        )}
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="client-container">
        <div className="client-list-section">
          <div className="search-box">
            <input
              type="text"
              placeholder="Search clients..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          {loading ? (
            <div className="loading">Loading clients...</div>
          ) : (
            <ClientList 
              clients={clients}
              selectedClient={selectedClient}
              onSelectClient={setSelectedClient}
            />
          )}
        </div>

        <div className="client-detail-section">
          {selectedClient ? (
            <ClientProfile 
              client={selectedClient}
              user={user}
              onUpdate={handleUpdateClient}
            />
          ) : (
            <div className="no-selection">
              <p>Select a client to view details</p>
            </div>
          )}
        </div>
      </div>

      {showAddModal && (
        <AddClientModal
          onAdd={handleAddClient}
          onClose={() => setShowAddModal(false)}
        />
      )}
    </div>
  );
}

export default ClientManagementPage;