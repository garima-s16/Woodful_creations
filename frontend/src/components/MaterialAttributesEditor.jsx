import React, { useEffect, useState, useImperativeHandle, forwardRef } from 'react';
import { materialCategoriesAPI } from '../utils/api';
import '../styles/components/MaterialAttributesEditor.css';

/* Category -> Subcategory -> dynamic attribute fields. Form.js can't
 * render fields that change based on another field's value within the
 * same form, so this is a dedicated component (same reason
 * LineItemEditor exists) - rendered alongside the static Form fields
 * (name, unit, stock settings), not replacing them. Reports
 * {subcategoryId, attributeValues} up to the parent on every change.
 *
 * initialSubcategoryId/initialAttributeValues let the same component
 * serve both create (blank) and edit (pre-populated with the
 * material's current specs) - passing neither behaves exactly as
 * before. initialAttributeValues is the material's real
 * attribute_values response shape (attribute_definition_id +
 * value_text/value_number), not a separately-invented input format. */
const MaterialAttributesEditor = forwardRef(function MaterialAttributesEditor(
  { onChange, initialSubcategoryId, initialAttributeValues }, ref
) {
  const [categories, setCategories] = useState([]);
  const [categoryId, setCategoryId] = useState('');
  const [subcategories, setSubcategories] = useState([]);
  const [subcategoryId, setSubcategoryId] = useState('');
  const [attributeDefs, setAttributeDefs] = useState([]);
  const [values, setValues] = useState({}); // attribute_definition_id -> raw string input

  // Selects a subcategory (and pre-fills its attribute values) given the
  // already-fetched category list. Shared by the initial-mount pre-fill
  // (editing an existing material) and applySuggestedSubcategory below
  // (Family 5's "intelligent defaults", accepted by explicit user action)
  // so the two never drift into two different implementations of the
  // same lookup.
  const selectSubcategory = (targetSubcategoryId, categoriesList, prefillAttributeValues) => {
    for (const category of categoriesList) {
      const match = (category.subcategories || []).find((s) => s.id === targetSubcategoryId);
      if (match) {
        setCategoryId(String(category.id));
        setSubcategories(category.subcategories);
        setSubcategoryId(String(match.id));
        setAttributeDefs(match.attribute_definitions || []);
        const prefilled = {};
        const attributeValues = [];
        (prefillAttributeValues || []).forEach((v) => {
          const raw = v.value_number ?? v.value_text ?? '';
          prefilled[v.attribute_definition_id] = raw;
          attributeValues.push({
            attribute_definition_id: v.attribute_definition_id,
            value_number: v.value_number != null ? raw : undefined,
            value_text: v.value_number == null ? raw : undefined,
          });
        });
        setValues(prefilled);
        onChange({ subcategoryId: match.id, attributeValues });
        return true;
      }
    }
    return false;
  };

  useEffect(() => {
    materialCategoriesAPI.list().then((res) => {
      setCategories(res.data);
      if (!initialSubcategoryId) return;
      // Find which category owns this subcategory, so both selects and
      // the attribute fields can be pre-populated in one pass. The
      // parent's state must reflect these pre-populated values
      // immediately - otherwise saving the form without touching the
      // hierarchy fields would submit subcategoryId: null and silently
      // wipe the material's existing category/specs.
      selectSubcategory(initialSubcategoryId, res.data, initialAttributeValues);
    }).catch(() => setCategories([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useImperativeHandle(ref, () => ({
    // Applies a suggested subcategory (Family 5's material-name
    // interpretation, e.g. typing "HDHMR 6mm"). Only ever called from an
    // explicit "Apply suggestion" click - never automatically - so it
    // can't fight a category/subcategory the user already chose
    // themselves. Selecting a subcategory clears attribute values the
    // same way the manual dropdown does (a different subcategory means
    // different attribute definitions), so there's nothing stale left
    // behind from a prior selection. Returns false if the suggested
    // subcategory can no longer be found (e.g. deleted meanwhile).
    applySuggestedSubcategory(targetSubcategoryId) {
      if (!targetSubcategoryId) return false;
      return selectSubcategory(targetSubcategoryId, categories, null);
    },
  }), [categories]);

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
});

export default MaterialAttributesEditor;
