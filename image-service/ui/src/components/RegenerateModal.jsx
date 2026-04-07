import { useState } from 'react';

import { apiClient } from '../lib/apiClient';

const RegenerateModal = ({ asset, onClose, onSuccess }) => {
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [error, setError] = useState(null);

  const handleRegenerate = async () => {
    setIsRegenerating(true);
    setError(null);

    try {
      await apiClient.post(`/assets/${asset.id}/regenerate`);
      onSuccess();
      onClose();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Failed to regenerate asset');
    } finally {
      setIsRegenerating(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal">
        <div className="modal-header">
          <h3>Regenerate Asset</h3>
          <button className="modal-close" onClick={onClose}>
            &times;
          </button>
        </div>
        <div className="modal-body">
          <p>Are you sure you want to regenerate this asset? This will create a new version while keeping the original.</p>
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
          <button className="secondary-button" onClick={onClose} disabled={isRegenerating}>
            Cancel
          </button>
          <button className="primary-button" onClick={handleRegenerate} disabled={isRegenerating}>
            {isRegenerating ? 'Regenerating...' : 'Regenerate'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default RegenerateModal;
