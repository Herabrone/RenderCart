import { useState } from 'react';
import axios from 'axios';
import {
  useCaseOptions,
  productCategoryOptions,
  outputFormatOptions,
  generationModeOptions,
} from '../constants/businessOptions';

const GenerateForm = ({ imageUrl, onJobCreated, onStatusChange }) => {
  const [prompt, setPrompt] = useState('');
  const [useCase, setUseCase] = useState('main_product_image');
  const [productCategory, setProductCategory] = useState('general');
  const [brandStyle, setBrandStyle] = useState('clean and modern');
  const [outputFormat, setOutputFormat] = useState('product_image');
  const [mode, setMode] = useState('production');
  const [numOutputs, setNumOutputs] = useState(1);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  
  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!imageUrl) {
      setError('Upload a product image to start generating store visuals.');
      return;
    }

    if (!prompt.trim()) {
      setError('Describe the shopping experience and product details.');
      return;
    }

    setGenerating(true);
    setError(null);

    try {
      const apiKey = localStorage.getItem('apiKey');
      const response = await axios.post(
        '/api/generate',
        {
          image_url: imageUrl,
          prompt,
          preset_id: 'realvisxl_default',
          use_case: useCase,
          product_category: productCategory,
          brand_style: brandStyle,
          output_format: outputFormat,
          mode,
          num_outputs: numOutputs,
          metadata: {
            source: 'ui',
          },
        },
        {
          headers: {
            ...(apiKey && { 'X-API-Key': apiKey }),
          },
        }
      );

      onJobCreated(response.data.job_id);
      if (onStatusChange) {
        onStatusChange({ status: 'pending', step: 'queued' });
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Generation failed. Please try again.');
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
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="e.g. Bright lifestyle shot of a ceramic mug on a marble counter, soft natural light"
          rows={4}
        />
        <div className="note-text">Focus on product purpose, mood, and selling context.</div>
      </div>

      <div className="form-grid">
        <div className="form-group">
          <label htmlFor="useCase">Use case</label>
          <select id="useCase" value={useCase} onChange={(e) => setUseCase(e.target.value)}>
            {useCaseOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="productCategory">Product category</label>
          <select id="productCategory" value={productCategory} onChange={(e) => setProductCategory(e.target.value)}>
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
          onChange={(e) => setBrandStyle(e.target.value)}
          placeholder="e.g. minimalist premium lifestyle"
        />
      </div>

      <div className="form-group">
        <label htmlFor="outputFormat">Output format</label>
        <select id="outputFormat" value={outputFormat} onChange={(e) => setOutputFormat(e.target.value)}>
          {outputFormatOptions.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
      </div>

      <button type="button" className="link-button" onClick={() => setShowAdvanced(!showAdvanced)}>
        {showAdvanced ? 'Hide advanced settings' : 'Show advanced settings'}
      </button>

      {showAdvanced && (
        <div className="advanced-panel">
          <div className="form-grid">
            <div className="form-group">
              <label htmlFor="mode">Generation mode</label>
              <select id="mode" value={mode} onChange={(e) => setMode(e.target.value)}>
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
                onChange={(e) => setNumOutputs(parseInt(e.target.value, 10))}
              />
              <div className="range-value">{numOutputs} assets</div>
            </div>
          </div>
          <div className="note-text">Preview mode is faster and lower cost; production mode is optimized for final marketing assets.</div>
        </div>
      )}

      <button type="submit" className="generate-button" disabled={generating || !imageUrl}>
        {generating ? 'Creating images…' : 'Generate product visuals'}
      </button>

      {error && <div className="error-message">{error}</div>}
    </form>
  );
};

export default GenerateForm;