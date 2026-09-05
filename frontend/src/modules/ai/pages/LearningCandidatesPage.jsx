import React, { useEffect, useState, useCallback } from 'react';
import { useSelector } from 'react-redux';
import { chatAPI } from '../../../utils/api';
import Table from '../../../components/common/Table';
import Alert from '../../../components/common/Alert';

const STATUS_TABS = ['pending', 'approved', 'rejected'];

function LearningCandidatesPage() {
  const { user } = useSelector((state) => state.auth);
  const isMaster = user?.role === 'master';
  const [status, setStatus] = useState('pending');
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [actioningId, setActioningId] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError('');
    chatAPI.learningCandidates(status)
      .then((res) => setCandidates(res.data.candidates))
      .catch(() => setError('Unable to load learning candidates. Please try again.'))
      .finally(() => setLoading(false));
  }, [status]);

  useEffect(() => { load(); }, [load]);

  const handleApprove = (id) => {
    setActioningId(id);
    chatAPI.approveLearningCandidate(id)
      .then(load)
      .catch(() => setError('Unable to approve this candidate. Please try again.'))
      .finally(() => setActioningId(null));
  };

  const handleReject = (id) => {
    setActioningId(id);
    chatAPI.rejectLearningCandidate(id)
      .then(load)
      .catch(() => setError('Unable to reject this candidate. Please try again.'))
      .finally(() => setActioningId(null));
  };

  if (!isMaster) {
    return <div className="page"><div className="card-body">Chatbot learning review is available to master accounts only.</div></div>;
  }

  const columns = [
    { key: 'phrase', label: 'Phrase' },
    { key: 'resolved_tool', label: 'Resolved To' },
    { key: 'occurrence_count', label: 'Seen' },
  ];
  if (status === 'pending') {
    columns.push({
      key: 'actions', label: '', render: (v, row) => (
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          <button className="btn-secondary" disabled={actioningId === row.id} onClick={() => handleApprove(row.id)}>Approve</button>
          <button className="btn-link" disabled={actioningId === row.id} onClick={() => handleReject(row.id)}>Reject</button>
        </div>
      ),
    });
  } else {
    columns.push({ key: 'reviewed_by', label: 'Reviewed By' });
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Chatbot Learning</h1>
          <p className="page-summary">
            Phrases Gemini has successfully interpreted where the deterministic chatbot could not.
            Approving a phrase lets Woodful answer it directly next time, without calling Gemini at all.
          </p>
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <div className="tab-bar">
        {STATUS_TABS.map((t) => (
          <button
            key={t}
            className={status === t ? 'tab active' : 'tab'}
            onClick={() => setStatus(t)}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      <Table columns={columns} data={candidates} loading={loading} emptyMessage="No candidates in this status." />
    </div>
  );
}

export default LearningCandidatesPage;
