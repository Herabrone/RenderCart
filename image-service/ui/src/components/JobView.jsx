import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

import { apiClient } from '../lib/apiClient';
import ApprovalModal from './ApprovalModal';
import RejectionModal from './RejectionModal';
import RegenerateModal from './RegenerateModal';

const JobView = () => {
  const { jobId } = useParams();
  const navigate = useNavigate();
  
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [showRejectionModal, setShowRejectionModal] = useState(false);
  const [showRegenerateModal, setShowRegenerateModal] = useState(false);

  useEffect(() => {
    const fetchJob = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await apiClient.get(`/jobs/${jobId}`);
        setJob(response.data);
      } catch (requestError) {
        setError(requestError.response?.data?.detail || 'Failed to fetch job details');
      } finally {
        setLoading(false);
      }
    };

    fetchJob();
  }, [jobId]);

  const handleSuccess = () => {
    // Refresh job data after approval/rejection/regeneration
    const fetchJob = async () => {
      try {
        const response = await apiClient.get(`/jobs/${jobId}`);
        setJob(response.data);
      } catch (requestError) {
        setError(requestError.response?.data?.detail || 'Failed to refresh job details');
      }
    };

    fetchJob();
  };

  if (loading) {
    return (
      <div className="container">
        <div className="loading">Loading job details...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container">
        <div className="error">{error}</div>
        <button className="button" onClick={() => navigate('/jobs')}>
          Back to Jobs
        </button>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="container">
        <div className="error">Job not found</div>
        <button className="button" onClick={() => navigate('/jobs')}>
          Back to Jobs
        </button>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="job-view">
        <div className="job-header">
          <h1>Job #{job.id}</h1>
          <div className="job-status">
            <span className={`status-badge ${job.status}`}>{job.status}</span>
          </div>
        </div>

        <div className="job-details">
          <div className="job-info">
            <div className="info-row">
              <strong>Created:</strong> {new Date(job.created_at).toLocaleString()}
            </div>
            <div className="info-row">
              <strong>Updated:</strong> {new Date(job.updated_at).toLocaleString()}
            </div>
            <div className="info-row">
              <strong>Product:</strong> {job.product_name}
            </div>
            <div className="info-row">
              <strong>Variants:</strong> {job.variants.join(', ')}
            </div>
          </div>

          <div className="job-actions">
            {job.status === 'completed' && (
              <>
                <button
                  className="button primary"
                  onClick={() => setShowApprovalModal(true)}
                >
                  Approve
                </button>
                <button
                  className="button danger"
                  onClick={() => setShowRejectionModal(true)}
                >
                  Reject
                </button>
                <button
                  className="button secondary"
                  onClick={() => setShowRegenerateModal(true)}
                >
                  Regenerate
                </button>
              </>
            )}
            <button className="button" onClick={() => navigate('/jobs')}>
              Back to Jobs
            </button>
          </div>
        </div>

        <div className="job-outputs">
          <h2>Generated Assets</h2>
          <div className="assets-grid">
            {job.assets.map((asset) => (
              <div key={asset.id} className="asset-card">
                <div className="asset-image">
                  <img src={asset.preview_url} alt={asset.label} />
                </div>
                <div className="asset-info">
                  <h3>{asset.label}</h3>
                  <div className="asset-meta">
                    <span>{asset.file_format.toUpperCase()}</span>
                    <span>{asset.width}×{asset.height}</span>
                  </div>
                  <div className="asset-status">
                    <span className={`status-badge ${asset.approval_status}`}>
                      {asset.approval_status}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {showApprovalModal && (
        <ApprovalModal
          asset={job.assets[0]}
          onClose={() => setShowApprovalModal(false)}
          onSuccess={handleSuccess}
        />
      )}

      {showRejectionModal && (
        <RejectionModal
          asset={job.assets[0]}
          onClose={() => setShowRejectionModal(false)}
          onSuccess={handleSuccess}
        />
      )}

      {showRegenerateModal && (
        <RegenerateModal
          asset={job.assets[0]}
          onClose={() => setShowRegenerateModal(false)}
          onSuccess={handleSuccess}
        />
      )}
    </div>
  );
};

export default JobView;
