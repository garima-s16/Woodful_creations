import React, { useState } from 'react';
import '../../styles/components/interviews/CandidateProfile.css';

function CandidateProfile({ interview, user, onUpdateStatus, onGenerateOfferLetter }) {
  const [feedback, setFeedback] = useState('');
  const [showFeedbackForm, setShowFeedbackForm] = useState(false);

  const handleUpdateStatus = (newStatus) => {
    onUpdateStatus(interview.id, newStatus, feedback);
    setFeedback('');
    setShowFeedbackForm(false);
  };

  return (
    <div className="candidate-profile">
      <div className="profile-header">
        <div>
          <h2>{interview.candidate_name}</h2>
          <p className="position-title">{interview.position}</p>
        </div>
        <span className={`status-badge ${interview.status}`}>
          {interview.status.toUpperCase()}
        </span>
      </div>

      <div className="profile-content">
        <div className="info-section">
          <h3>Contact Information</h3>
          <div className="info-row">
            <span className="label">Email:</span>
            <span className="value">{interview.candidate_email}</span>
          </div>
          <div className="info-row">
            <span className="label">Phone:</span>
            <span className="value">{interview.candidate_phone}</span>
          </div>
        </div>

        <div className="info-section">
          <h3>Interview Details</h3>
          <div className="info-row">
            <span className="label">Date:</span>
            <span className="value">{interview.interview_date}</span>
          </div>
          <div className="info-row">
            <span className="label">Time:</span>
            <span className="value">{interview.interview_time}</span>
          </div>
          <div className="info-row">
            <span className="label">Type:</span>
            <span className="value">{interview.interview_type}</span>
          </div>
          {interview.panel_members && (
            <div className="info-row">
              <span className="label">Panel Members:</span>
              <span className="value">{interview.panel_members}</span>
            </div>
          )}
        </div>

        {interview.feedback && (
          <div className="info-section">
            <h3>Feedback</h3>
            <p>{interview.feedback}</p>
          </div>
        )}

        {user?.role === 'master' && interview.status === 'completed' && (
          <div className="actions-section">
            <button 
              className="btn-action"
              onClick={() => handleUpdateStatus('selected')}
            >
              Select Candidate
            </button>
            <button 
              className="btn-action reject"
              onClick={() => handleUpdateStatus('rejected')}
            >
              Reject Candidate
            </button>
            {interview.status === 'selected' && (
              <button 
                className="btn-action"
                onClick={() => onGenerateOfferLetter(interview.id)}
              >
                Generate Offer Letter
              </button>
            )}
          </div>
        )}

        {user?.role === 'master' && !showFeedbackForm && interview.status === 'scheduled' && (
          <div className="actions-section">
            <button 
              className="btn-action"
              onClick={() => setShowFeedbackForm(true)}
            >
              Mark as Completed
            </button>
          </div>
        )}

        {showFeedbackForm && (
          <div className="feedback-form">
            <h3>Interview Feedback</h3>
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="Enter interview feedback"
              rows="4"
            />
            <div className="form-actions">
              <button 
                className="btn-save"
                onClick={() => handleUpdateStatus('completed')}
              >
                Save Feedback
              </button>
              <button 
                className="btn-cancel"
                onClick={() => setShowFeedbackForm(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default CandidateProfile;