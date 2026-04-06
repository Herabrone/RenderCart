import { useState } from 'react';

import {
  generationModeOptions,
  outputFormatOptions,
  presetOptions,
  productCategoryOptions,
  useCaseOptions,
} from '../constants/businessOptions';
import { apiClient } from '../lib/apiClient';

const GenerateForm = ({ uploadedImages = [], onJobCreated, onBatchCreated, onStatusChange }) => {
  const [prompt, setPrompt] = useState('');
  const [useCase, setUseCase] = useState('main_product_image');
  const [productCategory, setProductCategory] = useState('general');
  const [brandStyle, setBrandStyle] = useState('clean and modern');
  const [presetId, setPresetId] = useState('realvisxl_default');
  const [outputFormat, setOutputFormat] = useState('product_image');
  const [mode, setMode] = useState('production');
  const [numOutputs, setNumOutputs] = useState(1);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!uploadedImages || uploadedImages.length === 0) {
      setError('Upload at least one product image to start generating store visuals.');
      return;
    }

    if (!prompt.trim()) {
      setError('Describe the shopping experience and product details.');
      return;
    }

    setGenerating(true);
    setError(null);

    const isBatch = uploadedImages.length > 1;
    const payloadBase = {
      prompt,
      preset_id: presetId,
      use_case: useCase,
      product_category: productCategory,
      brand_style: brandStyle,
      output_format: outputFormat,
      mode,
      num_outputs: numOutputs,
      metadata: { source: 'ui' },
    };

    try {
      if (isBatch) {
        const response = await apiClient.post('/batch/generate', {
          ...payloadBase,
          items: uploadedImages.map((item) => ({
            image_url: item.url,
            label: item.name,
            input_file_name: item.name,
          })),
        });

        if (onBatchCreated) {
          onBatchCreated(response.data.batch_id);
        }
        if (onStatusChange) {
          onStatusChange({ status: 'pending', step: 'queued', batchId: response.data.batch_id });
        }
      } else {
        const response = await apiClient.post('/generate', {
          image_url: uploadedImages[0].url,
          ...payloadBase,
        });

        if (onJobCreated) {
          onJobCreated(response.data.job_id);
        }
        if (onStatusChange) {
          onStatusChange({ status: 'pending', step: 'queued' });
        }
      }
    } catch (requestError) {
      setError(requestError.response?.data?.detail || requestError.message || 'Generation failed. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="generate-form">
      <div className="form-group">
        <label htmlFor="prompt">Product description</label>
        <textarea
          id="prompt"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="e.g. Bright lifestyle shot of a ceramic mug on a marble counter, soft natural light"
          rows={4}
        />
        <div className="note-text">Focus on product purpose, mood, and selling context.</div>
      </div>

      <div className="form-grid">
        <div className="form-group">
          <label htmlFor="useCase">Use case</label>
          <select id="useCase" value={useCase} onChange={(event) => setUseCase(event.target.value)}>
            {useCaseOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="productCategory">Product category</label>
          <select id="productCategory" value={productCategory} onChange={(event) => setProductCategory(event.target.value)}>
            {productCategoryOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="form-group">
        <label htmlFor="brandStyle">Brand style</label>
        <input
          id="brandStyle"
          value={brandStyle}
          onChange={(event) => setBrandStyle(event.target.value)}
          placeholder="e.g. minimalist premium lifestyle"
        />
      </div>

      <div className="form-grid">
        <div className="form-group">
          <label htmlFor="presetId">Export preset</label>
          <select id="presetId" value={presetId} onChange={(event) => setPresetId(event.target.value)}>
            {presetOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="outputFormat">Output format</label>
          <select id="outputFormat" value={outputFormat} onChange={(event) => setOutputFormat(event.target.value)}>
            {outputFormatOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </div>
      </div>

      <button type="button" className="link-button" onClick={() => setShowAdvanced(!showAdvanced)}>
        {showAdvanced ? 'Hide advanced settings' : 'Show advanced settings'}
      </button>

      {showAdvanced && (
        <div className="advanced-panel">
          <div className="form-grid">
            <div className="form-group">
              <label htmlFor="mode">Generation mode</label>
              <select id="mode" value={mode} onChange={(event) => setMode(event.target.value)}>
                {generationModeOptions.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="numOutputs">Number of assets</label>
              <input
                type="range"
                id="numOutputs"
                min="1"
                max="4"
                step="1"
                value={numOutputs}
                onChange={(event) => setNumOutputs(parseInt(event.target.value, 10))}
              />
              <div className="range-value">{numOutputs} assets</div>
            </div>
          </div>
          <div className="note-text">Preview mode is faster and lower cost; production mode is optimized for final marketing assets.</div>
        </div>
      )}

      <button type="submit" className="generate-button" disabled={generating || !uploadedImages || uploadedImages.length === 0}>
        {generating ? 'Creating images...' : uploadedImages.length > 1 ? 'Generate batch visuals' : 'Generate product visuals'}
      </button>

      {error && <div className="error-message">{error}</div>}
    </form>
  );
};

export default GenerateForm;
