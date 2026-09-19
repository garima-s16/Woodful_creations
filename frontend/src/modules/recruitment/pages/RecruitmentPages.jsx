// Recruitment pages: candidates workspace and interviews. Combines
// the former CandidatesPage.jsx, CandidateDetailPage.jsx, and
// InterviewsPage.jsx.
//
// CandidatesPage below is rebuilt on the finalized Orders/Clients/
// Suppliers/Employees command-center workspace as the visual master
// (KPI strip / toolbar / 4 summary cards / 68-32 list+detail grid /
// 3-zone detail panel) - see OrdersPage (../../sales/pages/SalesListPages.jsx),
// ClientsPage (../../clients/pages/ClientPages.jsx), SuppliersPage
// (../../procurement/pages/ProcurementPages.jsx) for the reference
// implementation this mirrors. Reuses the exact same CSS classes
// (kpi-strip/orders-workspace-*/order-detail-*) - shared workspace-
// layout primitives, not Orders-specific styling. CandidateDetailPage's
// former standalone-route functionality (profile/resume/interview
// history/schedule interview) now lives inside the workspace's
// right-hand inspector panel. InterviewsPage and RecruitmentHub below
// are UNTOUCHED - Interviews stays exactly as it was.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { candidatesAPI, interviewsAPI } from '../../../utils/api';
import { Alert, Card, ConfirmDialog, Form, KpiStrip, Modal, Pagination, Table } from '../../../components/common/UI';
import { classifyLoadError, statusClass } from '../../../utils/utils';
import { CandidateIcon, CheckCircleIcon, TaskIcon, AttendanceIcon, PrinterIcon } from '../../../components/icons';

// --- CandidatesPage.jsx ---
const PAGE_SIZE = 25;
const CANDIDATE_STATUSES = ['Applied', 'Shortlisted', 'Selected', 'Rejected'];

