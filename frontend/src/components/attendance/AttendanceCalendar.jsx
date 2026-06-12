import React from 'react';
import '../../styles/components/attendance/AttendanceCalendar.css';

function AttendanceCalendar({ employeeId, month, attendance, onMarkAttendance, canEdit }) {
  const getDaysInMonth = (date) => {
    return new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
  };

  const getFirstDayOfMonth = (date) => {
    return new Date(date.getFullYear(), date.getMonth(), 1).getDay();
  };

  const [year, monthNum] = month.split('-').map(Number);
  const date = new Date(year, monthNum - 1);
  const daysInMonth = getDaysInMonth(date);
  const firstDay = getFirstDayOfMonth(date);

  const getAttendanceStatus = (day) => {
    const attendanceKey = `${year}-${String(monthNum).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const record = attendance.find(a => a.date === attendanceKey && a.employee_id === employeeId);
    return record?.status || null;
  };

  const handleStatusChange = (day, status) => {
    if (canEdit) {
      const dateStr = `${year}-${String(monthNum).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      onMarkAttendance(employeeId, dateStr, status);
    }
  };

  const days = [];
  for (let i = 0; i < firstDay; i++) {
    days.push(null);
  }
  for (let i = 1; i <= daysInMonth; i++) {
    days.push(i);
  }

  const monthName = new Date(year, monthNum - 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

  return (
    <div className="attendance-calendar">
      <h3>{monthName}</h3>
      <div className="calendar-grid">
        <div className="calendar-header">
          <div>Sun</div>
          <div>Mon</div>
          <div>Tue</div>
          <div>Wed</div>
          <div>Thu</div>
          <div>Fri</div>
          <div>Sat</div>
        </div>

        <div className="calendar-days">
          {days.map((day, index) => {
            const status = day ? getAttendanceStatus(day) : null;
            return (
              <div key={index} className={`calendar-day ${status ? status.toLowerCase() : 'empty'}`}>
                {day && (
                  <>
                    <div className="day-number">{day}</div>
                    {canEdit ? (
                      <select 
                        value={status || 'unmarked'}
                        onChange={(e) => handleStatusChange(day, e.target.value)}
                        className="status-select"
                      >
                        <option value="unmarked">-</option>
                        <option value="present">P</option>
                        <option value="absent">A</option>
                        <option value="leave">L</option>
                        <option value="half_day">H</option>
                      </select>
                    ) : (
                      <div className="status-display">
                        {status ? status.charAt(0).toUpperCase() : '-'}
                      </div>
                    )}
                  </>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="calendar-legend">
        <div className="legend-item"><span className="legend-present"></span>Present</div>
        <div className="legend-item"><span className="legend-absent"></span>Absent</div>
        <div className="legend-item"><span className="legend-leave"></span>Leave</div>
        <div className="legend-item"><span className="legend-half"></span>Half Day</div>
      </div>
    </div>
  );
}

export default AttendanceCalendar;