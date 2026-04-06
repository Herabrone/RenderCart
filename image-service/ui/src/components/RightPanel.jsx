const RightPanel = ({ previewImage, generatedImages, jobStatus }) => {
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
              {generatedImages.length > 0 ? (
                <img src={generatedImages[0]} alt="Generated preview" className="preview-image" />
              ) : (
                <div className="preview-empty">Generated results appear here</div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="panel-card panel-card--secondary" id="batch-jobs">
        <div className="panel-title">Batch jobs & export</div>
        <p className="panel-copy">
          Generated assets are ready to download or export to your commerce workflow.
        </p>
      </div>

      <div className="panel-card panel-card--results">
        <div className="panel-title">Generation preview grid</div>
        {generatedImages.length > 0 ? (
          <div className="result-grid">
            {generatedImages.map((image, index) => (
              <div key={index} className="result-item">
                <img src={image} alt={`Generated ${index + 1}`} className="result-thumb" />
                <button
                  className="download-button"
                  onClick={() => window.open(image, '_blank')}
                >
                  Download
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <p>No generated assets yet. Start a generation to preview results.</p>
          </div>
        )}
      </div>

      <div className="panel-card panel-card--secondary" id="pricing">
        <div className="panel-title">Pricing / Usage</div>
        <p className="panel-copy">
          Track how many product images and marketing assets are generated, with preview and production mode distinctions.
        </p>
      </div>

      <div className="panel-card panel-card--secondary" id="integrations">
        <div className="panel-title">Integrations</div>
        <p className="panel-copy">
          Future-ready architecture for Shopify, brand stores, and export target workflows.
        </p>
      </div>
    </section>
  );
};

export default RightPanel;
