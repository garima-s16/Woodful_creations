import React from 'react';
import './Pagination.css';

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

export default Pagination;
