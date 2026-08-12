import React, { useEffect, useState } from 'react';
import { auditLogsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Alert from '../components/common/Alert';

function AuditLogsPage() {
  const [logs, setLogs] = useState([]);
  const [moduleFilter, setModuleFilter] = useState('');
  const [error, setError] = useState('');
  const [pageLoading, setPageLoading] = useState(true);

  const load = (params) => {
    setPageLoading(true);
    auditLogsAPI.list(params).then((res) => setLogs(res.data)).catch(() => setError('You do not have permission to view audit logs.')).finally(() => setPageLoading(false));
  };
  useEffect(() => load(), []);

  const handleFilter = (e) => {
    e.preventDefault();
    load(moduleFilter ? { module_name: moduleFilter } : undefined);
  };

  const columns = [
    { key: 'created_at', label: 'Time', render: (v) => new Date(v).toLocaleString() },
    { key: 'action', label: 'Action' }, { key: 'module_name', label: 'Module' },
    { key: 'record_id', label: 'Record ID' }, { key: 'user_id', label: 'User ID' },
    { key: 'ip_address', label: 'IP Address' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Audit Logs</h1>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <form className="page-search" onSubmit={handleFilter}>
        <input
          type="text" placeholder="Filter by module (e.g. payments, users)..." value={moduleFilter}
          onChange={(e) => setModuleFilter(e.target.value)} className="form-input"
        />
        <button type="submit" className="btn-secondary">Filter</button>
      </form>
      <Table columns={columns} data={logs} loading={pageLoading} emptyMessage="No audit log entries found." />
    </div>
  );
}

export default AuditLogsPage;
