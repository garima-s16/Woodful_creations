import React from 'react';
import '../../styles/components/analytics/EmployeeAnalytics.css';

function EmployeeAnalytics({ data }) {
  const employeeData = data?.employee || {};

  return (
    <div className="employee-analytics">
      <div className="analytics-section">
        <h3>Employee Headcount and Trends</h3>
        <div className="metrics-grid">
          <div className="metric-card">
            <div className="metric-label">Total Employees</div>
            <div className="metric-value">{employeeData.total_employees || 0}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">New Joinings</div>
            <div className="metric-value">{employeeData.new_joinings || 0}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Turnover Rate</div>
            <div className="metric-value">{employeeData.turnover_rate || 0}%</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Avg Tenure</div>
            <div className="metric-value">{employeeData.avg_tenure || 0} years</div>
          </div>
        </div>
      </div>

      <div className="analytics-section">
        <h3>Attendance Trends</h3>
        <div className="metrics-grid">
          <div className="metric-card attendance">
            <div className="metric-label">Average Attendance Rate</div>
            <div className="metric-value">{employeeData.avg_attendance || 0}%</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Frequent Absentees</div>
            <div className="metric-value">{employeeData.frequent_absentees || 0}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Leave Utilization</div>
            <div className="metric-value">{employeeData.leave_utilization || 0}%</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Avg Leave Days Used</div>
            <div className="metric-value">{employeeData.avg_leaves_used || 0}</div>
          </div>
        </div>
      </div>

      <div className="analytics-section">
        <h3>Salary Expenditure Analysis</h3>
        <table className="analytics-table">
          <thead>
            <tr>
              <th>Department</th>
              <th>Employee Count</th>
              <th>Total Salary</th>
              <th>Average Salary</th>
              <th>Salary as % of Revenue</th>
            </tr>
          </thead>
          <tbody>
            {employeeData.salary_by_department && employeeData.salary_by_department.length > 0 ? (
              employeeData.salary_by_department.map((dept, idx) => (
                <tr key={idx}>
                  <td>{dept.department}</td>
                  <td>{dept.count}</td>
                  <td>Rs {dept.total}</td>
                  <td>Rs {dept.average}</td>
                  <td>{dept.percentage}%</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="5" className="no-data">No salary data available</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="analytics-section">
        <h3>Employee Performance Metrics</h3>
        <table className="analytics-table">
          <thead>
            <tr>
              <th>Employee Name</th>
              <th>Attendance Rate</th>
              <th>Leave Taken</th>
              <th>Performance Score</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {employeeData.performance && employeeData.performance.length > 0 ? (
              employeeData.performance.map((emp, idx) => (
                <tr key={idx}>
                  <td>{emp.name}</td>
                  <td>{emp.attendance}%</td>
                  <td>{emp.leaves_taken}</td>
                  <td>
                    <div className="performance-bar">
                      <div 
                        className="performance-fill"
                        style={{width: `${emp.score}%`}}
                      ></div>
                    </div>
                  </td>
                  <td>
                    <span className={`status-badge ${emp.status}`}>
                      {emp.status}
                    </span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="5" className="no-data">No performance data available</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default EmployeeAnalytics;