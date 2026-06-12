import React, { useState, useEffect } from 'react';
import axios from 'axios';
import '../styles/pages/InterviewsPage.css';
import InterviewList from '../components/interviews/InterviewList';
import InterviewForm from '../components/interviews/InterviewForm';
import CandidateProfile from '../components/interviews/CandidateProfile';

function InterviewsPage({ user }) {
  const [interviews, setInterviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedInterview, setSelectedInterview] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [filterStatus, setFilterStatus] = useState('all');

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    fetchInterviews();
  }, [filterStatus]);

  const fetchInterviews = async () => {
    try {
      const token = localStorage.getItem('authToken');
      const params = new URLSearchParams();
      if (filterStatus !== 'all') params.append('status', filterStatus);

      const response = await axios.get(
        `${API_BASE_URL}/api/interviews?${params.toString()}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setInterviews(response.data.interviews);
    } catch (err) {
      setError('Failed to load interviews');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddInterview = async (interviewData) => {
    try {
      const token = localStorage.getItem('authToken');
      await axios.post(
        `${API_BASE_URL}/api/interviews`,
        interviewData,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setShowForm(false);
      fetchInterviews();
    } catch (err) {
      setError('Failed to create interview');
      console.error(err);
    }
  };

  const handleUpdateInterviewStatus = async (interviewId, status, feedback = '') => {
    try {
      const token = localStorage.getItem('authToken');
      await axios.put(
        `${API_BASE_URL}/api/interviews/${interviewId}`,
        { status, feedback },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      fetchInterviews();
      setSelectedInterview(null);
    } catch (err) {
      setError('Failed to update interview');
      console.error(err);
    }
  };

  const handleGenerateOfferLetter = async (interviewId) => {
    try {
      const token = localStorage.getItem('authToken');
      const response = await axios.get(
        `${API_BASE_URL}/api/interviews/${interviewId}/offer-letter`,
        { 
          headers: { Authorization: `Bearer ${token}` },
          responseType: 'blob'
        }
      );
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `offer-letter-${interviewId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.parentChild.removeChild(link);
    } catch (err) {
      setError('Failed to generate offer letter');
      console.error(err);
    }
  };

  return (
    <div className="interviews-page">
      <div className="interviews-header">
        <div>
          <h1>Interview Tracking</h1>
          <p>Manage recruitment and interview process</p>
        </div>
        {user?.role === 'master' && (
          <button 
            className="btn-primary"
            onClick={() => setShowForm(true)}
          >
            Schedule New Interview
          </button>
        )}
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="interviews-filter">
        <select 
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="filter-select"
        >
          <option value="all">All Interviews</option>
          <option value="scheduled">Scheduled</option>
          <option value="completed">Completed</option>
          <option value="selected">Selected</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      <div className="interviews-container">
        <div className="interviews-list-section">
          {loading ? (
            <div className="loading">Loading interviews...</div>
          ) : (
            <InterviewList 
              interviews={interviews}
              selectedInterview={selectedInterview}
              onSelectInterview={setSelectedInterview}
            />
          )}
        </div>

        {selectedInterview && (
          <div className="interviews-detail-section">
            <CandidateProfile 
              interview={selectedInterview}
              user={user}
              onUpdateStatus={handleUpdateInterviewStatus}
              onGenerateOfferLetter={handleGenerateOfferLetter}
            />
          </div>
        )}
      </div>

      {showForm && (
        <InterviewForm
          onAdd={handleAddInterview}
          onClose={() => setShowForm(false)}
        />
      )}
    </div>
  );
}

export default InterviewsPage;