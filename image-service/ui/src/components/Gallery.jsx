import { useCallback, useEffect, useState } from 'react';

import { outputFormatOptions } from '../constants/businessOptions';
import { apiClient } from '../lib/apiClient';

const assetTypeOptions = [
  { value: '', label: 'All asset types' },
  { value: 'generated_output', label: 'Generated outputs' },
];

const approvalStatusOptions = [
  { value: '', label: 'All statuses' },
  { value: 'pending', label: 'Pending approval' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
];

const emptyFilters = {
  search: '',
  assetType: '',
  outputFormat: '',
  startDate: '',
  endDate: '',
  approvalStatus: '',
};

const Gallery = () => {
  const [assets, setAssets] = useState([]);
  const [filters, setFilters] = useState(emptyFilters);
  const [submittedFilters, setSubmittedFilters] = useState(emptyFilters);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAssets = useCallback(async (activeFilters) => {
    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.get('/assets', {
        params: {
          search: activeFilters.search || undefined,
          asset_type: activeFilters.assetType || undefined,
          output_format: activeFilters.outputFormat || undefined,
          start_date: activeFilters.startDate || undefined,
          end_date: activeFilters.endDate || undefined,
          approval_status: activeFilters.approvalStatus || undefined,
        },
      });

      setAssets(response.data.assets || []);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Failed to fetch gallery assets');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAssets(submittedFilters);
  }, [fetchAssets, submittedFilters]);

  const handleDelete = async (assetId) => {
    try {
      await apiClient.delete(`/assets/${assetId}`);
      setAssets((previous) => previous.filter((asset) => asset.id !== assetId));
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Failed to delete asset');
    }
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    setSubmittedFilters(filters);
  };

  const clearFilters = () => {
    setFilters(emptyFilters);
    setSubmittedFilters(emptyFilters);
    setError(null);
  };

  return (
    <div className="gallery-container">
      <div className="card">
        <div className="card-title">Asset Gallery</div>

        <form onSubmit={handleSubmit} className="filter-row">
          <div className="form-group">
            <label htmlFor="search">Search</label>
            <input
              id="search"
              value={filters.search}
              onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
              placeholder="Search by product, tag, or asset label"
            />
          </div>

          <div className="form-group">
            <label htmlFor="assetType">Asset type</label>
            <select
              id="assetType"
              value={filters.assetType}
              onChange={(event) => setFilters((current) => ({ ...current, assetType: event.target.value }))}
            >
              {assetTypeOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="outputFormat">Output format</label>
            <select
              id="outputFormat"
              value={filters.outputFormat}
              onChange={(event) => setFilters((current) => ({ ...current, outputFormat: event.target.value }))}
            >
              <option value="">All formats</option>
              {outputFormatOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="approvalStatus">Approval status</label>
            <select
              id="approvalStatus"
              value={filters.approvalStatus}
              onChange={(event) => setFilters((current) => ({ ...current, approvalStatus: event.target.value }))}
            >
              {approvalStatusOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="startDate">From</label>
            <input
              id="startDate"
              type="date"
              value={filters.startDate}
              onChange={(event) => setFilters((current) => ({ ...current, startDate: event.target.value }))}
            />
          </div>

          <div className="form-group">
            <label htmlFor="endDate">To</label>
            <input
              id="endDate"
              type="date"
              value={filters.endDate}
              onChange={(event) => setFilters((current) => ({ ...current, endDate: event.target.value }))}
            />
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
                <div className="asset-status">
                  {asset.approval_status === 'approved' && <span className="status-badge approved">✓ Approved</span>}
                  {asset.approval_status === 'rejected' && <span className="status-badge rejected">✗ Rejected</span>}
                  {asset.approval_status === 'pending' && <span className="status-badge pending">⏳ Pending</span>}
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
