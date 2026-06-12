import React, { useState, useEffect } from 'react';
import axios from 'axios';
import '../styles/pages/AttendancePage.css';
import AttendanceCalendar from '../components/attendance/AttendanceCalendar';
import AttendanceList from '../components/attendance/AttendanceList';
import SalarySlips from '../components/attendance/SalarySlips';

function AttendancePage({ user }) {
  const [employees, setEmployees] = useState([]);
  const [attendance, setAttendance] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [selectedMonth, setSelectedMonth] = useState(new Date().toISOString().slice(0, 7));
  const [activeTab, setActiveTab] = useState('attendance');

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    fetchEmployees();
    fetchAttendance();
  }, [selectedMonth]);

  const fetchEmployees = async () => {
    try {
      const token = localStorage.getItem('authToken');
      const response = await axios.get(
        `${API_BASE_URL}/api/employees`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setEmployees(response.data.employees);
      if (response.data.employees.length > 0) {
        setSelectedEmployee(response.data.employees[0].id);
      }
    } catch (err) {
      setError('Failed to load employees');
      console.error(err);
    }
  };

  const fetchAttendance = async () => {
    try {
      const token = localStorage.getItem('authToken');
      const response = await axios.get(
        `${API_BASE_URL}/api/attendance?month=${selectedMonth}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setAttendance(response.data.attendance);
    } catch (err) {
      setError('Failed to load attendance');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleMarkAttendance = async (employeeId, date, status) => {
    try {
      const token = localStorage.getItem('authToken');
      await axios.post(
        `${API_BASE_URL}/api/attendance`,
        {
          employee_id: employeeId,
          date,
          status
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      fetchAttendance();
    } catch (err) {
      setError('Failed to mark attendance');
      console.error(err);
    }
  };

  const handleGenerateSalarySlip = async (employeeId) => {
    try {
      const token = localStorage.getItem('authToken');
      const response = await axios.get(
        `${API_BASE_URL}/api/attendance/${employeeId}/salary-slip?month=${selectedMonth}`,
        { 
          headers: { Authorization: `Bearer ${token}` },
          responseType: 'blob'
        }
      );
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `salary-slip-${employeeId}-${selectedMonth}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.parentChild.removeChild(link);
    } catch (err) {
      setError('Failed to generate salary slip');
      console.error(err);
    }
  };

  return (
    <div className="attendance-page">
      <div className="attendance-header">
        <div>
          <h1>Employee Attendance</h1>
          <p>Track attendance and manage salaries</p>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="attendance-controls">
        <input
          type="month"
          value={selectedMonth}
          onChange={(e) => setSelectedMonth(e.target.value)}
          className="month-picker"
        />

        <div className="tab-buttons">
          <button 
            className={`tab-button ${activeTab === 'attendance' ? 'active' : ''}`}
            onClick={() => setActiveTab('attendance')}
          >
            Attendance
          </button>
          <button 
            className={`tab-button ${activeTab === 'salary' ? 'active' : ''}`}
            onClick={() => setActiveTab('salary')}
          >
            Salary Slips
          </button>
        </div>
      </div>

      {loading ? (
        <div className="loading">Loading attendance data...</div>
      ) : (
        <div className="attendance-content">
          {activeTab === 'attendance' && (
            <div className="attendance-section">
              <div className="employee-selector">
                <label>Select Employee:</label>
                <select 
                  value={selectedEmployee}
                  onChange={(e) => setSelectedEmployee(e.target.value)}
                  className="employee-select"
                >
                  {employees.map(emp => (
                    <option key={emp.id} value={emp.id}>
                      {emp.name}
                    </option>
                  ))}
                </select>
              </div>

              {selectedEmployee && (
                <>
                  <AttendanceCalendar 
                    employeeId={selectedEmployee}
                    month={selectedMonth}
                    attendance={attendance}
                    onMarkAttendance={handleMarkAttendance}
                    canEdit={user?.role === 'master'}
                  />
                  <AttendanceList 
                    employeeId={selectedEmployee}
                    attendance={attendance}
                  />
                </>
              )}
            </div>
          )}

          {activeTab === 'salary' && (
            <SalarySlips 
              employees={employees}
              month={selectedMonth}
              onGenerateSlip={handleGenerateSalarySlip}
            />
          )}
        </div>
      )}
    </div>
  );
}

export default AttendancePage;