import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import './Form.css';

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

export default Form;
