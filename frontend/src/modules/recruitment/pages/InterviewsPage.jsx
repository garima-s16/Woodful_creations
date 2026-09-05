import React, { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { interviewsAPI, candidatesAPI } from '../../../utils/api';
import Table from '../../../components/common/Table';
import Modal from '../../../components/common/Modal';
import Form from '../../../components/common/Form';
import Alert from '../../../components/common/Alert';

function InterviewsPage() {
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [interviews, setInterviews] = useState([]);
  const [candidates, setCandidates] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [feedbackTarget, setFeedbackTarget] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = () => {
    setPageLoading(true);
    setLoadError(false);
    interviewsAPI.list().then((res) => setInterviews(res.data)).catch((err) => {
      setLoadError(true);
      setError(err.response?.status === 403 ? 'You do not have permission to view interviews.' : 'Unable to load interviews. Please try again.');
    }).finally(() => setPageLoading(false));
    candidatesAPI.list().then((res) => setCandidates(res.data)).catch(() => {});
  };
  useEffect(load, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await interviewsAPI.create({
        ...formData,
        candidate_id: Number(formData.candidate_id),
        scheduled_date: new Date(formData.scheduled_date).toISOString(),
      });
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to schedule interview');
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = async (id, status) => {
    try {
      await interviewsAPI.update(id, { status });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update interview status');
    }
  };

  const handleFeedbackSubmit = async (formData) => {
    setLoading(true);
    setError('');
    try {
      const payload = { ...formData };
      ['overall_rating', 'technical_rating', 'communication_rating', 'culture_fit_rating'].forEach((f) => {
        payload[f] = formData[f] ? Number(formData[f]) : null;
      });
      await interviewsAPI.update(feedbackTarget.id, payload);
      setFeedbackTarget(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save feedback');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'candidate_id', label: 'Candidate', render: (v) => candidates.find((c) => c.id === v)?.name || v },
    { key: 'round', label: 'Round' },
    { key: 'scheduled_date', label: 'Scheduled', render: (v) => new Date(v).toLocaleString() },
    { key: 'interviewer', label: 'Interviewer' },
    { key: 'recommendation', label: 'Recommendation', render: (v) => v || '-' },
    {
      key: 'status', label: 'Status', render: (v, row) => (
        <select value={v} onChange={(e) => handleStatusChange(row.id, e.target.value)}>
          {['Scheduled', 'Completed', 'Rescheduled', 'Cancelled'].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      ),
    },
    {
      key: 'feedback_action', label: '', render: (v, row) => (
        <button className="btn-link" onClick={() => setFeedbackTarget(row)}>
          {row.overall_rating ? 'Edit Feedback' : 'Add Feedback'}
        </button>
      ),
    },
  ];

  const fields = [
    { name: 'candidate_id', label: 'Candidate', type: 'select', required: true, options: candidates.map((c) => ({ value: c.id, label: c.name })) },
    { name: 'round', label: 'Round', placeholder: 'Round 1' },
    { name: 'scheduled_date', label: 'Scheduled Date/Time', type: 'datetime-local', required: true },
    { name: 'interviewer', label: 'Interviewer' },
  ];

  const ratingOptions = [1, 2, 3, 4, 5].map((n) => ({ value: n, label: String(n) }));
  const feedbackFields = [
    { name: 'overall_rating', label: 'Overall Rating (1-5)', type: 'select', options: ratingOptions },
    { name: 'recommendation', label: 'Recommendation', type: 'select', options: [
      { value: 'Strong Hire', label: 'Strong Hire' }, { value: 'Hire', label: 'Hire' },
      { value: 'Hold', label: 'Hold' }, { value: 'Reject', label: 'Reject' },
    ] },
    { name: 'technical_rating', label: 'Technical Rating (1-5)', type: 'select', options: ratingOptions, advanced: true },
    { name: 'communication_rating', label: 'Communication (1-5)', type: 'select', options: ratingOptions, advanced: true },
    { name: 'culture_fit_rating', label: 'Culture/Fit (1-5)', type: 'select', options: ratingOptions, advanced: true },
    { name: 'strengths', label: 'Strengths', type: 'textarea', advanced: true },
    { name: 'weaknesses', label: 'Weaknesses', type: 'textarea', advanced: true },
    { name: 'observations', label: 'Observations', type: 'textarea', advanced: true },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Interviews</h1>
          <p className="page-summary">Schedule and track candidate interviews and outcomes.</p>
        </div>
        {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>Schedule Interview</button>}
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={interviews} loading={pageLoading} error={loadError} onRetry={load} emptyMessage="No interviews scheduled yet." />
      <Modal isOpen={showAdd} title="Schedule Interview" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Schedule" />
      </Modal>
      <Modal
        isOpen={!!feedbackTarget}
        title={`Feedback - ${candidates.find((c) => c.id === feedbackTarget?.candidate_id)?.name || ''}`}
        onClose={() => setFeedbackTarget(null)}
      >
        {feedbackTarget && (
          <Form
            fields={feedbackFields} onSubmit={handleFeedbackSubmit} loading={loading} submitText="Save Feedback"
            initialValues={{
              overall_rating: feedbackTarget.overall_rating || '', technical_rating: feedbackTarget.technical_rating || '',
              communication_rating: feedbackTarget.communication_rating || '', culture_fit_rating: feedbackTarget.culture_fit_rating || '',
              strengths: feedbackTarget.strengths || '', weaknesses: feedbackTarget.weaknesses || '',
              observations: feedbackTarget.observations || '', recommendation: feedbackTarget.recommendation || '',
            }}
          />
        )}
      </Modal>
    </div>
  );
}

export default InterviewsPage;
