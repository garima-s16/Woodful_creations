import React, { useEffect, useState, useCallback } from 'react';
import { locationsAPI } from '../utils/api';
import Card from '../components/common/Card';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import '../styles/components/LocationTree.css';

function LocationNode({ node, onAddChild }) {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = node.children && node.children.length > 0;

  return (
    <li className="location-node">
      <div className="location-node-row">
        {hasChildren ? (
          <button className="location-node-toggle" onClick={() => setExpanded((e) => !e)} aria-label={expanded ? 'Collapse' : 'Expand'}>
            {expanded ? '\u2212' : '+'}
          </button>
        ) : <span className="location-node-toggle-spacer" />}
        <span className="location-node-name">{node.name}</span>
        {node.location_type && <span className="location-node-type">{node.location_type}</span>}
        {node.business_id && <span className="business-id-badge">{node.business_id}</span>}
        <button className="btn-link" onClick={() => onAddChild(node)}>+ Add here</button>
      </div>
      {hasChildren && expanded && (
        <ul className="location-node-children">
          {node.children.map((child) => (
            <LocationNode key={child.id} node={child} onAddChild={onAddChild} />
          ))}
        </ul>
      )}
    </li>
  );
}

function LocationsPage() {
  const [tree, setTree] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [parentForNew, setParentForNew] = useState(null); // null = top-level (new Warehouse)
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    locationsAPI.tree().then((res) => setTree(res.data)).catch(() => setError('Unable to load locations.'));
  }, []);

  useEffect(load, [load]);

  const handleAddChild = (node) => {
    setParentForNew(node);
    setShowAdd(true);
  };

  const handleAddTopLevel = () => {
    setParentForNew(null);
    setShowAdd(true);
  };

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await locationsAPI.create({
        name: formData.name, location_type: formData.location_type || null,
        parent_id: parentForNew ? parentForNew.id : null,
      });
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create location');
    } finally {
      setLoading(false);
    }
  };

  const fields = [
    { name: 'name', label: 'Name', required: true, placeholder: parentForNew ? 'e.g. Rack A2' : 'e.g. Main Warehouse' },
    { name: 'location_type', label: 'Type (optional)', placeholder: 'Warehouse / Area / Rack / Bin' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Locations</h1>
          <p className="page-summary">
            Where materials are actually stored - a flexible tree (Warehouse &rarr; Area &rarr; Rack &rarr; Bin,
            or as many/few levels as your business needs). Create your own structure; nothing here is fixed.
          </p>
        </div>
        <button className="btn-primary" onClick={handleAddTopLevel}>+ New Top-Level Location</button>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      <Card>
        {tree.length === 0 ? (
          <div className="card-body" style={{ color: 'var(--text-secondary)' }}>
            No locations yet. Create your first top-level location (e.g. a warehouse) to get started.
          </div>
        ) : (
          <ul className="location-tree-root">
            {tree.map((node) => (
              <LocationNode key={node.id} node={node} onAddChild={handleAddChild} />
            ))}
          </ul>
        )}
      </Card>

      <Modal
        isOpen={showAdd}
        title={parentForNew ? `New location under "${parentForNew.name}"` : 'New Top-Level Location'}
        onClose={() => setShowAdd(false)}
      >
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Create Location" />
      </Modal>
    </div>
  );
}

export default LocationsPage;
