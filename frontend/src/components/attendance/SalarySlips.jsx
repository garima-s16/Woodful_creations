import React from 'react';
import '../../styles/components/attendance/SalarySlips.css';

function SalarySlips({ employees, month, onGenerateSlip }) {
  return (
    <div className="salary-slips">
      <h3>Generate Salary Slips for {month}</h3>
      
      <div className="slips-table">
        <table>
          <thead>
            <tr>
              <th>Employee Name</th>
              <th>Employee ID</th>
              <th>Department</th>
              <th>Basic Salary</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {employees.map(emp => (
              <tr key={emp.id}>
                <td>{emp.name}</td>
                <td>{emp.id}</td>
                <td>{emp.department}</td>
                <td>Rs {emp.basic_salary}</td>
                <td>
                  <button 
                    className="btn-generate"
                    onClick={() => onGenerateSlip(emp.id)}
                  >
                    Generate Slip
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {employees.length === 0 && (
        <div className="no-employees">No employees found</div>
      )}
    </div>
  );
}

export default SalarySlips;