import React, { useEffect, useState } from 'react';
import { interviewsAPI, candidatesAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';

function InterviewsPage() {
  const [interviews, setInterviews] = useState([]);
  const [candidates, setCandidates] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = () => {
    interviewsAPI.list().then((res) => setInterviews(res.data)).catch(() => setError('You do not have permission to view interviews.'));
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

  const handleFeedback = async (id, status) => {
    const feedback = window.prompt('Feedback (optional):') || '';
    try {
      await interviewsAPI.update(id, { status, feedback });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update interview');
    }
  };

  const columns = [
    { key: 'candidate_id', label: 'Candidate', render: (v) => candidates.find((c) => c.id === v)?.name || v },
    { key: 'round', label: 'Round' },
    { key: 'scheduled_date', label: 'Scheduled', render: (v) => new Date(v).toLocaleString() },
    { key: 'interviewer', label: 'Interviewer' }, { key: 'feedback', label: 'Feedback' },
    {
      key: 'status', label: 'Status', render: (v, row) => (
        <select value={v} onChange={(e) => handleFeedback(row.id, e.target.value)}>
          {['Scheduled', 'Completed', 'Rescheduled', 'Cancelled'].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      ),
    },
  ];

  const fields = [
    { name: 'candidate_id', label: 'Candidate', type: 'select', required: true, options: candidates.map((c) => ({ value: c.id, label: c.name })) },
    { name: 'round', label: 'Round', placeholder: 'Round 1' },
    { name: 'scheduled_date', label: 'Scheduled Date/Time', type: 'datetime-local', required: true },
    { name: 'interviewer', label: 'Interviewer' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Interviews</h1>
        <button className="btn-primary" onClick={() => setShowAdd(true)}>Schedule Interview</button>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={interviews} />
      <Modal isOpen={showAdd} title="Schedule Interview" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Schedule" />
      </Modal>
    </div>
  );
}

export default InterviewsPage;
