import { useCallback, useEffect, useState } from 'react';

import { apiClient, downloadWithAuth } from '../lib/apiClient';

const BatchStatus = ({ batchId, onStatusChange }) => {
  const [status, setStatus] = useState('pending');
  const [progress, setProgress] = useState(0);
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState(null);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState(null);

  const fetchBatch = useCallback(async () => {
    try {
      const response = await apiClient.get(`/batch/${batchId}`);
      setStatus(response.data.status || 'pending');
      setProgress(response.data.progress || 0);
      setItems(response.data.items || []);
      setError(null);
      setRetryError(null);

      if (onStatusChange) {
        onStatusChange(response.data);
      }

      return response.data;
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Unable to load batch status.');
      return null;
    }
  }, [batchId, onStatusChange]);

  useEffect(() => {
    let intervalId;

    const refresh = async () => {
      const result = await fetchBatch();
      if (result && (result.status === 'completed' || result.status === 'failed')) {
        clearInterval(intervalId);
      }
    };

    refresh();
    intervalId = setInterval(refresh, 2000);

    return () => clearInterval(intervalId);
  }, [fetchBatch]);

  const handleRetryFailed = async () => {
    setRetrying(true);
    setRetryError(null);
    try {
      await apiClient.post(`/batch/${batchId}/retry-failed`, { keep_item_labels: true });
      await fetchBatch();
    } catch (requestError) {
      setRetryError(requestError.response?.data?.detail || 'Retry failed.');
    } finally {
      setRetrying(false);
    }
  };

  const handleDownloadBatch = async () => {
    setDownloading(true);
    setDownloadError(null);
    try {
      const response = await downloadWithAuth(`/batch/${batchId}/download`);
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || 'Download failed.');
      }

      const blob = await response.blob();
      const contentDisposition = response.headers.get('content-disposition');
      const fileNameMatch = contentDisposition && contentDisposition.match(/filename="?(.+?)"?/);
      const fileName = fileNameMatch ? fileNameMatch[1] : `${batchId}.zip`;
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', fileName);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (requestError) {
      setDownloadError(requestError.message || 'Download failed.');
    } finally {
      setDownloading(false);
    }
  };

  const failedItemsCount = items.filter((item) => item.status === 'failed').length;
  const hasDownloadableAssets = items.some((item) => item.output_urls && item.output_urls.length > 0);

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

      {failedItemsCount > 0 && (
        <div className="retry-panel" style={{ marginTop: '16px' }}>
          <button type="button" className="generate-button" onClick={handleRetryFailed} disabled={retrying}>
            {retrying ? 'Retrying failed items...' : `Retry ${failedItemsCount} failed item${failedItemsCount === 1 ? '' : 's'}`}
          </button>
          {retryError && <div className="error-message" style={{ marginTop: '10px' }}>{retryError}</div>}
        </div>
      )}

      {hasDownloadableAssets && (
        <div className="download-panel" style={{ marginTop: '16px' }}>
          <button type="button" className="generate-button" onClick={handleDownloadBatch} disabled={downloading}>
            {downloading ? 'Downloading batch...' : 'Download batch ZIP'}
          </button>
          {downloadError && <div className="error-message" style={{ marginTop: '10px' }}>{downloadError}</div>}
        </div>
      )}

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
                  {item.error && <span style={{ color: '#d32f2f', marginLeft: '10px' }}>Failed</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {error && <div className="error-message" style={{ marginTop: '12px' }}>{error}</div>}
    </div>
  );
};

export default BatchStatus;
