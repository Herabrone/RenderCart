import { useEffect, useState } from 'react';

import { getPublishStatus } from '../lib/apiClient';

const PublishStatus = ({ assetId, onStatusChange, onComplete }) => {
  const [status, setStatus] = useState('pending');
  const [error, setError] = useState(null);
  const [publishedAt, setPublishedAt] = useState(null);
  const [mediaId, setMediaId] = useState(null);

  useEffect(() => {
    let intervalId;
    let isMounted = true;

    const fetchStatus = async () => {
      try {
        const response = await getPublishStatus(assetId);
        const { shopify_publish_status, shopify_error_message, shopify_published_at, shopify_media_id } = response.data;

        if (!isMounted) return;

        setStatus(shopify_publish_status);
        setError(shopify_error_message);
        setPublishedAt(shopify_published_at);
        setMediaId(shopify_media_id);

        if (onStatusChange) {
          onStatusChange({
            status: shopify_publish_status,
            error: shopify_error_message,
            publishedAt: shopify_published_at,
            mediaId: shopify_media_id,
          });
        }

        if (
          (shopify_publish_status === 'succeeded' || shopify_publish_status === 'failed') &&
          onComplete
        ) {
          onComplete(shopify_publish_status === 'succeeded');
        }

        if (shopify_publish_status === 'succeeded' || shopify_publish_status === 'failed') {
          clearInterval(intervalId);
        }
      } catch (err) {
        if (!isMounted) return;
        setError(err.response?.data?.detail || 'Failed to fetch publish status');
        clearInterval(intervalId);
      }
    };

    fetchStatus();
    intervalId = setInterval(fetchStatus, 2000);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, [assetId, onStatusChange, onComplete]);

  if (status === 'pending') {
    return (
      <div className="publish-status">
        <div className="status-header">
          <span className="status-label">Status:</span>
          <span className="status-badge status-pending">⏳ Publishing...</span>
        </div>
        <div className="progress-container">
          <div className="progress-track">
            <div className="progress-fill" style={{ width: '50%' }} />
          </div>
          <p className="status-text">Please wait while your asset is being added to Shopify...</p>
        </div>
      </div>
    );
  }

  if (status === 'succeeded') {
    return (
      <div className="publish-status">
        <div className="status-header">
          <span className="status-label">Status:</span>
          <span className="status-badge status-succeeded">✓ Published</span>
        </div>
        {publishedAt && (
          <p className="status-text success">
            Successfully published on {new Date(publishedAt).toLocaleString()}
          </p>
        )}
        {mediaId && (
          <p className="status-text dim">
            Media ID: {mediaId}
          </p>
        )}
      </div>
    );
  }

  if (status === 'failed') {
    return (
      <div className="publish-status">
        <div className="status-header">
          <span className="status-label">Status:</span>
          <span className="status-badge status-failed">✗ Failed</span>
        </div>
        {error && (
          <div className="error-message">
            <p><strong>Error:</strong> {error}</p>
          </div>
        )}
        <p className="status-text dim">Check the error message above and try again.</p>
      </div>
    );
  }

  return null;
};

export default PublishStatus;
