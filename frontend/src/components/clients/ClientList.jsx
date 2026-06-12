import React from 'react';
import '../../styles/components/clients/ClientList.css';

function ClientList({ clients, selectedClient, onSelectClient }) {
  return (
    <div className="client-list">
      {clients.length > 0 ? (
        <ul className="client-items">
          {clients.map(client => (
            <li 
              key={client.id}
              className={`client-item ${selectedClient?.id === client.id ? 'selected' : ''}`}
              onClick={() => onSelectClient(client)}
            >
              <div className="client-item-header">
                <div className="client-name">{client.name}</div>
                <div className="client-classification">{client.classification}</div>
              </div>
              <div className="client-item-info">
                <span>{client.email}</span>
                <span>{client.phone}</span>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="no-clients">No clients found</div>
      )}
    </div>
  );
}

export default ClientList;