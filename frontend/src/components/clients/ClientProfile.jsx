import React, { useState } from 'react';
import '../../styles/components/clients/ClientProfile.css';

function ClientProfile({ client, user, onUpdate }) {
  const [activeTab, setActiveTab] = useState('overview');
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState(client);

  const handleSave = () => {
    onUpdate(client.id, editData);
    setIsEditing(false);
  };

  return (
    <div className="client-profile">
      <div className="profile-header">
        <h2>{client.name}</h2>
        {user?.role === 'master' && (
          <button 
            className={`btn-edit-toggle ${isEditing ? 'editing' : ''}`}
            onClick={() => setIsEditing(!isEditing)}
          >
            {isEditing ? 'Cancel' : 'Edit'}
          </button>
        )}
      </div>

      <div className="profile-tabs">
        <button 
          className={`tab ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        <button 
          className={`tab ${activeTab === 'products' ? 'active' : ''}`}
          onClick={() => setActiveTab('products')}
        >
          Products
        </button>
        <button 
          className={`tab ${activeTab === 'payments' ? 'active' : ''}`}
          onClick={() => setActiveTab('payments')}
        >
          Payments
        </button>
        <button 
          className={`tab ${activeTab === 'history' ? 'active' : ''}`}
          onClick={() => setActiveTab('history')}
        >
          History
        </button>
      </div>

      <div className="profile-content">
        {activeTab === 'overview' && (
          <div className="overview-tab">
            {isEditing ? (
              <div className="edit-form">
                <div className="form-row">
                  <div className="form-group">
                    <label>Name</label>
                    <input 
                      type="text" 
                      value={editData.name}
                      onChange={(e) => setEditData({...editData, name: e.target.value})}
                    />
                  </div>
                  <div className="form-group">
                    <label>Email</label>
                    <input 
                      type="email" 
                      value={editData.email}
                      onChange={(e) => setEditData({...editData, email: e.target.value})}
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Phone</label>
                    <input 
                      type="tel" 
                      value={editData.phone}
                      onChange={(e) => setEditData({...editData, phone: e.target.value})}
                    />
                  </div>
                  <div className="form-group">
                    <label>Company</label>
                    <input 
                      type="text" 
                      value={editData.company}
                      onChange={(e) => setEditData({...editData, company: e.target.value})}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label>Address</label>
                  <textarea 
                    value={editData.address}
                    onChange={(e) => setEditData({...editData, address: e.target.value})}
                    rows="3"
                  />
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Classification</label>
                    <select 
                      value={editData.classification}
                      onChange={(e) => setEditData({...editData, classification: e.target.value})}
                    >
                      <option value="VIP">VIP</option>
                      <option value="Regular">Regular</option>
                      <option value="New">New</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label>Credit Limit</label>
                    <input 
                      type="number" 
                      value={editData.credit_limit}
                      onChange={(e) => setEditData({...editData, credit_limit: parseFloat(e.target.value)})}
                    />
                  </div>
                </div>

                <button className="btn-save" onClick={handleSave}>Save Changes</button>
              </div>
            ) : (
              <div className="info-display">
                <div className="info-row">
                  <span className="label">Email:</span>
                  <span className="value">{client.email}</span>
                </div>
                <div className="info-row">
                  <span className="label">Phone:</span>
                  <span className="value">{client.phone}</span>
                </div>
                <div className="info-row">
                  <span className="label">Company:</span>
                  <span className="value">{client.company}</span>
                </div>
                <div className="info-row">
                  <span className="label">Address:</span>
                  <span className="value">{client.address}</span>
                </div>
                <div className="info-row">
                  <span className="label">Classification:</span>
                  <span className="value badge">{client.classification}</span>
                </div>
                <div className="info-row">
                  <span className="label">Credit Limit:</span>
                  <span className="value">Rs {client.credit_limit}</span>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'products' && (
          <div className="products-tab">
            <h3>Products Requested</h3>
            {client.products && client.products.length > 0 ? (
              <table className="products-table">
                <thead>
                  <tr>
                    <th>Product Name</th>
                    <th>Quantity</th>
                    <th>Design Status</th>
                    <th>Execution Status</th>
                    <th>Delivery Status</th>
                    <th>ETA</th>
                  </tr>
                </thead>
                <tbody>
                  {client.products.map(prod => (
                    <tr key={prod.id}>
                      <td>{prod.name}</td>
                      <td>{prod.quantity}</td>
                      <td>{prod.design_status}</td>
                      <td>{prod.execution_status}</td>
                      <td>{prod.delivery_status}</td>
                      <td>{prod.eta}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="no-data">No products requested</div>
            )}
          </div>
        )}

        {activeTab === 'payments' && (
          <div className="payments-tab">
            <h3>Payment Details</h3>
            <div className="payment-summary">
              <div className="payment-card">
                <div className="payment-label">Total Invoiced</div>
                <div className="payment-value">Rs {client.total_invoiced || 0}</div>
              </div>
              <div className="payment-card">
                <div className="payment-label">Paid</div>
                <div className="payment-value">Rs {client.total_paid || 0}</div>
              </div>
              <div className="payment-card">
                <div className="payment-label">Pending</div>
                <div className="payment-value">Rs {(client.total_invoiced || 0) - (client.total_paid || 0)}</div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'history' && (
          <div className="history-tab">
            <h3>Recent Activity</h3>
            {client.activities && client.activities.length > 0 ? (
              <div className="activity-list">
                {client.activities.map((activity, idx) => (
                  <div key={idx} className="activity-item">
                    <div className="activity-date">{activity.date}</div>
                    <div className="activity-description">{activity.description}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="no-data">No recent activities</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default ClientProfile;