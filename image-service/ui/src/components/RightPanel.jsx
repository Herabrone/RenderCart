import { useState } from 'react';

import PublishModal from './PublishModal';
import BulkPublishModal from './BulkPublishModal';
import PublishStatus from './PublishStatus';

const RightPanel = ({ previewImage, generatedImages, batchStatus, uploadedImages, stores }) => {
  const [showPublishModal, setShowPublishModal] = useState(false);
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [selectedAssetForPublish, setSelectedAssetForPublish] = useState(null);
  const [publishingAssets, setPublishingAssets] = useState({});
  const [selectedAssetIds, setSelectedAssetIds] = useState(new Set());

  const normalizedGeneratedImages = Array.isArray(generatedImages)
    ? generatedImages.map((image) => (typeof image === 'string' ? { asset_url: image, approval_status: 'pending' } : image))
    : [];

  const approvedAssets = normalizedGeneratedImages.filter((a) => a.approval_status === 'approved' && a.id);

  const toggleAssetSelection = (assetId) => {
    setSelectedAssetIds((prev) => {
      const next = new Set(prev);
      if (next.has(assetId)) {
        next.delete(assetId);
      } else {
        next.add(assetId);
      }
      return next;
    });
  };

  const handlePublishClick = (asset) => {
    if (!stores || stores.length === 0) {
      alert('Please connect a Shopify store first');
      return;
    }
    setSelectedAssetForPublish(asset);
    setShowPublishModal(true);
  };

  const handlePublishSuccess = () => {
    if (selectedAssetForPublish) {
      setPublishingAssets((prev) => ({
        ...prev,
        [selectedAssetForPublish.id || selectedAssetForPublish.asset_url]: true,
      }));
    }
    setShowPublishModal(false);
  };

  const handleBulkPublishSuccess = (result) => {
    const queued = new Set(result.queued || []);
    setPublishingAssets((prev) => {
      const next = { ...prev };
      for (const id of queued) {
        next[id] = true;
      }
      return next;
    });
    setSelectedAssetIds(new Set());
    setShowBulkModal(false);
  };

  const handlePublishComplete = (assetKey) => {
    setPublishingAssets((prev) => {
      const updated = { ...prev };
      delete updated[assetKey];
      return updated;
    });
  };

  const selectedBulkAssets = approvedAssets.filter((a) => selectedAssetIds.has(a.id));

  return (
    <section className="right-panel">
      <div className="panel-card panel-card--preview">
        <div className="panel-title">Live preview</div>
        <div className="preview-grid">
          <div className="preview-card">
            <div className="preview-card-label">Before</div>
            <div className="preview-frame">
              {previewImage ? (
                <img src={previewImage} alt="Uploaded product" className="preview-image" />
              ) : (
                <div className="preview-empty">Upload a product image to begin</div>
              )}
            </div>
          </div>

          <div className="preview-card">
            <div className="preview-card-label">After</div>
            <div className="preview-frame">
              {normalizedGeneratedImages && normalizedGeneratedImages.length > 0 ? (
                <img src={normalizedGeneratedImages[0].asset_url} alt="Generated preview" className="preview-image" />
              ) : (
                <div className="preview-empty">Generated results appear here</div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="panel-card panel-card--results" style={{ marginTop: '20px' }}>
        <div className="results-header">
          <div className="panel-title">Asset variants</div>
          {selectedAssetIds.size > 0 && (
            <button
              type="button"
              className="primary-button primary-button--sm"
              onClick={() => setShowBulkModal(true)}
            >
              Publish {selectedAssetIds.size} selected
            </button>
          )}
        </div>

        {normalizedGeneratedImages && normalizedGeneratedImages.length > 0 ? (
          <div className="result-grid">
            {normalizedGeneratedImages.map((result, index) => {
              const assetKey = result.id || result.asset_url;
              const isPublishing = publishingAssets[assetKey];
              const isSelected = result.id && selectedAssetIds.has(result.id);

              return (
                <div
                  key={assetKey || index}
                  className={`result-item${isSelected ? ' result-item--selected' : ''}`}
                >
                  {result.approval_status === 'approved' && result.id && (
                    <label className="result-select-label">
                      <input
                        type="checkbox"
                        className="result-select-checkbox"
                        checked={isSelected}
                        onChange={() => toggleAssetSelection(result.id)}
                        disabled={isPublishing}
                      />
                    </label>
                  )}
                  <img src={result.asset_url} alt={`Generated ${index + 1}`} className="result-thumb" />
                  <div className="result-actions">
                    <button
                      type="button"
                      className="download-button"
                      onClick={() => window.open(result.asset_url, '_blank')}
                    >
                      Download
                    </button>
                    {result.approval_status === 'approved' && (
                      <button
                        type="button"
                        className="primary-button primary-button--sm"
                        onClick={() => handlePublishClick(result)}
                        disabled={isPublishing}
                      >
                        {isPublishing ? 'Publishing...' : 'Publish'}
                      </button>
                    )}
                  </div>
                  <div className="result-status">
                    {result.approval_status === 'approved' && <span className="status-badge approved">âœ“ Approved</span>}
                    {result.approval_status === 'rejected' && <span className="status-badge rejected">âœ— Rejected</span>}
                    {result.approval_status === 'pending' && <span className="status-badge pending">â³ Pending</span>}
                    {!['approved', 'rejected', 'pending'].includes(result.approval_status) && (
                      <span className="status-badge pending">{result.approval_status || 'Pending'}</span>
                    )}
                  </div>

                  {isPublishing && (
                    <div className="publish-status-inline">
                      <PublishStatus
                        assetId={result.id}
                        onComplete={() => handlePublishComplete(assetKey)}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : batchStatus ? (
          <div className="empty-state">
            <p>Batch submitted with {batchStatus.total_items} items.</p>
            <p>{batchStatus.completed_items} completed, {batchStatus.pending_items} pending, {batchStatus.failed_items} failed.</p>
          </div>
        ) : uploadedImages && uploadedImages.length > 1 ? (
          <div className="empty-state">
            <p>{uploadedImages.length} images ready for batch generation.</p>
            <p>Click Generate to submit the batch.</p>
          </div>
        ) : (
          <div className="empty-state">
            <p>No generated assets yet. Start a generation to preview results.</p>
          </div>
        )}
      </div>

      <div className="panel-card panel-card--secondary" id="integrations" style={{ marginTop: '20px' }}>
        <div className="panel-title">Integration status</div>
        <p className="panel-copy">
          {stores && stores.length > 0
            ? `You have ${stores.length} Shopify store(s) connected. Approved assets can be published directly.`
            : 'Connect a Shopify store to publish assets. Go to "Shopify Stores" on the left to get started.'}
        </p>
      </div>

      {showPublishModal && selectedAssetForPublish && (
        <PublishModal
          asset={selectedAssetForPublish}
          stores={stores || []}
          onClose={() => setShowPublishModal(false)}
          onSuccess={handlePublishSuccess}
        />
      )}

      {showBulkModal && selectedBulkAssets.length > 0 && (
        <BulkPublishModal
          assets={selectedBulkAssets}
          stores={stores || []}
          onClose={() => setShowBulkModal(false)}
          onSuccess={handleBulkPublishSuccess}
        />
      )}
    </section>
  );
};

export default RightPanel;
