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
      const response = await axios.post('/api/generate', {
        image_url: imageUrl,
        prompt: prompt,
        style: style,
        num_outputs: numOutputs
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
        <label htmlFor="prompt">Prompt</label>
        <textarea
          id="prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Describe what you want to generate..."
          rows={3}
        />
      </div>
      
      <div className="form-group">
        <label htmlFor="style">Style</label>
        <select
          id="style"
          value={style}
          onChange={(e) => setStyle(e.target.value)}
        >
          <option value="realistic">Realistic</option>
          <option value="cartoon">Cartoon</option>
          <option value="anime">Anime</option>
          <option value="sketch">Sketch</option>
        </select>
      </div>
      
      <div className="form-group">
        <label htmlFor="numOutputs">Number of Outputs</label>
        <input
          type="range"
          id="numOutputs"
          min="1"
          max="4"
          value={numOutputs}
          onChange={(e) => setNumOutputs(parseInt(e.target.value))}
        />
        <span className="range-value">{numOutputs}</span>
      </div>
      
      <button type="submit" className="generate-button" disabled={generating || !imageUrl}>
        {generating ? 'Generating...' : 'Generate Images'}
      </button>
      
      {error && <div className="error-message">{error}</div>}
    </form>
  );
};

export default GenerateForm;