import React, { useState, useEffect } from 'react';
import axios from 'axios';
import '../styles/pages/PaymentsPage.css';
import PaymentList from '../components/payments/PaymentList';
import PaymentForm from '../components/payments/PaymentForm';
import PaymentStats from '../components/payments/PaymentStats';

function PaymentsPage({ user }) {
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [filterStatus, setFilterStatus] = useState('all');
  const [stats, setStats] = useState(null);

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    if (user?.role === 'master') {
      fetchPayments();
      fetchStats();
    }
  }, [filterStatus, user?.role]);

  const fetchPayments = async () => {
    try {
      const token = localStorage.getItem('authToken');
      const params = new URLSearchParams();
      if (filterStatus !== 'all') params.append('status', filterStatus);

      const response = await axios.get(
        `${API_BASE_URL}/api/payments?${params.toString()}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setPayments(response.data.payments);
    } catch (err) {
      setError('Failed to load payments');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const token = localStorage.getItem('authToken');
      const response = await axios.get(
        `${API_BASE_URL}/api/payments/stats`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setStats(response.data);
    } catch (err) {
      console.error('Failed to load payment stats', err);
    }
  };

  const handleAddPayment = async (paymentData) => {
    try {
      const token = localStorage.getItem('authToken');
      await axios.post(
        `${API_BASE_URL}/api/payments`,
        paymentData,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setShowForm(false);
      fetchPayments();
      fetchStats();
    } catch (err) {
      setError('Failed to add payment');
      console.error(err);
    }
  };

  const handleDeletePayment = async (paymentId) => {
    if (!window.confirm('Are you sure you want to delete this payment?')) return;

    try {
      const token = localStorage.getItem('authToken');
      await axios.delete(
        `${API_BASE_URL}/api/payments/${paymentId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      fetchPayments();
      fetchStats();
    } catch (err) {
      setError('Failed to delete payment');
      console.error(err);
    }
  };

  if (user?.role !== 'master') {
    return (
      <div className="payments-page">
        <div className="access-denied">
          <h1>Access Denied</h1>
          <p>Only Master Users can access Payment Management</p>
        </div>
      </div>
    );
  }

  return (
    <div className="payments-page">
      <div className="payments-header">
        <div>
          <h1>Payment Management</h1>
          <p>Track all payments owed by Woodful Creations</p>
        </div>
        <button 
          className="btn-primary"
          onClick={() => setShowForm(true)}
        >
          Add New Payment
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {stats && <PaymentStats stats={stats} />}

      <div className="payments-filter">
        <select 
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="filter-select"
        >
          <option value="all">All Payments</option>
          <option value="pending">Pending</option>
          <option value="completed">Completed</option>
          <option value="overdue">Overdue</option>
        </select>
      </div>

      {loading ? (
        <div className="loading">Loading payments...</div>
      ) : (
        <PaymentList 
          payments={payments}
          onDelete={handleDeletePayment}
        />
      )}

      {showForm && (
        <PaymentForm
          onAdd={handleAddPayment}
          onClose={() => setShowForm(false)}
        />
      )}
    </div>
  );
}

export default PaymentsPage;