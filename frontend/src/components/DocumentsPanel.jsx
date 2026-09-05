import React, { useEffect, useState } from 'react';
import Card from './common/Card';
import Alert from './common/Alert';

/**
 * api must provide: list(), upload(file, description), downloadUrl(documentId), remove(documentId)
 * - already bound to the specific parent, so this component itself never needs to know
 * which document API (generic vs client vs payment) or which parent_type/parent_id it's talking to.
 */
function DocumentsPanel({ title = 'Documents', api, canUpload = true }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [description, setDescription] = useState('');

  const load = () => {
    setLoading(true);
    setLoadError(false);
    api.list()
      .then((res) => setDocuments(res.data))
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    setError('');
    try {
      await api.upload(file, description);
      setDescription('');
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed.');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleDelete = async (documentId) => {
    if (!window.confirm('Remove this document?')) return;
    try {
      await api.remove(documentId);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not remove this document.');
    }
  };

  return (
    <Card title={title}>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {canUpload && (
        <div className="document-upload-row" style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-4)', alignItems: 'center' }}>
          <input
            type="text" placeholder="Description (optional)" value={description}
            onChange={(e) => setDescription(e.target.value)} className="form-input" style={{ flex: 1 }}
          />
          <label className="btn-secondary" style={{ cursor: uploading ? 'not-allowed' : 'pointer', opacity: uploading ? 0.6 : 1 }}>
            {uploading ? 'Uploading...' : 'Upload File'}
            <input type="file" onChange={handleFileChange} disabled={uploading} style={{ display: 'none' }} />
          </label>
        </div>
      )}
      {loading ? (
        <div className="card-body" style={{ color: 'var(--text-secondary)' }}>Loading...</div>
      ) : loadError ? (
        <div className="card-body" style={{ color: 'var(--text-secondary)' }}>
          Unable to load documents.{' '}
          <button type="button" className="btn-link" onClick={load}>Retry</button>
        </div>
      ) : documents.length === 0 ? (
        <div className="card-body" style={{ color: 'var(--text-secondary)' }}>No documents yet.</div>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
          {documents.map((doc) => (
            <li key={doc.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--space-2) 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <div>
                <a href={api.downloadUrl(doc.id)} target="_blank" rel="noreferrer">{doc.original_filename}</a>
                {doc.description && <span style={{ color: 'var(--text-secondary)', marginLeft: 'var(--space-2)' }}>- {doc.description}</span>}
              </div>
              {canUpload && (
                <button className="btn-secondary" onClick={() => handleDelete(doc.id)} style={{ fontSize: '0.8rem' }}>Remove</button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export default DocumentsPanel;
