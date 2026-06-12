import React from 'react';
import '../../styles/components/attendance/AttendanceList.css';

function AttendanceList({ employeeId, attendance }) {
  const employeeAttendance = attendance.filter(a => a.employee_id === employeeId);

  const stats = {
    present: employeeAttendance.filter(a => a.status === 'present').length,
    absent: employeeAttendance.filter(a => a.status === 'absent').length,
    leave: employeeAttendance.filter(a => a.status === 'leave').length,
    halfDay: employeeAttendance.filter(a => a.status === 'half_day').length
  };

  return (
    <div className="attendance-list">
      <h3>Attendance Summary</h3>
      
      <div className="stats-grid">
        <div className="stat-card present">
          <div className="stat-label">Present</div>
          <div className="stat-value">{stats.present}</div>
        </div>
        <div className="stat-card absent">
          <div className="stat-label">Absent</div>
          <div className="stat-value">{stats.absent}</div>
        </div>
        <div className="stat-card leave">
          <div className="stat-label">Leave</div>
          <div className="stat-value">{stats.leave}</div>
        </div>
        <div className="stat-card halfday">
          <div className="stat-label">Half Day</div>
          <div className="stat-value">{stats.halfDay}</div>
        </div>
      </div>

      <div className="attendance-records">
        <h4>Attendance Records</h4>
        {employeeAttendance.length > 0 ? (
          <table className="records-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Status</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {employeeAttendance.map((record, idx) => (
                <tr key={idx}>
                  <td>{record.date}</td>
                  <td>
                    <span className={`status-badge ${record.status}`}>
                      {record.status.replace('_', ' ').toUpperCase()}
                    </span>
                  </td>
                  <td>{record.notes || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="no-records">No attendance records found</div>
        )}
      </div>
    </div>
  );
}

export default AttendanceList;