import { useState, useEffect } from 'react';
import axios from 'axios';
import { outputFormatOptions } from '../constants/businessOptions';

const assetTypeOptions = [
  { value: '', label: 'All asset types' },
  { value: 'generated_output', label: 'Generated outputs' },
];

const Gallery = () => {
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [assetType, setAssetType] = useState('');
  const [outputFormat, setOutputFormat] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const fetchAssets = async () => {
    setLoading(true);
    setError(null);

    try {
      const apiKey = localStorage.getItem('apiKey');
      if (!apiKey) {
        setError('Please enter your API key in the header');
        setLoading(false);
        return;
      }

      const response = await axios.get('/api/assets', {
        params: {
          search: search || undefined,
          asset_type: assetType || undefined,
          output_format: outputFormat || undefined,
          start_date: startDate || undefined,
          end_date: endDate || undefined,
        },
        headers: {
          'X-API-Key': apiKey,
        },
      });

      setAssets(response.data.assets || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to fetch gallery assets');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssets();
  }, []);

  const handleDelete = async (assetId) => {
    try {
      const apiKey = localStorage.getItem('apiKey');
      if (!apiKey) {
        setError('Please enter your API key in the header');
        return;
      }

      await axios.delete(`/api/assets/${assetId}`, {
        headers: {
          'X-API-Key': apiKey,
        },
      });

      setAssets((prev) => prev.filter((asset) => asset.id !== assetId));
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete asset');
    }
  };

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchAssets();
  };

  const clearFilters = () => {
    setSearch('');
    setAssetType('');
    setOutputFormat('');
    setStartDate('');
    setEndDate('');
    setError(null);
    fetchAssets();
  };

  return (
    <div className="gallery-container">
      <div className="card">
        <div className="card-title">📦 Asset Gallery</div>

        <form onSubmit={handleSearchSubmit} className="filter-row">
          <div className="form-group">
            <label htmlFor="search">Search</label>
            <input
              id="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by product, tag, or asset label"
            />
          </div>

          <div className="form-group">
            <label htmlFor="assetType">Asset type</label>
            <select id="assetType" value={assetType} onChange={(e) => setAssetType(e.target.value)}>
              {assetTypeOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="outputFormat">Output format</label>
            <select id="outputFormat" value={outputFormat} onChange={(e) => setOutputFormat(e.target.value)}>
              <option value="">All formats</option>
              {outputFormatOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="startDate">From</label>
            <input id="startDate" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </div>

          <div className="form-group">
            <label htmlFor="endDate">To</label>
            <input id="endDate" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </div>

          <div className="filter-actions">
            <button type="submit" className="primary-button">Apply filters</button>
            <button type="button" className="secondary-button" onClick={clearFilters}>Clear</button>
          </div>
        </form>

        {loading && (
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <div className="spinner"></div>
            <p style={{ marginTop: '16px', color: 'var(--text-dim)' }}>Loading assets...</p>
          </div>
        )}

        {!loading && assets.length === 0 && (
          <div className="empty-state">
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>🖼️</div>
            <p>No assets matched your filters yet.</p>
          </div>
        )}

        {!loading && assets.length > 0 && (
          <div className="image-grid">
            {assets.map((asset) => (
              <div key={asset.id} className="grid-item" style={{ position: 'relative' }}>
                <img
                  src={asset.asset_url}
                  alt={asset.label || 'Gallery asset'}
                  className="grid-image"
                  onClick={() => window.open(asset.asset_url, '_blank')}
                />
                <div className="asset-metadata">
                  <div className="asset-label">{asset.label || 'Generated asset'}</div>
                  <div className="asset-details">{asset.file_format?.toUpperCase()} · {asset.width}×{asset.height}</div>
                </div>
                <div className="asset-actions">
                  <button type="button" onClick={() => window.open(asset.asset_url, '_blank')} className="link-button">Download</button>
                  <button type="button" onClick={() => handleDelete(asset.id)} className="danger-button">Delete</button>
                </div>
              </div>
            ))}
          </div>
        )}

        {error && <div className="error-message">{error}</div>}
      </div>
    </div>
  );
};

export default Gallery;
