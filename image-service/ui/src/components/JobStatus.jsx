import { useState, useEffect } from 'react';
import axios from 'axios';

const JobStatus = ({ jobId, onImagesGenerated }) => {
  const [status, setStatus] = useState('pending');
  const [progress, setProgress] = useState(0);
  const [images, setImages] = useState([]);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    let interval;
    
    const fetchStatus = async () => {
      try {
        const response = await axios.get(`/api/job/${jobId}`);

        setStatus(response.data.status);
        setProgress(response.data.progress || 0);
        
        if (response.data.images && response.data.images.length > 0) {
          setImages(response.data.images);
          onImagesGenerated(response.data.images);
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
      <div className="status-header">
        <span className="status-label">Job Status:</span>
        <span className={`status-text ${status}`}>{status}</span>
      </div>
      
      {status === 'processing' && (
        <div className="progress-container">
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="progress-text">{progress}%</span>
        </div>
      )}
      
      {status === 'completed' && images.length > 0 && (
        <div className="results-grid">
          {images.map((image, index) => (
            <div key={index} className="result-item">
              <img src={image} alt={`Generated image ${index + 1}`} className="result-image" />
            </div>
          ))}
        </div>
      )}
      
      {error && <div className="error-message">{error}</div>}
    </div>
  );
};

export default JobStatus;