function CandidatesPage() {
  // Route compatibility: /candidates/:candidateId (the former
  // standalone CandidateDetailPage route) now renders this same
  // workspace with that candidate pre-selected, instead of a separate
  // detail screen.
  const { candidateId: routeCandidateId } = useParams();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  // workspace holds the one bounded GET /api/candidates/workspace
  // response: { summary, candidates: {items,total_count,limit,offset},
  // selected_candidate }.
  const [workspace, setWorkspace] = useState(null);
  const [selectedCandidateId, setSelectedCandidateId] = useState(routeCandidateId ? Number(routeCandidateId) : null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');
  const location = useLocation();
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const activeFilters = () => {
    const params = {};
    if (statusFilter) params.status = statusFilter;
    if (search) params.search = search;
    return params;
  };

  const activeFiltersRef = useRef(activeFilters);
  activeFiltersRef.current = activeFilters;
  const selectedCandidateIdRef = useRef(selectedCandidateId);
  selectedCandidateIdRef.current = selectedCandidateId;

  const load = useCallback((filterParams, pageNum = 1) => {
    const offset = (pageNum - 1) * PAGE_SIZE;
    setPageLoading(true);
    setLoadError(false);
    candidatesAPI.workspace({
      ...filterParams, limit: PAGE_SIZE, offset,
      selected_candidate_id: selectedCandidateIdRef.current || undefined,
    }).then((res) => {
      setWorkspace(res.data);
      if (res.data.selected_candidate) setSelectedCandidateId(res.data.selected_candidate.id);
    }).catch((err) => {
      setLoadError(true);
      setError(err.response?.status === 403 ? 'You do not have permission to view candidates.' : 'Unable to load candidates. Please try again.');
    }).finally(() => setPageLoading(false));
  }, []);

  useEffect(() => {
    load(activeFiltersRef.current());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  useEffect(() => {
    if (!pageLoading && workspace && !selectedCandidateId && workspace.candidates?.items?.length) {
      handleSelectCandidate(workspace.candidates.items[0].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageLoading, workspace]);

  const handleSelectCandidate = (candidateIdVal) => {
    if (candidateIdVal === selectedCandidateId && workspace?.selected_candidate) return;
    setSelectedCandidateId(candidateIdVal);
    setDetailLoading(true);
    candidatesAPI.workspace({ selected_candidate_id: candidateIdVal, detail_only: true }).then((res) => {
      setWorkspace((prev) => (prev ? { ...prev, selected_candidate: res.data.selected_candidate } : prev));
    }).catch(() => {}).finally(() => setDetailLoading(false));
  };

  const applyFilters = (nextStatus, nextSearch) => {
    const params = {};
    if (nextStatus) params.status = nextStatus;
    if (nextSearch) params.search = nextSearch;
    setPage(1);
    load(params, 1);
  };

  const handleSearch = (e) => {
    e.preventDefault();
    applyFilters(statusFilter, search);
  };

  const handleStatusTab = (nextStatus) => {
    setStatusFilter(nextStatus);
    applyFilters(nextStatus, search);
  };

  const goToPage = (pageNum) => {
    setPage(pageNum);
    load(activeFilters(), pageNum);
  };

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await candidatesAPI.create(formData);
      setShowAdd(false);
      setSuccess('Candidate added.');
      load(activeFilters(), page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add candidate');
    } finally {
      setLoading(false);
    }
  };

  const refreshSelected = () => {
    if (!selectedCandidateId) return;
    candidatesAPI.workspace({ selected_candidate_id: selectedCandidateId, detail_only: true }).then((res) => {
      setWorkspace((prev) => (prev ? { ...prev, selected_candidate: res.data.selected_candidate } : prev));
    }).catch(() => {});
  };

  const handleStatusChange = async (id, status) => {
    try {
      await candidatesAPI.update(id, { status });
      load(activeFilters(), page);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update status');
    }
  };

  const fields = [
    { name: 'name', label: 'Name', required: true },
    { name: 'position', label: 'Position' },
    { name: 'phone', label: 'Phone' },
    { name: 'experience', label: 'Experience', advanced: true },
    { name: 'email', label: 'Email', type: 'email', advanced: true },
    { name: 'resume_url', label: 'Resume Link (optional - or upload a file after creating)', advanced: true },
    { name: 'remarks', label: 'Remarks', type: 'textarea', advanced: true },
  ];

  const summary = workspace?.summary || null;
  const candidateRows = workspace?.candidates?.items || [];
  const totalCount = workspace?.candidates?.total_count || 0;
  const offsetStart = workspace?.candidates?.offset ?? (page - 1) * PAGE_SIZE;
  const selected = workspace?.selected_candidate || null;

  const statusTabs = [{ value: '', label: 'All' }, ...CANDIDATE_STATUSES.map((s) => ({ value: s, label: s }))];

  // 4 KPI chips, all sourced from workspace.summary - real counts only.
  const kpiItems = summary ? [
    { label: 'Total Candidates', value: summary.total_candidates, icon: CandidateIcon },
    { label: 'Applied', value: summary.applied_count, icon: TaskIcon },
    { label: 'Shortlisted', value: summary.shortlisted_count, icon: AttendanceIcon },
    { label: 'Selected / Hiring', value: summary.selected_count, icon: CheckCircleIcon, tone: 'success' },
  ] : [];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>
            Candidates
            {summary && <span className="home-card-chip" style={{ marginLeft: 10, verticalAlign: 'middle' }}>{summary.total_candidates} Candidates</span>}
          </h1>
          <p className="page-summary">Track applicants through the hiring pipeline, from application to offer.</p>
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

      {summary && <KpiStrip items={kpiItems} />}

      {isPrivileged && (
        <div className="orders-workspace-toolbar">
          <button className="btn-primary" onClick={() => setShowAdd(true)}>+ New Candidate</button>
        </div>
      )}

      <div className="orders-summary-cards">
        <Card className="home-card home-card-flush">
          <div className="home-card-header">
            <span className="home-card-title">Candidate Overview</span>
            {summary && <span className="home-card-chip">{summary.overview.total_candidates} Total</span>}
          </div>
          {summary ? (
            <div className="orders-card-body">
              {summary.overview.status_breakdown.map((s) => (
                <div className="orders-card-stat-row" key={s.status}><span>{s.status}</span><strong>{s.count}</strong></div>
              ))}
            </div>
          ) : <div className="simple-chart-empty">Loading...</div>}
        </Card>

        <Card className="home-card home-card-flush">
          <div className="home-card-header">
            <span className="home-card-title">Hiring Pipeline</span>
          </div>
          {summary ? (
            <div className="orders-card-body">
              <div className="orders-card-hero">
                <span className="orders-card-hero-number">{summary.hiring_pipeline.applied}</span>
                <span className="orders-card-hero-caption">Applied</span>
              </div>
              <div className="orders-card-footer-row"><span>Shortlisted</span><strong>{summary.hiring_pipeline.shortlisted}</strong></div>
              <div className="orders-card-footer-row"><span>Selected</span><strong>{summary.hiring_pipeline.selected}</strong></div>
            </div>
          ) : <div className="simple-chart-empty">Loading...</div>}
        </Card>

        <Card className="home-card home-card-flush">
          <div className="home-card-header">
            <span className="home-card-title">Interview Activity</span>
          </div>
          {summary ? (
            <div className="orders-card-body">
              <div className="orders-card-hero">
                <span className="orders-card-hero-number">{summary.interview_activity.total_interviews}</span>
                <span className="orders-card-hero-caption">Total Interviews</span>
              </div>
              <div className="orders-card-footer-row"><span>Upcoming</span><strong>{summary.interview_activity.upcoming_interviews}</strong></div>
              <div className="orders-card-footer-row"><span>Completed</span><strong>{summary.interview_activity.completed_interviews}</strong></div>
            </div>
          ) : <div className="simple-chart-empty">Loading...</div>}
        </Card>

        <Card className="home-card home-card-flush">
          <div className="home-card-header">
            <span className="home-card-title">Hiring Status</span>
          </div>
          {summary ? (
            <div className="orders-card-body">
              <div className="order-health-chips">
                <div className="order-health-chip order-health-success">
                  <span className="order-health-count">{summary.hiring_status.selected_count}</span>
                  <span className="order-health-label">Selected</span>
                </div>
                <div className="order-health-chip order-health-danger">
                  <span className="order-health-count">{summary.hiring_status.rejected_count}</span>
                  <span className="order-health-label">Rejected</span>
                </div>
              </div>
            </div>
          ) : <div className="simple-chart-empty">Loading...</div>}
        </Card>
      </div>

      <div className="orders-workspace-grid">
        {/* All Candidates - 68%, compact table, sticky header, internal
            scroll, row click selects (never navigates). */}
        <div className="card orders-workspace-panel">
          <div className="orders-panel-header">
            <div className="orders-panel-title">
              <h3>All Candidates</h3>
              <div className="orders-panel-tabs">
                {statusTabs.map((t) => (
                  <button
                    key={t.label} type="button"
                    className={`orders-panel-tab ${statusFilter === t.value ? 'active' : ''}`}
                    onClick={() => handleStatusTab(t.value)}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
            <span className="home-card-caption">{totalCount} total</span>
          </div>
          <form
            className="page-search"
            onSubmit={handleSearch}
            style={{ maxWidth: 'none', flexWrap: 'wrap', padding: 'var(--space-3) var(--space-4)', margin: 0, borderBottom: '1px solid var(--border-subtle)' }}
          >
            <input
              type="text" placeholder="Search by name, email, phone, position, or ID..." value={search}
              onChange={(e) => setSearch(e.target.value)} className="form-input"
            />
            <button type="submit" className="btn-secondary">Search</button>
          </form>
          <div className="orders-table-scroll">
            {loadError ? (
              <div className="simple-chart-empty">
                Failed to load candidates. <button className="btn-link" onClick={() => load(activeFilters(), page)}>Retry</button>
              </div>
            ) : pageLoading ? (
              <div className="simple-chart-empty">Loading candidates...</div>
            ) : candidateRows.length === 0 ? (
              <div className="simple-chart-empty">
                No candidates yet.
                {isPrivileged && <><br /><button className="btn-link" onClick={() => setShowAdd(true)}>Add your first candidate</button></>}
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Candidate ID</th><th>Name</th><th>Position</th><th>Phone</th>
                    <th>Email</th><th>Experience</th><th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {candidateRows.map((row) => (
                    <tr
                      key={row.id}
                      className={`clickable ${row.id === selectedCandidateId ? 'orders-row-selected' : ''}`}
                      tabIndex={0}
                      role="button"
                      onClick={() => handleSelectCandidate(row.id)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSelectCandidate(row.id); } }}
                    >
                      <td><span className="business-id-badge">{row.business_id || '-'}</span></td>
                      <td>{row.name}</td>
                      <td>{row.position || '-'}</td>
                      <td>{row.phone || '-'}</td>
                      <td>{row.email || '-'}</td>
                      <td>{row.experience || '-'}</td>
                      <td>
                        <select
                          value={row.status} onClick={(e) => e.stopPropagation()}
                          onChange={(e) => handleStatusChange(row.id, e.target.value)}
                        >
                          {CANDIDATE_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="orders-panel-footer">
            <span>{candidateRows.length ? `Showing ${offsetStart + 1}-${offsetStart + candidateRows.length} of ${totalCount}` : `${totalCount} candidates`}</span>
            {totalCount > PAGE_SIZE && (
              <Pagination currentPage={page} totalPages={Math.ceil(totalCount / PAGE_SIZE)} onPageChange={goToPage} />
            )}
          </div>
        </div>

        {/* Candidate Details - 32%, three fixed/scroll/fixed zones. */}
        <div className="card orders-workspace-panel">
          <div className="orders-panel-header">
            <div className="orders-panel-title"><h3>Candidate Details</h3></div>
          </div>
          {!selected ? (
            <div className="order-detail-empty">
              {detailLoading ? 'Loading...' : 'Select a candidate from the list to see their details.'}
            </div>
          ) : (
            <CandidateInspectorBody
              key={selected.id}
              candidateId={selected.id}
              selected={selected}
              isPrivileged={isPrivileged}
              onStatusChange={(status) => handleStatusChange(selected.id, status)}
              onChanged={refreshSelected}
            />
          )}
        </div>
      </div>

      <Modal isOpen={showAdd} title="Add Candidate" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Add Candidate" />
      </Modal>
    </div>
  );
}

// --- CandidateInspectorBody (formerly the standalone CandidateDetailPage.jsx) ---
// Preserves ALL of CandidateDetailPage's former functionality - resume
// upload/replace/delete/download, status editing, and Schedule
// Interview (still calling interviewsAPI.create(), no new interview
// backend) - now rendered inside the workspace's inspector panel
// instead of a standalone page.
function CandidateInspectorBody({ candidateId, selected, isPrivileged, onStatusChange, onChanged }) {
  // Interview history comes straight from selected.interviews - the
  // workspace's own detail_only payload (see
  // _build_workspace_selected_candidate in recruitment/module.py),
  // read directly from the existing Interview table via candidate_id.
  // onChanged() (a detail_only re-fetch) is what refreshes it after a
  // schedule/resume change - never a second, separate interview fetch
  // here.
  const [showSchedule, setShowSchedule] = useState(false);
  const [loading, setLoading] = useState(false);
  const [uploadingResume, setUploadingResume] = useState(false);
  const [error, setError] = useState('');

  const handleResumeFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploadingResume(true);
    setError('');
    try {
      await candidatesAPI.uploadResume(candidateId, file);
      onChanged();
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
      onChanged();
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
      onChanged();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to schedule interview');
    } finally {
      setLoading(false);
    }
  };

  const resume = selected.resume || {};

  return (
    <>
      <div className="order-detail-top">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <h3 style={{ margin: 0 }}>{selected.name}</h3>
          <button type="button" className="order-detail-icon-btn" title="Print" onClick={() => window.print()}>
            <PrinterIcon />
          </button>
        </div>
        <div className="order-detail-top-meta" style={{ marginTop: 6 }}>
          <span className="business-id-badge">{selected.business_id}</span>
          <span className={`status-badge status-badge-dot ${statusClass(selected.profile.status)}`}>{selected.profile.status}</span>
          {isPrivileged && <button className="btn-link" onClick={() => setShowSchedule(true)}>Schedule Interview</button>}
        </div>
      </div>

      <div className="order-detail-scroll">
        {error && <Alert type="error" message={error} onClose={() => setError('')} />}

        <div>
          <div className="order-detail-section-label">Candidate Profile</div>
          <div className="order-detail-row"><span>Position</span><strong>{selected.profile.position || 'Not specified'}</strong></div>
          <div className="order-detail-row"><span>Email</span><strong>{selected.profile.email || '-'}</strong></div>
          <div className="order-detail-row"><span>Phone</span><strong>{selected.profile.phone || '-'}</strong></div>
          <div className="order-detail-row"><span>Experience</span><strong>{selected.profile.experience || '-'}</strong></div>
          <div className="order-detail-row"><span>Status</span><strong>{selected.profile.status}</strong></div>
          {isPrivileged && (
            <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {CANDIDATE_STATUSES.map((s) => (
                <button key={s} className={selected.profile.status === s ? 'btn-primary' : 'btn-secondary'} onClick={() => onStatusChange(s)}>{s}</button>
              ))}
            </div>
          )}
        </div>

        <div>
          <div className="order-detail-section-label">Resume</div>
          <div className="order-detail-row">
            <span>File</span>
            <strong>
              {resume.resume_original_filename ? (
                <>
                  <a href={candidatesAPI.resumeDownloadUrl(candidateId)} target="_blank" rel="noreferrer">{resume.resume_original_filename}</a>
                  {' '}
                  {isPrivileged && <button className="btn-link" onClick={handleDeleteResume}>Remove</button>}
                </>
              ) : resume.resume_url ? (
                <a href={resume.resume_url} target="_blank" rel="noreferrer">View Resume Link</a>
              ) : 'No resume on file'}
            </strong>
          </div>
          {isPrivileged && (
            <div className="order-detail-row">
              <label className="btn-link" style={{ cursor: 'pointer' }}>
                {uploadingResume ? 'Uploading...' : (resume.resume_original_filename ? 'Replace Resume' : 'Upload Resume')}
                <input
                  type="file" accept=".pdf,.doc,.docx" style={{ display: 'none' }}
                  onChange={handleResumeFileChange} disabled={uploadingResume}
                />
              </label>
            </div>
          )}
        </div>

        <div>
          <div className="order-detail-section-label">Interview History ({selected.interview_count ?? (selected.interviews || []).length})</div>
          {(selected.interviews || []).length === 0 ? (
            <div className="order-detail-row"><span>No interviews scheduled for this candidate yet.</span></div>
          ) : (selected.interviews || []).map((i) => (
            <div className="order-detail-item-row" key={i.id}>
              <span>{i.round || 'Interview'} &middot; {new Date(i.scheduled_date).toLocaleString()}</span>
              <span><span className={`status-badge ${statusClass(i.status)}`}>{i.status}</span></span>
            </div>
          ))}
        </div>

        {selected.remarks && (
          <div>
            <div className="order-detail-section-label">Notes / Remarks</div>
            <div className="order-detail-row"><span>{selected.remarks}</span></div>
          </div>
        )}
      </div>

      <div className="order-detail-bottom">
        {isPrivileged && <button className="btn-primary" style={{ flex: 1 }} onClick={() => setShowSchedule(true)}>Schedule Interview</button>}
      </div>

      <Modal isOpen={showSchedule} title="Schedule Interview" onClose={() => setShowSchedule(false)}>
        {error && <Alert type="error" message={error} onClose={() => setError('')} />}
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
    </>
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

// --- RecruitmentHub.jsx ---
// Woodful navigation/module-structure consolidation: Candidates and
// Interviews used to be two separate primary Sidebar destinations.
// They are now one "Recruitment" workspace reached from a single nav
// item (/recruitment) - a thin tab switcher over the exact same two
// page components above (same components, same API calls, same
// role-gating; only the selected tab is mounted, so no duplicate
// network traffic). /candidates, /candidates/:id, and /interviews
// keep working exactly as before.
const RECRUITMENT_TABS = ['Candidates', 'Interviews'];

function RecruitmentHub() {
  const [tab, setTab] = useState('Candidates');
  return (
    <div className="page recruitment-hub">
      <div className="page-header">
        <div>
          <h1>Recruitment</h1>
          <p className="page-summary">Candidates and their interviews in one place.</p>
        </div>
      </div>
      <div className="tab-bar">
        {RECRUITMENT_TABS.map((t) => (
          <button key={t} className={tab === t ? 'tab active' : 'tab'} onClick={() => setTab(t)} type="button">{t}</button>
        ))}
      </div>
      {tab === 'Candidates' && <CandidatesPage />}
      {tab === 'Interviews' && <InterviewsPage />}
    </div>
  );
}

export { CandidatesPage, InterviewsPage, RecruitmentHub };
