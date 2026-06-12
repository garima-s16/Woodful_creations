import React, { useState } from 'react';
import '../../styles/components/interviews/InterviewForm.css';

function InterviewForm({ onAdd, onClose }) {
  const [formData, setFormData] = useState({
    candidate_name: '',
    candidate_email: '',
    candidate_phone: '',
    position: '',
    interview_date: '',
    interview_time: '',
    interview_type: 'in-person',
    panel_members: '',
    notes: ''
  });

  const [errors, setErrors] = useState({});

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    const newErrors = {};
    if (!formData.candidate_name.trim()) newErrors.candidate_name = 'Candidate name is required';
    if (!formData.candidate_email.trim()) newErrors.candidate_email = 'Email is required';
    if (!formData.position.trim()) newErrors.position = 'Position is required';
    if (!formData.interview_date) newErrors.interview_date = 'Interview date is required';
    if (!formData.interview_time) newErrors.interview_time = 'Interview time is required';

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    onAdd(formData);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Schedule New Interview</h2>
          <button className="close-button" onClick={onClose}>X</button>
        </div>

        <form onSubmit={handleSubmit} className="interview-form">
          <div className="form-row">
            <div className="form-group">
              <label>Candidate Name</label>
              <input
                type="text"
                name="candidate_name"
                value={formData.candidate_name}
                onChange={handleChange}
                placeholder="Enter candidate name"
              />
              {errors.candidate_name && <span className="error">{errors.candidate_name}</span>}
            </div>

            <div className="form-group">
              <label>Position</label>
              <input
                type="text"
                name="position"
                value={formData.position}
                onChange={handleChange}
                placeholder="Enter position"
              />
              {errors.position && <span className="error">{errors.position}</span>}
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Email</label>
              <input
                type="email"
                name="candidate_email"
                value={formData.candidate_email}
                onChange={handleChange}
                placeholder="Enter email"
              />
              {errors.candidate_email && <span className="error">{errors.candidate_email}</span>}
            </div>

            <div className="form-group">
              <label>Phone</label>
              <input
                type="tel"
                name="candidate_phone"
                value={formData.candidate_phone}
                onChange={handleChange}
                placeholder="Enter phone number"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Interview Date</label>
              <input
                type="date"
                name="interview_date"
                value={formData.interview_date}
                onChange={handleChange}
              />
              {errors.interview_date && <span className="error">{errors.interview_date}</span>}
            </div>

            <div className="form-group">
              <label>Interview Time</label>
              <input
                type="time"
                name="interview_time"
                value={formData.interview_time}
                onChange={handleChange}
              />
              {errors.interview_time && <span className="error">{errors.interview_time}</span>}
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Interview Type</label>
              <select 
                name="interview_type"
                value={formData.interview_type}
                onChange={handleChange}
              >
                <option value="phone">Phone</option>
                <option value="video">Video</option>
                <option value="in-person">In-Person</option>
              </select>
            </div>

            <div className="form-group">
              <label>Panel Members</label>
              <input
                type="text"
                name="panel_members"
                value={formData.panel_members}
                onChange={handleChange}
                placeholder="Enter panel member names (comma separated)"
              />
            </div>
          </div>

          <div className="form-group">
            <label>Notes</label>
            <textarea
              name="notes"
              value={formData.notes}
              onChange={handleChange}
              placeholder="Add any notes"
              rows="3"
            />
          </div>

          <div className="modal-footer">
            <button type="button" className="btn-cancel" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-submit">Schedule Interview</button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default InterviewForm;