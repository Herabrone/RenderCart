import { useEffect, useState } from 'react';

import { apiClient } from '../lib/apiClient';

const JobStatus = ({ jobId, onImagesGenerated, onStatusChange }) => {
  const [status, setStatus] = useState('pending');
  const [progress, setProgress] = useState(0);
  const [step, setStep] = useState('');
  const [error, setError] = useState(null);

  useEffect(() => {
    let intervalId;

    const handleResponse = (data) => {
      setStatus(data.status);
      setProgress(data.progress || 0);
      setStep(data.step || '');
      setError(null);

      if (onStatusChange) {
        onStatusChange(data);
      }

      const images = data.result_urls || data.output_urls || [];
      if (images.length > 0 && onImagesGenerated) {
        onImagesGenerated(images);
      }

      if (data.status === 'failed' || data.status === 'completed') {
        clearInterval(intervalId);
      }
    };

    const fetchStatus = async () => {
      try {
        const response = await apiClient.get(`/v1/job/${jobId}`);
        handleResponse(response.data);
      } catch {
        try {
          const response = await apiClient.get(`/job/${jobId}`);
          handleResponse(response.data);
        } catch (innerError) {
          setError(innerError.response?.data?.detail || 'Failed to fetch job status');
          clearInterval(intervalId);
        }
      }
    };

    fetchStatus();
    intervalId = setInterval(fetchStatus, 2000);

    return () => clearInterval(intervalId);
  }, [jobId, onImagesGenerated, onStatusChange]);

  return (
    <div className="job-status">
      <div className="status-header" style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
        <span className="status-label" style={{ fontSize: '14px', color: 'var(--text-dim)' }}>Status:</span>
        <span className={`status-badge status-${status}`}>{status}</span>
      </div>

      {(status === 'processing' || status === 'pending') && (
        <div className="progress-container">
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${progress || 5}%` }} />
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-dim)', textAlign: 'right' }}>
            {status === 'processing'
              ? step
                ? `${progress}% complete - ${step}`
                : `${progress}% complete`
              : 'Initializing...'}
          </div>
        </div>
      )}

      {status === 'failed' && <div className="error-message">Generation failed. Please try again.</div>}
      {error && <div className="error-message">{error}</div>}
    </div>
  );
};

export default JobStatus;
