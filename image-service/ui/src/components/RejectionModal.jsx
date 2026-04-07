import { useState } from 'react';

import { apiClient } from '../lib/apiClient';

const RejectionModal = ({ asset, onClose, onSuccess }) => {
  const [rejectionReason, setRejectionReason] = useState('');
  const [isRejecting, setIsRejecting] = useState(false);
  const [error, setError] = useState(null);

  const handleReject = async () => {
    if (!rejectionReason.trim()) {
      setError('Please provide a reason for rejection');
      return;
    }

    setIsRejecting(true);
    setError(null);

    try {
      await apiClient.post(`/assets/${asset.id}/reject`, { reason: rejectionReason });
      onSuccess();
      onClose();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Failed to reject asset');
    } finally {
      setIsRejecting(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal">
        <div className="modal-header">
          <h3>Reject Asset</h3>
          <button className="modal-close" onClick={onClose}>
            &times;
          </button>
        </div>
        <div className="modal-body">
          <p>Are you sure you want to reject this asset? Please provide a reason.</p>
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
          <div className="form-group">
            <label htmlFor="rejectionReason">Reason for rejection</label>
            <textarea
              id="rejectionReason"
              value={rejectionReason}
              onChange={(event) => setRejectionReason(event.target.value)}
              placeholder="Enter reason for rejection..."
              rows={4}
            />
          </div>
          {error && (
            <p className="error-message">{error}</p>
          )}
        </div>
        <div className="modal-footer">
          <button className="secondary-button" onClick={onClose} disabled={isRejecting}>
            Cancel
          </button>
          <button className="danger-button" onClick={handleReject} disabled={isRejecting}>
            {isRejecting ? 'Rejecting...' : 'Reject'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default RejectionModal;
