import { useState } from 'react';

const RightPanel = ({ previewImage, generatedImages, jobStatus }) => {
  const [exporting, setExporting] = useState(false);
  const [exported, setExported] = useState(false);

  const handleExportToStockman = async () => {
    setExporting(true);
    // Mock the external call to Stockman app
    setTimeout(() => {
      setExporting(false);
      setExported(true);
      setTimeout(() => setExported(false), 3000);
    }, 1500);
  };

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
        <div className="panel-title">Asset variants & export</div>
        {generatedImages && generatedImages.length > 0 ? (
          <div>
            <div className="result-grid">
              {generatedImages.map((image, index) => (
                <div key={index} className="result-item">
                  <img src={image} alt={`Generated ${index + 1}`} className="result-thumb" />
                  <div className="result-actions">
                    <button
                      className="download-button"
                      onClick={() => window.open(image, '_blank')}
                    >
                      Download HD
                    </button>
                    <button
                      className="generate-button"
                      style={{ width: '100%', marginTop: '8px' }}
                      onClick={handleExportToStockman}
                      disabled={exporting}
                    >
                      {exporting ? 'Syncing...' : exported ? '✓ Pushed to Shopify' : 'Send to Stockman'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="empty-state">
            <p>No generated assets yet. Start a generation to preview results.</p>
          </div>
        )}
      </div>

      <div className="panel-card panel-card--secondary" id="integrations" style={{ marginTop: '20px' }}>
        <div className="panel-title">Integrations (Stockman App)</div>
        <p className="panel-copy">
          This generation pipeline will connect directly to your Shopify store via <b>Stockman</b>. Webhooks and v1 APIs are enabled so merchants can generate photos directly inside the Shopify admin panel.
        </p>
      </div>
    </section>
  );
};

export default RightPanel;
