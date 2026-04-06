const RightPanel = ({ previewImage, generatedImages, batchStatus, uploadedImages }) => {
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
              {generatedImages && generatedImages.length > 0 ? (
                <img src={generatedImages[0]} alt="Generated preview" className="preview-image" />
              ) : (
                <div className="preview-empty">Generated results appear here</div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="panel-card panel-card--results" style={{ marginTop: '20px' }}>
        <div className="panel-title">Asset variants</div>
        {generatedImages && generatedImages.length > 0 ? (
          <div className="result-grid">
            {generatedImages.map((image, index) => (
              <div key={image} className="result-item">
                <img src={image} alt={`Generated ${index + 1}`} className="result-thumb" />
                <div className="result-actions">
                  <button
                    type="button"
                    className="download-button"
                    onClick={() => window.open(image, '_blank')}
                  >
                    Download
                  </button>
                </div>
              </div>
            ))}
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
          API-key based requests, webhook callbacks, and v1 job polling are now first-class parts of the app flow.
          Store connections should build on top of those real endpoints rather than temporary client-side mocks.
        </p>
      </div>
    </section>
  );
};

export default RightPanel;
