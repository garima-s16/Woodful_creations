import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { candidatesAPI, interviewsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Card from '../components/common/Card';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import { statusClass } from '../utils/statusColors';

function CandidateDetailPage() {
  const { candidateId } = useParams();
  const [candidate, setCandidate] = useState(null);
  const [interviews, setInterviews] = useState([]);
  const [showSchedule, setShowSchedule] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    candidatesAPI.get(candidateId).then((res) => setCandidate(res.data)).catch(() => setError('Unable to load this candidate.'));
    interviewsAPI.list({ candidate_id: candidateId }).then((res) => setInterviews(res.data));
  }, [candidateId]);

  useEffect(load, [load]);

  const handleSchedule = async (formData) => {
    setLoading(true); setError('');
    try {
      await interviewsAPI.create({
        ...formData, candidate_id: Number(candidateId),
        scheduled_date: new Date(formData.scheduled_date).toISOString(),
      });
      setShowSchedule(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to schedule interview');
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = async (status) => {
    try {
      await candidatesAPI.update(candidateId, { status });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update status');
    }
  };

  if (error && !candidate) return <div className="page"><Alert type="error" message={error} /></div>;
  if (!candidate) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <Link to="/candidates" className="btn-link">&larr; Back to Candidates</Link>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{candidate.name}</h1>
          <div className="detail-subtitle">
            {candidate.position || 'Position not specified'}
            {' '}<span className={`status-badge ${statusClass(candidate.status)}`}>{candidate.status}</span>
          </div>
        </div>
        <div className="page-actions">
          <button className="btn-secondary" onClick={() => setShowSchedule(true)}>Schedule Interview</button>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      <div className="dashboard-grid">
        <Card title="Candidate Details">
          <div className="card-body">
            <div className="detail-meta">
              <div className="detail-meta-item"><span className="detail-meta-label">Email</span><span className="detail-meta-value">{candidate.email || '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Phone</span><span className="detail-meta-value">{candidate.phone || '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Experience</span><span className="detail-meta-value">{candidate.experience || '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Resume</span><span className="detail-meta-value">{candidate.resume_url ? <a href={candidate.resume_url} target="_blank" rel="noreferrer">View Resume</a> : '-'}</span></div>
            </div>
            {candidate.remarks && (
              <div style={{ marginTop: 16 }}>
                <span className="detail-meta-label">Remarks</span>
                <p>{candidate.remarks}</p>
              </div>
            )}
            <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
              {['Applied', 'Shortlisted', 'Selected', 'Rejected'].map((s) => (
                <button key={s} className={candidate.status === s ? 'btn-primary' : 'btn-secondary'} onClick={() => handleStatusChange(s)}>{s}</button>
              ))}
            </div>
          </div>
        </Card>

        <Card title="Interview History">
          <Table
            columns={[
              { key: 'round', label: 'Round' },
              { key: 'scheduled_date', label: 'Scheduled', render: (v) => new Date(v).toLocaleString() },
              { key: 'interviewer', label: 'Interviewer' },
              { key: 'status', label: 'Status', render: (v) => <span className={`status-badge ${statusClass(v)}`}>{v}</span> },
              { key: 'feedback', label: 'Feedback' },
            ]}
            data={interviews}
            emptyMessage="No interviews scheduled for this candidate yet."
          />
        </Card>
      </div>

      <Modal isOpen={showSchedule} title="Schedule Interview" onClose={() => setShowSchedule(false)}>
        <Form
          fields={[
            { name: 'round', label: 'Round', placeholder: 'Round 1' },
            { name: 'scheduled_date', label: 'Scheduled Date/Time', type: 'datetime-local', required: true },
            { name: 'interviewer', label: 'Interviewer' },
          ]}
          onSubmit={handleSchedule} loading={loading} submitText="Schedule Interview"
        />
      </Modal>
    </div>
  );
}

export default CandidateDetailPage;
