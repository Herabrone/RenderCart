import { useState } from 'react';

import BrandKitManager from './BrandKitManager';
import ImageUpload from './ImageUpload';
import GenerateForm from './GenerateForm';

const LeftPanel = ({
  uploadedImages,
  onImageUpload,
  onJobCreated,
  onBatchCreated,
  onStatusChange,
}) => {
  const [appliedBrandKit, setAppliedBrandKit] = useState(null);

  return (
    <section className="left-panel">
      <div className="panel-card panel-card--primary" id="assets">
        <div className="panel-title">Create store-ready visuals</div>
        <p className="panel-copy">
          Upload your product image, choose the merchant use case, and configure brand-friendly output
          options for listings, ads, and social content.
        </p>

        <div className="panel-section">
          <div className="panel-subtitle">Upload product images</div>
          <ImageUpload onImageUpload={onImageUpload} />
        </div>

        <div className="panel-section">
          <div className="panel-subtitle">Build your visual brief</div>
          <GenerateForm
            uploadedImages={uploadedImages}
            onJobCreated={onJobCreated}
            onBatchCreated={onBatchCreated}
            onStatusChange={onStatusChange}
            appliedBrandKit={appliedBrandKit}
          />
        </div>
      </div>

      <div className="panel-card panel-card--secondary" id="brand-styles">
        <div className="panel-title">Brand styles and presets</div>
        <p className="panel-copy">
          Save time by focusing on product image type, brand tone, and output format instead of raw model settings.
        </p>
        <BrandKitManager onApply={(brandKit) => setAppliedBrandKit({ ...brandKit, appliedAt: Date.now() })} />
      </div>
    </section>
  );
};

export default LeftPanel;
