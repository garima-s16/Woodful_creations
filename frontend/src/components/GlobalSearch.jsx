import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { searchAPI } from '../utils/api';
import '../styles/components/GlobalSearch.css';

function GlobalSearch() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef(null);

  // A live-search-as-you-type field genuinely needs debouncing (unlike
  // the page-level submit-triggered searches elsewhere in the app) -
  // without it, every keystroke would fire its own request.
  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      setLoading(false);
      return undefined;
    }
    setLoading(true);
    const timer = setTimeout(() => {
      searchAPI.query(query.trim())
        .then((res) => setResults(res.data))
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    function handleClickOutside(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (result) => {
    setQuery('');
    setResults([]);
    setOpen(false);
    navigate(result.path);
  };

  return (
    <div className="global-search" ref={containerRef}>
      <input
        type="text"
        className="global-search-input"
        placeholder="Search clients, orders, materials..."
        value={query}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
      />
      {open && query.trim() && (
        <div className="global-search-results">
          {loading && <div className="global-search-status">Searching...</div>}
          {!loading && results.length === 0 && (
            <div className="global-search-status">No matches for &ldquo;{query}&rdquo;.</div>
          )}
          {!loading && results.map((r) => (
            <button
              key={`${r.type}-${r.id}`}
              className="global-search-result"
              onClick={() => handleSelect(r)}
            >
              <span className="global-search-result-type">{r.type}</span>
              <span className="global-search-result-label">{r.label}</span>
              {r.sublabel && <span className="global-search-result-sublabel">{r.sublabel}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default GlobalSearch;
