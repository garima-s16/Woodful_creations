import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { candidatesAPI, interviewsAPI } from '../../../utils/api';
import Table from '../../../components/common/Table';
import Card from '../../../components/common/Card';
import Modal from '../../../components/common/Modal';
import ConfirmDialog from '../../../components/common/ConfirmDialog';
import Form from '../../../components/common/Form';
import Alert from '../../../components/common/Alert';
import { statusClass } from '../../../utils/format';
import { classifyLoadError } from '../../../utils/loadError';

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

export default CandidateDetailPage;
