// Shared UI primitives: Alert, Card, Form, Modal, Pagination, Table,
// ConfirmDialog, KpiCard, MaterialCard, OrderLifecycle, SendEmailModal,
// and SimpleBarChart. Combines all former components/common/*.js(x) files.
import React, { useEffect, useId, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { formatCurrency, statusClass } from '../../utils/utils';
import { CartIcon, PlusIcon } from '../icons';
import '../../styles/components.css';

// --- Alert.js ---
const Alert = ({ type = 'info', message, onClose }) => {
  React.useEffect(() => {
    if (type !== 'error') {
      const timer = setTimeout(onClose, 5000);
      return () => clearTimeout(timer);
    }
  }, [type, onClose]);

  return (
    <div className={`alert alert-${type}`} role={type === 'error' ? 'alert' : 'status'}>
      <div className="alert-content">{message}</div>
      <button className="alert-close" onClick={onClose} aria-label="Dismiss">&times;</button>
    </div>
  );
};

// --- Card.js ---
const Card = ({ title, children, actions, className = '', ...rest }) => {
  return (
    <div className={`card ${className}`} {...rest}>
      {title && (
        <div className="card-header">
          <h3>{title}</h3>
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}
      <div className="card-body">{children}</div>
    </div>
  );
};

// --- Form.js ---
function FieldInput({ field, value, error, onChange, onBlur, formData }) {
  if (field.type === 'computed') {
    // Read-only, derived from other field values (e.g. leave days from
    // start/end date) - never user-editable, so it can never end up
    // 0/negative/out of sync with the dates it's computed from.
    return (
      <input
        type="text" id={field.name} name={field.name}
        value={field.compute ? field.compute(formData) : (value || '')}
        readOnly disabled
        className="form-input form-input-readonly"
      />
    );
  }
  if (field.type === 'textarea') {
    return (
      <textarea
        id={field.name} name={field.name} value={value || ''} onChange={onChange} onBlur={onBlur}
        placeholder={field.placeholder} rows={field.rows || 4}
        aria-required={field.required || undefined}
        className={`form-input ${error ? 'error' : ''}`}
      />
    );
  }
  if (field.type === 'select') {
    return (
      <select
        id={field.name} name={field.name} value={value || ''} onChange={onChange} onBlur={onBlur}
        aria-required={field.required || undefined}
        className={`form-input ${error ? 'error' : ''}`}
      >
        <option value="">Select {field.label}</option>
        {field.options?.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    );
  }
  return (
    <input
      type={field.type || 'text'} id={field.name} name={field.name} value={value || ''}
      onChange={onChange} onBlur={onBlur} placeholder={field.placeholder}
      // Without this, a plain <input type="number"> defaults to the
      // browser's own step=1 HTML5 validation, which silently blocks
      // submitting a decimal value (e.g. 2.5 kg) - the browser shows
      // its own "please enter a valid value" prompt and the form never
      // reaches the API at all. step="any" removes that restriction;
      // whole numbers remain just as valid as before.
      step={field.type === 'number' ? 'any' : undefined}
      aria-required={field.required || undefined}
      className={`form-input ${error ? 'error' : ''}`}
    />
  );
}

function FieldGroup({ field, formData, errors, handleChange, handleBlur }) {
  const label = field.getLabel ? field.getLabel(formData) : field.label;
  const hint = field.getHint ? field.getHint(formData) : field.hint;
  // textarea/computed fields (long free text, or a derived readout) stay
  // full-width even in the two-column grid below - everything else
  // (text/number/date/select) is short enough to comfortably pair up
  // with a neighbour on wide screens.
  const isFullWidth = field.type === 'textarea' || field.type === 'computed' || field.fullWidth;
  return (
    <div className={`form-group${isFullWidth ? ' form-group--full' : ''}`}>
      <label htmlFor={field.name} className="form-label">
        {label} {field.required && <span className="required">*</span>}
      </label>
      <FieldInput
        field={field} value={formData[field.name]} error={errors[field.name]}
        onChange={handleChange} onBlur={handleBlur(field)} formData={formData}
      />
      {hint && <span className="form-hint">{hint}</span>}
      {errors[field.name] && <span className="error-message">{errors[field.name]}</span>}
    </div>
  );
}

/**
 * fields: array of { name, label, type, required, options, placeholder, section }
 * If any field has a `section` property, the form renders as a multi-step
 * wizard (one section per step, with a final Review step) instead of one
 * long flat list. Omitting `section` on every field keeps the old flat
 * single-page behavior - fully backward compatible.
 */
const Form = React.forwardRef(({ fields, onSubmit, onFieldChange, loading = false, submitText = 'Submit', initialValues = {} }, ref) => {
  const [formData, setFormData] = React.useState(initialValues);
  const [errors, setErrors] = React.useState({});
  const [step, setStep] = React.useState(0);
  const [showAdvanced, setShowAdvanced] = React.useState(false);

  // Lets a parent push a value into the form programmatically - e.g. the
  // material creation form's "intelligent defaults" suggestion
  // filling in thickness_size when the user clicks Apply - without turning
  // every field into a parent-controlled input. Only ever invoked from an
  // explicit user action, never automatically, so it can't fight the user
  // while they're typing. Backward compatible: callers that don't pass a
  // ref are unaffected.
  React.useImperativeHandle(ref, () => ({
    setValue(name, value) {
      setFormData((prev) => ({ ...prev, [name]: value }));
      setErrors((prev) => (prev[name] ? { ...prev, [name]: '' } : prev));
    },
  }), []);

  React.useEffect(() => {
    setFormData(initialValues);
    setStep(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(initialValues)]);

  const isDirty = JSON.stringify(formData) !== JSON.stringify(initialValues);
  React.useEffect(() => {
    if (!isDirty) return undefined;
    const handleBeforeUnload = (e) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isDirty]);

  const sections = React.useMemo(() => {
    const hasSections = fields.some((f) => f.section);
    if (!hasSections) return null;
    const order = [];
    const map = {};
    fields.forEach((f) => {
      const s = f.section || 'Details';
      if (!map[s]) { map[s] = []; order.push(s); }
      map[s].push(f);
    });
    return order.map((name) => ({ name, fields: map[name] }));
  }, [fields]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: '' }));
    if (onFieldChange) onFieldChange(name, value);
  };

  const handleBlur = (field) => () => {
    const value = formData[field.name];
    if (field.visibleIf && !field.visibleIf(formData)) return;
    if (field.required && !value) {
      setErrors((prev) => ({ ...prev, [field.name]: `${field.label} is required` }));
      return;
    }
    if (field.validate && value) {
      const message = field.validate(value, formData);
      setErrors((prev) => ({ ...prev, [field.name]: message || '' }));
    }
  };

  const validate = (fieldsToCheck) => {
    const newErrors = {};
    fieldsToCheck.forEach((field) => {
      if (field.visibleIf && !field.visibleIf(formData)) return; // hidden fields aren't required
      const value = formData[field.name];
      if (field.required && !value) {
        newErrors[field.name] = `${field.label} is required`;
        return;
      }
      // A field-specific validator (e.g. GSTIN length/format) only
      // runs when the field actually has a value - required-ness is
      // handled above, so an optional empty field never fails a
      // format check meant for when it IS filled in.
      if (field.validate && value) {
        const message = field.validate(value, formData);
        if (message) newErrors[field.name] = message;
      }
    });
    return newErrors;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const newErrors = validate(fields);
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      if (!sections && fields.some((f) => f.advanced && newErrors[f.name])) {
        setShowAdvanced(true);
      }
      return;
    }
    onSubmit(formData);
  };

  if (!sections) {
    const visibleFields = fields.filter((field) => !field.visibleIf || field.visibleIf(formData));
    const primaryFields = visibleFields.filter((field) => !field.advanced);
    const advancedFields = visibleFields.filter((field) => field.advanced);
    return (
      <form className="form" onSubmit={handleSubmit}>
        {primaryFields.map((field) => (
          <FieldGroup key={field.name} field={field} formData={formData} errors={errors} handleChange={handleChange} handleBlur={handleBlur} />
        ))}
        {advancedFields.length > 0 && (
          <>
            <button
              type="button" className="form-advanced-toggle"
              onClick={() => setShowAdvanced((v) => !v)}
              aria-expanded={showAdvanced}
            >
              Additional information {showAdvanced ? '▲' : '▼'}
            </button>
            <AnimatePresence initial={false}>
              {showAdvanced && (
                <motion.div
                  className="form-advanced-section"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                  style={{ overflow: 'hidden' }}
                >
                  {advancedFields.map((field) => (
                    <FieldGroup key={field.name} field={field} formData={formData} errors={errors} handleChange={handleChange} handleBlur={handleBlur} />
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </>
        )}
        <button type="submit" className="btn-primary btn-submit" disabled={loading}>
          {loading ? 'Please wait...' : submitText}
        </button>
      </form>
    );
  }

  // Multi-step wizard, with a Review step appended at the end.
  const isReview = step === sections.length;
  const currentSection = sections[step];

  const goNext = () => {
    if (currentSection) {
      const newErrors = validate(currentSection.fields);
      if (Object.keys(newErrors).length > 0) {
        setErrors((prev) => ({ ...prev, ...newErrors }));
        return;
      }
    }
    setStep((s) => Math.min(s + 1, sections.length));
  };
  const goBack = () => setStep((s) => Math.max(s - 1, 0));

  return (
    <form className="form form-wizard" onSubmit={handleSubmit}>
      <div className="wizard-steps">
        {sections.map((s, i) => (
          <div key={s.name} className={`wizard-step ${i === step ? 'active' : ''} ${i < step ? 'done' : ''}`}>
            {i + 1}. {s.name}
          </div>
        ))}
        <div className={`wizard-step ${isReview ? 'active' : ''}`}>{sections.length + 1}. Review</div>
      </div>

      {!isReview && (
        <div className="wizard-panel">
          {currentSection.fields.filter((field) => !field.visibleIf || field.visibleIf(formData)).map((field) => (
            <FieldGroup key={field.name} field={field} formData={formData} errors={errors} handleChange={handleChange} handleBlur={handleBlur} />
          ))}
        </div>
      )}

      {isReview && (
        <div className="wizard-panel wizard-review">
          {sections.map((s) => (
            <div key={s.name} className="review-section">
              <h4>{s.name}</h4>
              {s.fields.filter((f) => !f.visibleIf || f.visibleIf(formData)).map((f) => (
                <div key={f.name} className="review-row">
                  <span className="review-label">{f.getLabel ? f.getLabel(formData) : f.label}</span>
                  <span className="review-value">
                    {f.type === 'select'
                      ? (f.options?.find((o) => String(o.value) === String(formData[f.name]))?.label || formData[f.name] || '-')
                      : (formData[f.name] || '-')}
                  </span>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      <div className="wizard-actions">
        {step > 0 && <button type="button" className="btn-secondary" onClick={goBack}>Back</button>}
        {!isReview && <button type="button" className="btn-primary" onClick={goNext}>Continue</button>}
        {isReview && (
          <button type="submit" className="btn-primary btn-submit" disabled={loading}>
            {loading ? 'Please wait...' : submitText}
          </button>
        )}
      </div>
    </form>
  );
});

// --- Modal.js ---
const Modal = ({ isOpen, title, children, onClose, size }) => {
  const contentRef = useRef(null);
  const previouslyFocusedRef = useRef(null);
  const titleId = useId();

  // Move focus into the modal on open, and back to whatever triggered it
  // on close - without this, keyboard/screen-reader users lose their
  // place in the page every time a modal opens or closes.
  useEffect(() => {
    if (!isOpen) return undefined;

    previouslyFocusedRef.current = document.activeElement;
    const firstFocusable = contentRef.current?.querySelector(
      'input, select, textarea, button, [href], [tabindex]:not([tabindex="-1"])'
    );
    (firstFocusable || contentRef.current)?.focus();

    return () => {
      previouslyFocusedRef.current?.focus?.();
    };
  }, [isOpen]);

  // ESC to close, and a simple Tab focus trap so keyboard focus can't
  // silently leave the modal into the (visually dimmed) page behind it.
  useEffect(() => {
    if (!isOpen) return undefined;

    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        onClose();
        return;
      }
      if (event.key === 'Tab' && contentRef.current) {
        const focusable = contentRef.current.querySelectorAll(
          'input, select, textarea, button, [href], [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="modal-overlay"
          onClick={onClose}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.16, ease: 'easeOut' }}
        >
          <motion.div
            className={`modal-content${size === 'wide' ? ' modal-content--wide' : ''}`}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            ref={contentRef}
            tabIndex={-1}
            onClick={(e) => e.stopPropagation()}
            initial={{ opacity: 0, y: 8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="modal-header">
              <h2 id={titleId}>{title}</h2>
              <button className="modal-close" onClick={onClose} aria-label="Close dialog">&times;</button>
            </div>
            <div className="modal-body">{children}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

// --- Pagination.js ---
const Pagination = ({ currentPage, totalPages, onPageChange, loading = false }) => {
  const pages = [];
  const maxPagesToShow = 5;
  const halfRange = Math.floor(maxPagesToShow / 2);

  let startPage = Math.max(1, currentPage - halfRange);
  let endPage = Math.min(totalPages, startPage + maxPagesToShow - 1);

  if (endPage - startPage + 1 < maxPagesToShow) {
    startPage = Math.max(1, endPage - maxPagesToShow + 1);
  }

  if (startPage > 1) {
    pages.push(
      <button key={1} onClick={() => onPageChange(1)} disabled={loading} className="page-btn">
        1
      </button>
    );
    if (startPage > 2) {
      pages.push(
        <span key="left-ellipsis" className="ellipsis">
          ...
        </span>
      );
    }
  }

  for (let i = startPage; i <= endPage; i++) {
    pages.push(
      <button
        key={i}
        onClick={() => onPageChange(i)}
        disabled={loading}
        className={`page-btn ${i === currentPage ? 'active' : ''}`}
      >
        {i}
      </button>
    );
  }

  if (endPage < totalPages) {
    if (endPage < totalPages - 1) {
      pages.push(
        <span key="right-ellipsis" className="ellipsis">
          ...
        </span>
      );
    }
    pages.push(
      <button key={totalPages} onClick={() => onPageChange(totalPages)} disabled={loading} className="page-btn">
        {totalPages}
      </button>
    );
  }

  return (
    <div className="pagination">
      <button
        onClick={() => onPageChange(Math.max(1, currentPage - 1))}
        disabled={currentPage === 1 || loading}
        className="page-btn prev"
      >
        Previous
      </button>
      {pages}
      <button
        onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
        disabled={currentPage === totalPages || loading}
        className="page-btn next"
      >
        Next
      </button>
    </div>
  );
};

// --- Table.js ---
const Table = ({ columns, data, loading, error, onRetry, onRowClick, emptyMessage = 'No records yet.', emptyAction }) => {
  const alignStyle = (col) => (col.align ? { textAlign: col.align } : undefined);

  if (loading) {
    return (
      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.key} scope="col" style={alignStyle(col)}>{col.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 5 }).map((_, rowIdx) => (
              <tr key={rowIdx} className="skeleton-row">
                {columns.map((col) => (
                  <td key={col.key}><span className="skeleton-bar" /></td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (error) {
    return (
      <div className="table-error">
        <p className="table-error-message">Unable to load this data. Please try again.</p>
        {onRetry && (
          <button type="button" className="btn-secondary table-error-retry" onClick={onRetry}>Retry</button>
        )}
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="table-empty">
        <p className="table-empty-message">{emptyMessage}</p>
        {emptyAction && (
          <button type="button" className="btn-primary table-empty-action" onClick={emptyAction.onClick}>
            {emptyAction.label}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="table-container">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} scope="col" style={alignStyle(col)}>{col.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, index) => (
            <tr
              key={row.id || index}
              onClick={() => onRowClick && onRowClick(row)}
              onKeyDown={(e) => {
                if (onRowClick && (e.key === 'Enter' || e.key === ' ')) {
                  e.preventDefault();
                  onRowClick(row);
                }
              }}
              className={onRowClick ? 'clickable' : ''}
              tabIndex={onRowClick ? 0 : undefined}
              role={onRowClick ? 'button' : undefined}
            >
              {columns.map((col) => (
                <td key={`${row.id}-${col.key}`} style={alignStyle(col)}>
                  {col.render ? col.render(row[col.key], row) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

// --- ConfirmDialog.jsx ---
/**
 * One reusable confirmation dialog for every destructive action in the
 * app (delete, remove, etc.) - built on the existing Modal component
 * so it inherits the same focus-trap/ESC-to-close/accessibility
 * handling, rather than every page implementing its own confirm logic
 * (e.g. window.confirm, which cannot be styled and does not match the
 * rest of the application).
 *
 * Usage: keep the "thing pending deletion" in state, render this with
 * isOpen={!!pendingDelete}, and call the real delete API only from
 * onConfirm. Also track an in-flight boolean around that same delete
 * call and pass it as loading, so a rapid double-tap can't fire
 * onConfirm twice before the first request completes - the same
 * pattern Form's own loading prop already follows.
 */
const ConfirmDialog = ({
  isOpen, title = 'Confirm', message = 'Are you sure you want to delete this?',
  confirmLabel = 'Delete', onConfirm, onCancel, loading = false,
}) => (
  <Modal isOpen={isOpen} title={title} onClose={onCancel}>
    <p className="confirm-dialog-message">{message}</p>
    <div className="confirm-dialog-actions">
      <button type="button" className="btn-secondary" onClick={onCancel} disabled={loading}>Cancel</button>
      <button type="button" className="btn-danger" onClick={onConfirm} disabled={loading}>
        {loading ? 'Please wait...' : confirmLabel}
      </button>
    </div>
  </Modal>
);

// --- KpiCard.jsx ---
function KpiCard({ label, value, tone = 'default', onClick }) {
  return (
    <Card
      className={`kpi-card kpi-${tone}${onClick ? ' kpi-card-clickable' : ''}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') onClick(); } : undefined}
    >
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
    </Card>
  );
}

// --- MaterialCard.jsx ---
/**
 * Amazon-style product card for the Material Catalog grid.
 * `view` is 'grid' (default) or 'list' - list renders a slimmer,
 * single-row layout for scanning many materials at once.
 */
function MaterialCard({ material, onOpen, onAddToCart, view = 'grid' }) {
  const [qty, setQty] = useState(1);

  const specLine = [material.thickness_size, material.brand_grade].filter(Boolean).join(' \u2022 ');
  const inStock = material.stock_status !== 'OUT OF STOCK';

  const handleAdd = (e) => {
    e.stopPropagation();
    onAddToCart(material, qty);
    setQty(1);
  };

  const stepQty = (e, delta) => {
    e.stopPropagation();
    setQty((q) => Math.max(1, q + delta));
  };

  const handleCardKeyDown = (e) => {
    if (e.target !== e.currentTarget) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onOpen(material);
    }
  };

  if (view === 'list') {
    return (
      <div className="material-row-card" onClick={() => onOpen(material)} onKeyDown={handleCardKeyDown} role="button" tabIndex={0}>
        <div className="material-row-swatch" aria-hidden="true">{(material.category || material.name || '?')[0]}</div>
        <div className="material-row-main">
          <div className="material-row-name">{material.name}</div>
          <div className="material-row-spec">{material.category || 'Uncategorized'}{specLine ? ` \u2022 ${specLine}` : ''}</div>
        </div>
        <div className="material-row-price">{formatCurrency(material.average_rate)}<span>/ {material.unit}</span></div>
        <div className="material-row-stock">
          <span className={`status-badge ${statusClass(material.stock_status)}`}>{material.stock_status}</span>
          <span className="material-row-stock-count">{material.current_stock} {material.unit}</span>
        </div>
        <div className="material-row-location">{material.location || '\u2014'}</div>
        <button className="btn-secondary material-row-cart-btn" disabled={!inStock} onClick={handleAdd}>
          <CartIcon width={14} height={14} /> Add
        </button>
      </div>
    );
  }

  return (
    <div className="material-card" onClick={() => onOpen(material)} onKeyDown={handleCardKeyDown} role="button" tabIndex={0}>
      <div className="material-card-media" aria-hidden="true">
        <span className="material-card-initial">{(material.category || material.name || '?')[0]}</span>
        <span className={`status-badge material-card-status ${statusClass(material.stock_status)}`}>{material.stock_status}</span>
      </div>
      <div className="material-card-body">
        <div className="material-card-category">{material.category || 'Uncategorized'}</div>
        <div className="material-card-name">{material.name}</div>
        {specLine && <div className="material-card-spec">{specLine}</div>}
        <div className="material-card-price-row">
          <span className="material-card-price">{formatCurrency(material.average_rate)}</span>
          <span className="material-card-unit">/ {material.unit}</span>
        </div>
        <div className="material-card-meta">
          <span>Stock: <strong>{material.current_stock} {material.unit}</strong></span>
          {material.location && <span className="material-card-location">{material.location}</span>}
        </div>
      </div>
      <div className="material-card-footer">
        <div className="material-card-qty" onClick={(e) => e.stopPropagation()}>
          <button type="button" onClick={(e) => stepQty(e, -1)} aria-label="Decrease quantity">{'\u2212'}</button>
          <span aria-live="polite">{qty}</span>
          <button type="button" onClick={(e) => stepQty(e, 1)} aria-label="Increase quantity">
            <PlusIcon width={12} height={12} />
          </button>
        </div>
        <button className="btn-primary material-card-add-btn" disabled={!inStock} onClick={handleAdd}>
          <CartIcon width={14} height={14} /> {inStock ? 'Add to Cart' : 'Out of Stock'}
        </button>
      </div>
    </div>
  );
}

// --- OrderLifecycle.jsx ---
// The real, existing 11-stage production pipeline (ORDER_PROJECT_STATUSES
// in app/utils/status_rules.py) - not an invented sequence. "On Hold" and
// "Cancelled" are reachable from any stage rather than being stages
// themselves, so they're shown as a status overlay rather than a step.
const STAGES = [
  'Enquiry', 'Designing', 'Approved', 'Material Purchase', 'Cutting',
  'Edge Banding', 'Assembly', 'Painting', 'Ready for Dispatch', 'Installation', 'Completed',
];

const SUB_TRACKS = [
  { key: 'design_status', label: 'Design' },
  { key: 'execution_status', label: 'Execution' },
  { key: 'delivery_status', label: 'Delivery' },
];

function SubTrackDot({ state }) {
  const cls = state === 'Completed' ? 'sub-dot-done' : state === 'In Progress' ? 'sub-dot-active' : 'sub-dot-pending';
  return <span className={`order-lifecycle-sub-dot ${cls}`} aria-hidden="true" />;
}

/* Visualizes Order.project_status as a spatial progression through
   Woodful's real production stages, with design/execution/delivery shown
   as three parallel tracks alongside it - these move independently of
   the main stage (e.g. Delivery can still be Pending while Painting is
   already underway), so folding them into one sequence would misrepresent
   the real state rather than clarify it. */
function OrderLifecycle({ order }) {
  const isHalted = order.project_status === 'On Hold' || order.project_status === 'Cancelled';
  const currentIndex = STAGES.indexOf(order.project_status);

  return (
    <div className="order-lifecycle">
      <div className={`order-lifecycle-track ${isHalted ? 'order-lifecycle-track-halted' : ''}`} role="list" aria-label="Order production stage">
        {STAGES.map((stage, i) => {
          // While halted, project_status itself no longer points at any
          // real stage in STAGES (it's "On Hold"/"Cancelled", a side-state)
          // and the backend doesn't record what stage the job was at
          // beforehand - so every step is shown as neutral/pending rather
          // than guessing or fabricating how far it got.
          const isPast = !isHalted && i < currentIndex;
          const isCurrent = !isHalted && i === currentIndex;
          return (
            <div
              key={stage}
              role="listitem"
              className={`order-lifecycle-step ${isPast ? 'order-lifecycle-step-done' : ''} ${isCurrent ? 'order-lifecycle-step-current' : ''}`}
              title={stage}
            >
              <span className="order-lifecycle-dot" aria-hidden="true" />
              <span className="order-lifecycle-step-label">{stage}</span>
            </div>
          );
        })}
      </div>
      {isHalted && (
        <span className={`status-badge ${order.project_status === 'Cancelled' ? 'status-danger' : 'status-warning'} order-lifecycle-halt-badge`}>
          {order.project_status}
        </span>
      )}
      <div className="order-lifecycle-subtracks">
        {SUB_TRACKS.map(({ key, label }) => (
          <div className="order-lifecycle-subtrack" key={key}>
            <SubTrackDot state={order[key]} />
            <span className="order-lifecycle-subtrack-label">{label}</span>
            <span className="order-lifecycle-subtrack-state">{order[key]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- SendEmailModal.jsx ---
/**
 * previewFn: () => Promise<{data: {recipient_email, client_has_email, subject, body, attachment_filename}}>
 * sendFn: (payload: {recipient_email, subject, body}) => Promise<{data: {sent, message}}>
 * Both are called fresh each time the modal opens, since the underlying
 * record (and its client's email) may have changed since the page loaded.
 */
function SendEmailModal({ isOpen, title, previewFn, sendFn, onClose, onSent }) {
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState(null);
  const [recipientEmail, setRecipientEmail] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    setError('');
    setPreview(null);
    previewFn()
      .then((res) => {
        setPreview(res.data);
        setRecipientEmail(res.data.recipient_email || '');
        setSubject(res.data.subject);
        setBody(res.data.body);
      })
      .catch((err) => setError(err.response?.data?.detail || 'Could not load a preview for this email.'))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const handleSend = async () => {
    if (!recipientEmail || !recipientEmail.includes('@')) {
      setError('Please enter a valid recipient email address.');
      return;
    }
    setSending(true);
    setError('');
    try {
      const res = await sendFn({ recipient_email: recipientEmail, subject, body });
      onSent && onSent(res.data.message);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'The email could not be sent. Please try again.');
    } finally {
      setSending(false);
    }
  };

  return (
    <Modal isOpen={isOpen} title={title} onClose={onClose}>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {loading && <p>Loading preview...</p>}
      {!loading && preview && (
        <div>
          {!preview.client_has_email && (
            <Alert type="warning" onClose={() => {}} message="This client has no email on file - please enter one below before sending." />
          )}
          <div className="form-group">
            <label className="form-label" htmlFor="send-email-to">To</label>
            <input
              id="send-email-to" className="form-input" type="email" value={recipientEmail}
              onChange={(e) => setRecipientEmail(e.target.value)} placeholder="client@example.com"
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="send-email-subject">Subject</label>
            <input
              id="send-email-subject" className="form-input" type="text" value={subject}
              onChange={(e) => setSubject(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="send-email-body">Message</label>
            <textarea
              id="send-email-body" className="form-input" rows={8} value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 16 }}>
            Attachment: {preview.attachment_filename}
          </p>
          <div style={{ display: 'flex', gap: 12 }}>
            <button className="btn-primary" onClick={handleSend} disabled={sending}>
              {sending ? 'Sending...' : 'Send'}
            </button>
            <button className="btn-secondary" onClick={onClose} disabled={sending}>Cancel</button>
          </div>
        </div>
      )}
    </Modal>
  );
}

// --- SimpleBarChart.jsx ---
/* A small, dependency-free horizontal bar chart, built with plain CSS
 * width percentages (no SVG, no charting library needed - none exists
 * in this project, and a new npm dependency couldn't be verified to
 * resolve correctly in this environment) - driven entirely by real
 * data passed in. */
function SimpleBarChart({ data, labelKey, valueKey, formatValue = (v) => v, color = 'var(--color-gold)' }) {
  if (!data || data.length === 0) {
    return <div className="simple-chart-empty">No data yet.</div>;
  }
  const max = Math.max(...data.map((d) => Number(d[valueKey]) || 0), 1);

  return (
    <div className="simple-bar-chart">
      {data.map((d, i) => {
        const value = Number(d[valueKey]) || 0;
        const pct = (value / max) * 100;
        return (
          <div className="simple-bar-row" key={i}>
            <span className="simple-bar-label">{d[labelKey]}</span>
            <div className="simple-bar-track">
              <div className="simple-bar-fill" style={{ width: `${pct}%`, background: color }} />
            </div>
            <span className="simple-bar-value">{formatValue(value)}</span>
          </div>
        );
      })}
    </div>
  );
}

export { Alert, Card, Form, Modal, Pagination, Table, ConfirmDialog, KpiCard, MaterialCard, OrderLifecycle, SendEmailModal, SimpleBarChart };
