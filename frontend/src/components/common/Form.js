import React from 'react';
import './Form.css';

function FieldInput({ field, value, error, onChange, formData }) {
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
        id={field.name} name={field.name} value={value || ''} onChange={onChange}
        placeholder={field.placeholder} rows={field.rows || 4}
        className={`form-input ${error ? 'error' : ''}`}
      />
    );
  }
  if (field.type === 'select') {
    return (
      <select
        id={field.name} name={field.name} value={value || ''} onChange={onChange}
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
      onChange={onChange} placeholder={field.placeholder}
      className={`form-input ${error ? 'error' : ''}`}
    />
  );
}

function FieldGroup({ field, formData, errors, handleChange }) {
  return (
    <div className="form-group">
      <label htmlFor={field.name} className="form-label">
        {field.label} {field.required && <span className="required">*</span>}
      </label>
      <FieldInput field={field} value={formData[field.name]} error={errors[field.name]} onChange={handleChange} formData={formData} />
      {field.hint && <span className="form-hint">{field.hint}</span>}
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
const Form = ({ fields, onSubmit, loading = false, submitText = 'Submit', initialValues = {} }) => {
  const [formData, setFormData] = React.useState(initialValues);
  const [errors, setErrors] = React.useState({});
  const [step, setStep] = React.useState(0);

  React.useEffect(() => {
    setFormData(initialValues);
    setStep(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(initialValues)]);

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
  };

  const validate = (fieldsToCheck) => {
    const newErrors = {};
    fieldsToCheck.forEach((field) => {
      if (field.required && !formData[field.name]) {
        newErrors[field.name] = `${field.label} is required`;
      }
    });
    return newErrors;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const newErrors = validate(fields);
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }
    onSubmit(formData);
  };

  if (!sections) {
    return (
      <form className="form" onSubmit={handleSubmit}>
        {fields.map((field) => (
          <FieldGroup key={field.name} field={field} formData={formData} errors={errors} handleChange={handleChange} />
        ))}
        <button type="submit" className="btn-submit" disabled={loading}>
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
          {currentSection.fields.map((field) => (
            <FieldGroup key={field.name} field={field} formData={formData} errors={errors} handleChange={handleChange} />
          ))}
        </div>
      )}

      {isReview && (
        <div className="wizard-panel wizard-review">
          {sections.map((s) => (
            <div key={s.name} className="review-section">
              <h4>{s.name}</h4>
              {s.fields.map((f) => (
                <div key={f.name} className="review-row">
                  <span className="review-label">{f.label}</span>
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
          <button type="submit" className="btn-submit" disabled={loading}>
            {loading ? 'Please wait...' : submitText}
          </button>
        )}
      </div>
    </form>
  );
};

export default Form;
