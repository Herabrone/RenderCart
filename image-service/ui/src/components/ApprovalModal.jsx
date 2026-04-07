import { useState } from 'react';

import { apiClient } from '../lib/apiClient';

const ApprovalModal = ({ asset, onClose, onSuccess }) => {
  const [isApproving, setIsApproving] = useState(false);
  const [error, setError] = useState(null);

  const handleApprove = async () => {
    setIsApproving(true);
    setError(null);

    try {
      await apiClient.post(`/assets/${asset.id}/approve`);
      onSuccess();
      onClose();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Failed to approve asset');
    } finally {
      setIsApproving(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal">
        <div className="modal-header">
          <h3>Approve Asset</h3>
          <button className="modal-close" onClick={onClose}>
            &times;
          </button>
        </div>
        <div className="modal-body">
          <p>Are you sure you want to approve this asset?</p>
          {asset.label && (
            <p className="asset-info">
              <strong>Label:</strong> {asset.label}
            </p>
          )}
          {asset.file_format && (
            <p className="asset-info">
              <strong>Format:</strong> {asset.file_format.toUpperCase()}
            </p>
          )}
          {error && (
            <p className="error-message">{error}</p>
          )}
        </div>
        <div className="modal-footer">
          <button className="secondary-button" onClick={onClose} disabled={isApproving}>
            Cancel
          </button>
          <button className="primary-button" onClick={handleApprove} disabled={isApproving}>
            {isApproving ? 'Approving...' : 'Approve'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ApprovalModal;
