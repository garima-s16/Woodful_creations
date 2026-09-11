// Recruitment pages: candidates list/detail and interviews.
// Combines the former CandidatesPage.jsx, CandidateDetailPage.jsx,
// and InterviewsPage.jsx.
import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { candidatesAPI, interviewsAPI } from '../../../utils/api';
import { Alert, Card, ConfirmDialog, Form, Modal, Table } from '../../../components/common/UI';
import { classifyLoadError, statusClass } from '../../../utils/utils';

// --- CandidatesPage.jsx ---
function CandidatesPage() {
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const navigate = useNavigate();
  const [candidates, setCandidates] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = () => {
    setPageLoading(true);
    setLoadError(false);
    candidatesAPI.list().then((res) => setCandidates(res.data)).catch((err) => {
      setLoadError(true);
      setError(err.response?.status === 403 ? 'You do not have permission to view candidates.' : 'Unable to load candidates. Please try again.');
    }).finally(() => setPageLoading(false));
  };
  useEffect(() => {
    load();
  }, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await candidatesAPI.create(formData);
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add candidate');
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = async (id, status) => {
    try {
      await candidatesAPI.update(id, { status });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update status');
    }
  };

  const columns = [
    { key: 'name', label: 'Name' }, { key: 'position', label: 'Position' },
    { key: 'phone', label: 'Phone' }, { key: 'email', label: 'Email' }, { key: 'experience', label: 'Experience' },
    {
      key: 'status', label: 'Status', render: (v, row) => (
        <select value={v} onClick={(e) => e.stopPropagation()} onChange={(e) => handleStatusChange(row.id, e.target.value)}>
          {['Applied', 'Shortlisted', 'Selected', 'Rejected'].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      ),
    },
  ];

  const fields = [
    { name: 'name', label: 'Name', required: true },
    { name: 'position', label: 'Position' },
    { name: 'phone', label: 'Phone' },
    { name: 'experience', label: 'Experience', advanced: true },
    { name: 'email', label: 'Email', type: 'email', advanced: true },
    { name: 'resume_url', label: 'Resume Link (optional - or upload a file after creating)', advanced: true },
    { name: 'remarks', label: 'Remarks', type: 'textarea', advanced: true },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Candidates</h1>
          <p className="page-summary">Track applicants through the hiring pipeline, from application to offer.</p>
        </div>
        {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Candidate</button>}
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={candidates} loading={pageLoading} error={loadError} onRetry={load} onRowClick={(row) => navigate(`/candidates/${row.id}`)} emptyMessage="No candidates yet. Add your first candidate to start the hiring pipeline." emptyAction={isPrivileged ? { label: 'Add Candidate', onClick: () => setShowAdd(true) } : undefined} />
      <Modal isOpen={showAdd} title="Add Candidate" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Add Candidate" />
      </Modal>
    </div>
  );
}

// --- CandidateDetailPage.jsx ---
function CandidateDetailPage() {
  const { candidateId } = useParams();
  const { user } = useSelector((state) => state.auth);
  const isStrictlyMaster = user?.role === 'master';
  const [candidate, setCandidate] = useState(null);
  const [interviews, setInterviews] = useState([]);
  const [showSchedule, setShowSchedule] = useState(false);
  const [loading, setLoading] = useState(false);
  const [uploadingResume, setUploadingResume] = useState(false);
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState(null);

  const load = useCallback(() => {
    setLoadError(null);
    candidatesAPI.get(candidateId).then((res) => setCandidate(res.data)).catch((err) => setLoadError(classifyLoadError(err, 'candidate')));
    interviewsAPI.list({ candidate_id: candidateId }).then((res) => setInterviews(res.data)).catch(() => setInterviews([]));
  }, [candidateId]);

  useEffect(load, [load]);

  const handleResumeFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploadingResume(true);
    setError('');
    try {
      await candidatesAPI.uploadResume(candidateId, file);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to upload resume');
    } finally {
      setUploadingResume(false);
      e.target.value = '';
    }
  };

  const [confirmingResumeDelete, setConfirmingResumeDelete] = useState(false);
  const [deletingResume, setDeletingResume] = useState(false);
  const handleDeleteResume = () => setConfirmingResumeDelete(true);
  const confirmDeleteResume = async () => {
    setDeletingResume(true);
    try {
      await candidatesAPI.deleteResume(candidateId);
      setConfirmingResumeDelete(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to remove resume');
      setConfirmingResumeDelete(false);
    } finally {
      setDeletingResume(false);
    }
  };

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

  if (loadError) return (
    <div className="page">
      <Alert type="error" message={loadError.message} />
      {!loadError.isNotFound && (
        <button type="button" className="btn-secondary" style={{ marginTop: 'var(--space-4)' }} onClick={load}>Retry</button>
      )}
    </div>
  );
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
              <div className="detail-meta-item"><span className="detail-meta-label">Email</span><span className="detail-meta-value">{candidate.email ? <a href={`mailto:${candidate.email}`}>{candidate.email}</a> : '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Phone</span><span className="detail-meta-value">{candidate.phone ? <a href={`tel:${candidate.phone}`}>{candidate.phone}</a> : '-'}</span></div>
              <div className="detail-meta-item"><span className="detail-meta-label">Experience</span><span className="detail-meta-value">{candidate.experience || '-'}</span></div>
              <div className="detail-meta-item">
                <span className="detail-meta-label">Resume</span>
                <span className="detail-meta-value">
                  {candidate.resume_original_filename ? (
                    <>
                      <a href={candidatesAPI.resumeDownloadUrl(candidateId)} target="_blank" rel="noreferrer">
                        {candidate.resume_original_filename}
                      </a>
                      {' '}
                      {isStrictlyMaster && <button className="btn-link" onClick={handleDeleteResume}>Remove</button>}
                    </>
                  ) : candidate.resume_url ? (
                    <a href={candidate.resume_url} target="_blank" rel="noreferrer">View Resume</a>
                  ) : '-'}
                  <br />
                  <label className="btn-link" style={{ cursor: 'pointer' }}>
                    {uploadingResume ? 'Uploading...' : (candidate.resume_original_filename ? 'Replace Resume' : 'Upload Resume')}
                    <input
                      type="file" accept=".pdf,.doc,.docx" style={{ display: 'none' }}
                      onChange={handleResumeFileChange} disabled={uploadingResume}
                    />
                  </label>
                </span>
              </div>
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

      <ConfirmDialog
        isOpen={confirmingResumeDelete}
        message="Remove this candidate's resume? This cannot be undone."
        onConfirm={confirmDeleteResume}
        onCancel={() => setConfirmingResumeDelete(false)}
        loading={deletingResume}
      />
    </div>
  );
}

// --- InterviewsPage.jsx ---
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

export { CandidatesPage, CandidateDetailPage, InterviewsPage };
