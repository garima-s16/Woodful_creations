import React, { useState, useEffect } from 'react';
import axios from 'axios';
import '../styles/pages/EstimatesPage.css';
import EstimateList from '../components/estimates/EstimateList';
import EstimateForm from '../components/estimates/EstimateForm';
import EstimatePreview from '../components/estimates/EstimatePreview';

function EstimatesPage({ user }) {
  const [estimates, setEstimates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedEstimate, setSelectedEstimate] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [filterStatus, setFilterStatus] = useState('all');

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    fetchEstimates();
  }, [filterStatus]);

  const fetchEstimates = async () => {
    try {
      const token = localStorage.getItem('authToken');
      const params = new URLSearchParams();
      if (filterStatus !== 'all') params.append('status', filterStatus);

      const response = await axios.get(
        `${API_BASE_URL}/api/estimates?${params.toString()}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setEstimates(response.data.estimates);
    } catch (err) {
      setError('Failed to load estimates');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddEstimate = async (estimateData) => {
    try {
      const token = localStorage.getItem('authToken');
      await axios.post(
        `${API_BASE_URL}/api/estimates`,
        estimateData,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setShowForm(false);
      fetchEstimates();
    } catch (err) {
      setError('Failed to create estimate');
      console.error(err);
    }
  };

  const handleGeneratePDF = async (estimateId) => {
    try {
      const token = localStorage.getItem('authToken');
      const response = await axios.get(
        `${API_BASE_URL}/api/estimates/${estimateId}/generate-pdf`,
        { 
          headers: { Authorization: `Bearer ${token}` },
          responseType: 'blob'
        }
      );
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `estimate-${estimateId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.parentChild.removeChild(link);
    } catch (err) {
      setError('Failed to generate PDF');
      console.error(err);
    }
  };

  const handleSendEmail = async (estimateId, recipientEmail) => {
    try {
      const token = localStorage.getItem('authToken');
      await axios.post(
        `${API_BASE_URL}/api/estimates/${estimateId}/send-email`,
        { recipient_email: recipientEmail },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      alert('Estimate sent successfully');
    } catch (err) {
      setError('Failed to send email');
      console.error(err);
    }
  };

  return (
    <div className="estimates-page">
      <div className="estimates-header">
        <div>
          <h1>Cost Estimates</h1>
          <p>Create and manage cost estimates for clients</p>
        </div>
        {user?.role === 'master' && (
          <button 
            className="btn-primary"
            onClick={() => setShowForm(true)}
          >
            Create New Estimate
          </button>
        )}
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="estimates-filter">
        <select 
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="filter-select"
        >
          <option value="all">All Estimates</option>
          <option value="draft">Draft</option>
          <option value="sent">Sent</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      <div className="estimates-container">
        <div className="estimates-list-section">
          {loading ? (
            <div className="loading">Loading estimates...</div>
          ) : (
            <EstimateList 
              estimates={estimates}
              selectedEstimate={selectedEstimate}
              onSelectEstimate={setSelectedEstimate}
              onGeneratePDF={handleGeneratePDF}
            />
          )}
        </div>

        {selectedEstimate && (
          <div className="estimates-preview-section">
            <EstimatePreview 
              estimate={selectedEstimate}
              onSendEmail={handleSendEmail}
              onGeneratePDF={handleGeneratePDF}
            />
          </div>
        )}
      </div>

      {showForm && (
        <EstimateForm
          onAdd={handleAddEstimate}
          onClose={() => setShowForm(false)}
        />
      )}
    </div>
  );
}

export default EstimatesPage;