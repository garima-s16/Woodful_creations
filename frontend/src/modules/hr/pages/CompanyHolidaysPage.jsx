import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { holidaysAPI, reportsAPI } from '../../../utils/api';
import Card from '../../../components/common/Card';
import Alert from '../../../components/common/Alert';
import Modal from '../../../components/common/Modal';
import Form from '../../../components/common/Form';
import ConfirmDialog from '../../../components/common/ConfirmDialog';

function CompanyHolidaysPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';

  const [holidays, setHolidays] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingHoliday, setEditingHoliday] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [yearFilter, setYearFilter] = useState('all');
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    holidaysAPI.list()
      .then((res) => setHolidays(res.data))
      .catch(() => setError('Could not load holidays.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleSave = async (formData) => {
    setSaving(true);
    setError('');
    try {
      const payload = {
        date: formData.date, name: formData.name,
        is_working: formData.is_working === 'true' || formData.is_working === true,
        remarks: formData.remarks || null,
      };
      if (editingHoliday) {
        await holidaysAPI.update(editingHoliday.id, payload);
      } else {
        await holidaysAPI.create(payload);
      }
      setShowForm(false);
      setEditingHoliday(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not save this holiday.');
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await holidaysAPI.remove(pendingDelete.id);
      setPendingDelete(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not delete this holiday.');
      setPendingDelete(null);
    } finally {
      setDeleting(false);
    }
  };

  const years = [...new Set(holidays.map((h) => h.date.slice(0, 4)))].sort();
  const filteredHolidays = yearFilter === 'all' ? holidays : holidays.filter((h) => h.date.startsWith(yearFilter));

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Company Holidays</h1>
          <p className="page-summary">
            Holidays and special working days affect attendance and payroll calculations across every year - not just 2026.
          </p>
        </div>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl('company-holidays.xlsx')}>Export Excel</a>
          {isPrivileged && (
            <button className="btn-secondary" onClick={() => navigate('/company-holidays/import')}>Import Excel</button>
          )}
          {isPrivileged && (
            <button className="btn-primary" onClick={() => { setEditingHoliday(null); setShowForm(true); }}>Add Holiday</button>
          )}
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      {years.length > 1 && (
        <div style={{ marginBottom: 16 }}>
          <select className="form-input" style={{ maxWidth: 160 }} value={yearFilter} onChange={(e) => setYearFilter(e.target.value)}>
            <option value="all">All Years</option>
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
      )}

      {loading ? (
        <p>Loading...</p>
      ) : filteredHolidays.length === 0 && !error ? (
        <Card><div className="card-body">No holidays recorded yet.</div></Card>
      ) : !error && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Date</th><th>Name</th><th>Type</th><th>Remarks</th>{isPrivileged && <th></th>}
            </tr>
          </thead>
          <tbody>
            {filteredHolidays.map((h) => (
              <tr key={h.id}>
                <td>{new Date(h.date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</td>
                <td>{h.name}</td>
                <td>
                  <span className={`status-badge ${h.is_working ? 'status-info' : 'status-gold'}`}>
                    {h.is_working ? 'Special Working Day' : 'Holiday'}
                  </span>
                </td>
                <td>{h.remarks || '-'}</td>
                {isPrivileged && (
                  <td>
                    <button className="btn-link" onClick={() => { setEditingHoliday(h); setShowForm(true); }}>Edit</button>
                    <button className="btn-link" onClick={() => setPendingDelete(h)}>Delete</button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <Modal isOpen={showForm} title={editingHoliday ? 'Edit Holiday' : 'Add Holiday'} onClose={() => { setShowForm(false); setEditingHoliday(null); }}>
        <Form
          fields={[
            { name: 'date', label: 'Date', type: 'date', required: true },
            { name: 'name', label: 'Holiday Name', required: true },
            { name: 'is_working', label: 'Type', type: 'select', required: true, options: [
              { value: 'false', label: 'Holiday' }, { value: 'true', label: 'Special Working Day' },
            ] },
            { name: 'remarks', label: 'Remarks', type: 'textarea' },
          ]}
          onSubmit={handleSave}
          loading={saving}
          submitText={editingHoliday ? 'Save Changes' : 'Add Holiday'}
          initialValues={editingHoliday ? {
            date: editingHoliday.date, name: editingHoliday.name,
            is_working: String(editingHoliday.is_working), remarks: editingHoliday.remarks || '',
          } : {}}
        />
      </Modal>

      <ConfirmDialog
        isOpen={!!pendingDelete}
        message={pendingDelete ? `Delete "${pendingDelete.name}" (${pendingDelete.date})? This cannot be undone.` : ''}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
        loading={deleting}
      />
    </div>
  );
}

export default CompanyHolidaysPage;
