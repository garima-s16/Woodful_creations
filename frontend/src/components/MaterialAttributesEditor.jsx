import React, { useEffect, useState } from 'react';
import { materialCategoriesAPI } from '../utils/api';
import '../styles/components/MaterialAttributesEditor.css';

/* Category -> Subcategory -> dynamic attribute fields. Form.js can't
 * render fields that change based on another field's value within the
 * same form, so this is a dedicated component (same reason
 * LineItemEditor exists) - rendered alongside the static Form fields
 * (name, unit, stock settings), not replacing them. Reports
 * {subcategoryId, attributeValues} up to the parent on every change. */
function MaterialAttributesEditor({ onChange }) {
  const [categories, setCategories] = useState([]);
  const [categoryId, setCategoryId] = useState('');
  const [subcategories, setSubcategories] = useState([]);
  const [subcategoryId, setSubcategoryId] = useState('');
  const [attributeDefs, setAttributeDefs] = useState([]);
  const [values, setValues] = useState({}); // attribute_definition_id -> raw string input

  useEffect(() => {
    materialCategoriesAPI.list().then((res) => setCategories(res.data)).catch(() => setCategories([]));
  }, []);

  const handleCategoryChange = (e) => {
    const id = e.target.value;
    setCategoryId(id);
    setSubcategoryId('');
    setAttributeDefs([]);
    setValues({});
    const category = categories.find((c) => String(c.id) === id);
    setSubcategories(category?.subcategories || []);
    onChange({ subcategoryId: null, attributeValues: [] });
  };

  const handleSubcategoryChange = (e) => {
    const id = e.target.value;
    setSubcategoryId(id);
    setValues({});
    const subcategory = subcategories.find((s) => String(s.id) === id);
    const defs = subcategory?.attribute_definitions || [];
    setAttributeDefs(defs);
    onChange({ subcategoryId: id ? Number(id) : null, attributeValues: [] });
  };

  const handleValueChange = (attrId, rawValue, dataType) => {
    const nextValues = { ...values, [attrId]: rawValue };
    setValues(nextValues);
    const attributeValues = attributeDefs
      .filter((def) => nextValues[def.id])
      .map((def) => ({
        attribute_definition_id: def.id,
        value_number: def.data_type === 'number' ? nextValues[def.id] : undefined,
        value_text: def.data_type !== 'number' ? nextValues[def.id] : undefined,
      }));
    onChange({ subcategoryId: subcategoryId ? Number(subcategoryId) : null, attributeValues });
  };

  return (
    <div className="material-attributes-editor">
      <div className="material-attributes-row">
        <div className="form-group">
          <label>Category</label>
          <select className="form-input" value={categoryId} onChange={handleCategoryChange}>
            <option value="">Select category (optional)</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        {categoryId && (
          <div className="form-group">
            <label>Subcategory</label>
            <select className="form-input" value={subcategoryId} onChange={handleSubcategoryChange}>
              <option value="">Select subcategory</option>
              {subcategories.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
        )}
      </div>

      {attributeDefs.length > 0 && (
        <div className="material-attributes-fields">
          <div className="material-attributes-label">Specifications</div>
          {attributeDefs.map((def) => (
            <div className="form-group" key={def.id}>
              <label>{def.name}{def.is_required && ' *'}{def.unit_label && ` (${def.unit_label})`}</label>
              {def.data_type === 'select' ? (
                <select className="form-input" value={values[def.id] || ''} onChange={(e) => handleValueChange(def.id, e.target.value, def.data_type)}>
                  <option value="">Select {def.name}</option>
                  {(def.select_options || '').split(',').map((opt) => opt.trim()).filter(Boolean).map((opt) => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
              ) : (
                <input
                  type={def.data_type === 'number' ? 'number' : 'text'}
                  className="form-input"
                  value={values[def.id] || ''}
                  onChange={(e) => handleValueChange(def.id, e.target.value, def.data_type)}
                  placeholder={def.name}
                />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default MaterialAttributesEditor;
