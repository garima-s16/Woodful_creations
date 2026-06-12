import React from 'react';
import '../../styles/components/interviews/InterviewList.css';

function InterviewList({ interviews, selectedInterview, onSelectInterview }) {
  const getStatusColor = (status) => {
    const colors = {
      'scheduled': 'scheduled',
      'completed': 'completed',
      'selected': 'selected',
      'rejected': 'rejected'
    };
    return colors[status] || 'default';
  };

  return (
    <div className="interview-list">
      {interviews.length > 0 ? (
        <ul className="interview-items">
          {interviews.map(interview => (
            <li 
              key={interview.id}
              className={`interview-item ${selectedInterview?.id === interview.id ? 'selected' : ''}`}
              onClick={() => onSelectInterview(interview)}
            >
              <div className="interview-header">
                <div className="candidate-name">{interview.candidate_name}</div>
                <div className={`status-badge ${getStatusColor(interview.status)}`}>
                  {interview.status.toUpperCase()}
                </div>
              </div>
              <div className="interview-info">
                <span className="position">{interview.position}</span>
                <span className="interview-date">{interview.interview_date}</span>
              </div>
              <div className="interview-type">
                {interview.interview_type}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="no-interviews">No interviews found</div>
      )}
    </div>
  );
}

export default InterviewList;