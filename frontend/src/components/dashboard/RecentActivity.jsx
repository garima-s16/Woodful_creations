import React from 'react';
import '../../styles/components/dashboard/RecentActivity.css';

function RecentActivity({ data }) {
  const activities = data || [];

  return (
    <div className="recent-activity">
      <h2>Recent Activities</h2>
      {activities.length > 0 ? (
        <div className="activity-list">
          {activities.map((activity, index) => (
            <div key={index} className="activity-item">
              <div className="activity-time">{activity.timestamp}</div>
              <div className="activity-content">
                <div className="activity-type">{activity.type}</div>
                <div className="activity-description">{activity.description}</div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="no-activities">No recent activities</div>
      )}
    </div>
  );
}

export default RecentActivity;