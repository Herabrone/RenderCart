import { useState } from 'react';
import axios from 'axios';

const GenerateForm = ({ imageUrl, onJobCreated }) => {
  const [prompt, setPrompt] = useState('');
  const [style, setStyle] = useState('realistic');
  const [numOutputs, setNumOutputs] = useState(1);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!imageUrl) {
      setError('Please upload an image first');
      return;
    }

    if (!prompt.trim()) {
      setError('Please enter a prompt');
      return;
    }

    setGenerating(true);
    setError(null);
    
    try {
      const apiKey = localStorage.getItem('apiKey');
      const response = await axios.post('/api/generate', {
        image_url: imageUrl,
        prompt: prompt,
        style: style,
        num_outputs: numOutputs
      }, {
        headers: {
          ...(apiKey && { 'X-API-Key': apiKey })
        }
      });

      onJobCreated(response.data.job_id);
    } catch (err) {
      setError(err.response?.data?.detail || 'Generation failed. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="generate-form">
      <div className="form-group">
        <label htmlFor="prompt">Contextual Prompt</label>
        <textarea
          id="prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="e.g. On a wooden table in a high-end kitchen with natural morning light..."
          rows={3}
        />
        <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px' }}>
          Describe the background and lighting for the best results.
        </div>
      </div>
      
      <div className="form-group">
        <label htmlFor="style">Art Style</label>
        <select
          id="style"
          value={style}
          onChange={(e) => setStyle(e.target.value)}
        >
          <option value="realistic">📸 Realistic Photography</option>
          <option value="cartoon">🎨 Vibrant Cartoon</option>
          <option value="anime">✨ Stylized Anime</option>
          <option value="watercolor">🖌️ Artistic Watercolor</option>
          <option value="sketch">✏️ Graphite Sketch</option>
        </select>
      </div>
      
      <div className="form-group">
        <label htmlFor="numOutputs">Output Variations</label>
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <input
            type="range"
            id="numOutputs"
            min="1"
            max="4"
            step="1"
            value={numOutputs}
            onChange={(e) => setNumOutputs(parseInt(e.target.value))}
            style={{ flex: 1 }}
          />
          <span className="badge" style={{ 
            background: 'var(--bg-tertiary)', 
            padding: '4px 12px', 
            borderRadius: '4px',
            fontSize: '14px',
            fontWeight: '600',
            border: '1px solid var(--border)'
          }}>{numOutputs}</span>
        </div>
      </div>
      
      <button type="submit" className="btn-primary" disabled={generating || !imageUrl}>
        {generating ? (
          <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
            <span className="spinner"></span> Starting Generation...
          </span>
        ) : 'Initial Generation'}
      </button>
      
      {error && <div className="error-message">{error}</div>}
    </form>
  );
};

export default GenerateForm;