import { useState, useEffect } from 'react';
import axios from 'axios';

const JobStatus = ({ jobId, onImagesGenerated }) => {
  const [status, setStatus] = useState('pending');
  const [progress, setProgress] = useState(0);
  const [step, setStep] = useState('');
  const [error, setError] = useState(null);
  
  useEffect(() => {
    let interval;
    
    const fetchStatus = async () => {
      try {
        const response = await axios.get(`/api/job/${jobId}`);

        setStatus(response.data.status);
        setProgress(response.data.progress || 0);
        setStep(response.data.step || '');
        
        // Use result_urls if available, otherwise fall back to output_urls
        const images = response.data.result_urls || response.data.output_urls || [];
        if (images && images.length > 0) {
          onImagesGenerated(images);
        }
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to fetch job status');
      }
    };

    fetchStatus();
    interval = setInterval(fetchStatus, 2000);

    return () => clearInterval(interval);
  }, [jobId, onImagesGenerated]);

  return (
    <div className="job-status">
      <div className="status-header" style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
        <span className="status-label" style={{ fontSize: '14px', color: 'var(--text-dim)' }}>Status:</span>
        <span className={`status-badge status-${status}`}>{status}</span>
      </div>
      
      {(status === 'processing' || status === 'pending') && (
        <div className="progress-container">
          <div className="progress-track">
            <div
              className="progress-fill"
              style={{ width: `${progress || 5}%` }}
            />
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-dim)', textAlign: 'right' }}>
            {status === 'processing' ?
              step ?
                `${progress}% complete - ${step}` :
                `${progress}% complete` :
              'Initializing...'}
          </div>
        </div>
      )}
      
      {status === 'failed' && <div className="error-message">Generation failed. Please try again.</div>}
      
      {error && <div className="error-message">{error}</div>}
    </div>
  );
};

export default JobStatus;