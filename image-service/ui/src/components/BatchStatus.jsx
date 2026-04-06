import { useEffect, useState } from 'react';
import axios from 'axios';

const BatchStatus = ({ batchId, onStatusChange }) => {
  const [status, setStatus] = useState('pending');
  const [progress, setProgress] = useState(0);
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let interval;
    const fetchBatch = async () => {
      try {
        const apiKey = localStorage.getItem('apiKey');
        const response = await axios.get(`/api/batch/${batchId}`, {
          headers: {
            ...(apiKey && { 'X-API-Key': apiKey }),
          },
        });

        setStatus(response.data.status || 'pending');
        setProgress(response.data.progress || 0);
        setItems(response.data.items || []);
        setError(null);

        if (onStatusChange) {
          onStatusChange(response.data);
        }

        if (response.data.status === 'completed' || response.data.status === 'failed') {
          clearInterval(interval);
        }
      } catch (err) {
        setError(err.response?.data?.detail || 'Unable to load batch status.');
        clearInterval(interval);
      }
    };

    fetchBatch();
    interval = setInterval(fetchBatch, 2000);

    return () => clearInterval(interval);
  }, [batchId, onStatusChange]);

  return (
    <div className="batch-status">
      <div className="status-header" style={{ marginBottom: '14px' }}>
        <span className="status-label">Batch ID</span>
        <span className="status-value">{batchId}</span>
      </div>
      <div className="status-summary" style={{ marginBottom: '16px' }}>
        <div className="status-row">Status: <strong>{status}</strong></div>
        <div className="status-row">Progress: <strong>{progress}%</strong></div>
      </div>

      <div className="progress-container">
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${progress || 5}%` }} />
        </div>
      </div>

      {items.length > 0 && (
        <div className="batch-items" style={{ marginTop: '18px' }}>
          <div className="panel-title" style={{ marginBottom: '12px' }}>Batch items</div>
          {items.map((item) => {
            const label = item.label || (typeof item.item_index === 'number' ? `Item ${item.item_index + 1}` : item.job_id);
            return (
              <div key={item.job_id} className="batch-item">
                <div className="batch-item-main">
                  <div className="batch-item-label">{label}</div>
                  <div className={`status-badge status-${item.status}`}>{item.status}</div>
                </div>
              <div className="batch-item-meta">
                <span>Progress: {item.progress}%</span>
                {item.error && <span style={{ color: '#d32f2f' }}>Failed</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {error && <div className="error-message" style={{ marginTop: '12px' }}>{error}</div>}
    </div>
  );
};

export default BatchStatus;
