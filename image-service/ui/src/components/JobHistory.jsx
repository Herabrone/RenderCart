import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { outputFormatOptions } from '../constants/businessOptions';

const statusOptions = [
  { value: '', label: 'All statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'processing', label: 'Processing' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
];

const JobHistory = () => {
  const [mode, setMode] = useState('jobs');
  const [jobs, setJobs] = useState([]);
  const [batches, setBatches] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [selectedBatch, setSelectedBatch] = useState(null);
  const [search, setSearch] = useState('');
  const [outputFormat, setOutputFormat] = useState('');
  const [status, setStatus] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [downloadError, setDownloadError] = useState(null);
  const [downloading, setDownloading] = useState(false);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const apiKey = localStorage.getItem('apiKey');
      if (!apiKey) {
        setError('Please enter your API key in the header');
        setLoading(false);
        return;
      }

      const response = await axios.get('/api/jobs', {
        params: {
          search: search || undefined,
          output_format: outputFormat || undefined,
          status: status || undefined,
          start_date: startDate || undefined,
          end_date: endDate || undefined,
        },
        headers: {
          'X-API-Key': apiKey,
        },
      });

      setJobs(response.data.jobs || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load job history');
    } finally {
      setLoading(false);
    }
  }, [search, outputFormat, status, startDate, endDate]);

  const fetchBatches = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const apiKey = localStorage.getItem('apiKey');
      if (!apiKey) {
        setError('Please enter your API key in the header');
        setLoading(false);
        return;
      }

      const response = await axios.get('/api/batches', {
        params: {
          search: search || undefined,
          output_format: outputFormat || undefined,
          status: status || undefined,
          start_date: startDate || undefined,
          end_date: endDate || undefined,
        },
        headers: {
          'X-API-Key': apiKey,
        },
      });

      setBatches(response.data.batches || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load batch history');
    } finally {
      setLoading(false);
    }
  }, [search, outputFormat, status, startDate, endDate]);

  const fetchJobDetails = async (jobId) => {
    try {
      const apiKey = localStorage.getItem('apiKey');
      const response = await axios.get(`/api/jobs/${jobId}`, {
        headers: {
          'X-API-Key': apiKey,
        },
      });
      setSelectedBatch(null);
      setSelectedJob(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load job details');
    }
  };

  const fetchBatchDetails = async (batchId) => {
    try {
      const apiKey = localStorage.getItem('apiKey');
      const response = await axios.get(`/api/batch/${batchId}`, {
        headers: {
          'X-API-Key': apiKey,
        },
      });
      setSelectedJob(null);
      setSelectedBatch(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load batch details');
    }
  };

  const downloadBatchArchive = async (batchId) => {
    setDownloading(true);
    setDownloadError(null);
    try {
      const apiKey = localStorage.getItem('apiKey');
      const response = await fetch(`/api/batch/${batchId}/download`, {
        headers: {
          ...(apiKey && { 'X-API-Key': apiKey }),
        },
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || 'Download failed');
      }
      const blob = await response.blob();
      const contentDisposition = response.headers.get('content-disposition');
      const fileNameMatch = contentDisposition && contentDisposition.match(/filename="?(.+?)"?/);
      const fileName = fileNameMatch ? fileNameMatch[1] : `${batchId}.zip`;
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', fileName);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setDownloadError(err.message || 'Download failed');
    } finally {
      setDownloading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    fetchBatches();
  }, [fetchJobs, fetchBatches]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchJobs();
    fetchBatches();
  };

  const clearFilters = () => {
    setSearch('');
    setOutputFormat('');
    setStatus('');
    setStartDate('');
    setEndDate('');
    setError(null);
    fetchJobs();
    fetchBatches();
  };

  return (
    <div className="job-history-container">
      <div className="card">
        <div className="card-title">🗂️ History</div>

        <form onSubmit={handleSearchSubmit} className="filter-row">
          <div className="form-group">
            <label htmlFor="search">Search</label>
            <input
              id="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by prompt, brand style, or category"
            />
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
            <label htmlFor="status">Status</label>
            <select id="status" value={status} onChange={(e) => setStatus(e.target.value)}>
              {statusOptions.map((option) => (
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
            <p style={{ marginTop: '16px', color: 'var(--text-dim)' }}>Loading job history...</p>
          </div>
        )}

        {error && <div className="error-message">{error}</div>}

        <div className="history-grid">
          <div className="history-list">
            <div className="history-tabs" style={{ display: 'flex', gap: '12px', marginBottom: '16px' }}>
              <button
                type="button"
                className={`secondary-button ${mode === 'jobs' ? 'active' : ''}`}
                onClick={() => { setMode('jobs'); setSelectedBatch(null); }}
              >
                Jobs
              </button>
              <button
                type="button"
                className={`secondary-button ${mode === 'batches' ? 'active' : ''}`}
                onClick={() => { setMode('batches'); setSelectedJob(null); }}
              >
                Batches
              </button>
            </div>

            {mode === 'jobs' ? (
              jobs.map((job) => (
                <button
                  key={job.job_id}
                  type="button"
                  className={`history-item ${selectedJob?.job_id === job.job_id ? 'selected' : ''}`}
                  onClick={() => fetchJobDetails(job.job_id)}
                >
                  <div className="history-job-id">{job.job_id}</div>
                  <div className="history-meta">{job.status} · {new Date(job.created_at).toLocaleString()}</div>
                  <div className="history-meta">{job.preset_id || 'default'} · {job.output_format}</div>
                </button>
              ))
            ) : (
              batches.map((batch) => (
                <button
                  key={batch.batch_id}
                  type="button"
                  className={`history-item ${selectedBatch?.batch_id === batch.batch_id ? 'selected' : ''}`}
                  onClick={() => fetchBatchDetails(batch.batch_id)}
                >
                  <div className="history-job-id">{batch.batch_id}</div>
                  <div className="history-meta">{batch.status} · {new Date(batch.created_at).toLocaleString()}</div>
                  <div className="history-meta">{batch.total_items} items · {batch.completed_items} complete</div>
                </button>
              ))
            )}

            {((mode === 'jobs' && jobs.length === 0) || (mode === 'batches' && batches.length === 0)) && !loading && (
              <div className="empty-state">
                <p>No {mode === 'jobs' ? 'jobs' : 'batches'} found. Generate content to build your history.</p>
              </div>
            )}
          </div>

          <div className="history-details">
            {selectedBatch ? (
              <>
                <div className="panel-title">Batch details</div>
                <div className="detail-row"><strong>Status:</strong> {selectedBatch.status}</div>
                <div className="detail-row"><strong>Created:</strong> {new Date(selectedBatch.created_at).toLocaleString()}</div>
                <div className="detail-row"><strong>Total items:</strong> {selectedBatch.total_items}</div>
                <div className="detail-row"><strong>Completed:</strong> {selectedBatch.completed_items}</div>
                <div className="detail-row"><strong>Failed:</strong> {selectedBatch.failed_items}</div>
                <div className="detail-row"><strong>Prompt:</strong> {selectedBatch.prompt}</div>
                <div className="detail-row"><strong>Preset:</strong> {selectedBatch.preset_id}</div>
                <div className="detail-row"><strong>Format:</strong> {selectedBatch.output_format}</div>
                <div className="detail-row"><strong>Use case:</strong> {selectedBatch.use_case}</div>
                <div className="detail-row"><strong>Product category:</strong> {selectedBatch.product_category}</div>
                <div className="detail-row"><strong>Brand style:</strong> {selectedBatch.brand_style}</div>
                {selectedBatch.created_at && (
                  <div className="detail-row"><strong>Updated:</strong> {new Date(selectedBatch.updated_at).toLocaleString()}</div>
                )}
                <div className="detail-row"><strong>Metadata:</strong> <pre className="metadata-block">{JSON.stringify(selectedBatch.metadata || {}, null, 2)}</pre></div>

                <button
                  type="button"
                  className="generate-button"
                  onClick={() => downloadBatchArchive(selectedBatch.batch_id)}
                  disabled={downloading}
                  style={{ marginBottom: '16px' }}
                >
                  {downloading ? 'Downloading batch…' : 'Download batch ZIP'}
                </button>
                {downloadError && <div className="error-message" style={{ marginBottom: '16px' }}>{downloadError}</div>}

                {selectedBatch.items && selectedBatch.items.length > 0 ? (
                  <div className="assets-panel">
                    <div className="panel-title">Batch items</div>
                    <div className="image-grid">
                      {selectedBatch.items.map((item) => (
                        <div key={item.job_id} className="grid-item" style={{ position: 'relative' }}>
                          <div className="asset-metadata">
                            <div className="asset-label">{item.label || `Item ${item.item_index + 1}`}</div>
                            <div className="asset-details">{item.status} · {item.progress}%</div>
                          </div>
                          {item.output_urls && item.output_urls.length > 0 ? (
                            item.output_urls.map((url, index) => (
                              <button
                                key={`${item.job_id}-${index}`}
                                type="button"
                                className="link-button"
                                style={{ width: '100%', marginTop: '6px' }}
                                onClick={() => window.open(url, '_blank')}
                              >
                                Download item {item.item_index + 1} asset {index + 1}
                              </button>
                            ))
                          ) : (
                            <div className="empty-state" style={{ marginTop: '10px' }}>
                              <p>No generated assets for this item yet.</p>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="empty-state">
                    <p>No batch items to show yet.</p>
                  </div>
                )}
              </>
            ) : selectedJob ? (
              <>
                <div className="panel-title">Job details</div>
                <div className="detail-row"><strong>Status:</strong> {selectedJob.status}</div>
                <div className="detail-row"><strong>Created:</strong> {new Date(selectedJob.created_at).toLocaleString()}</div>
                <div className="detail-row"><strong>Preset:</strong> {selectedJob.preset_id}</div>
                <div className="detail-row"><strong>Format:</strong> {selectedJob.output_format}</div>
                <div className="detail-row"><strong>Use case:</strong> {selectedJob.use_case}</div>
                <div className="detail-row"><strong>Product category:</strong> {selectedJob.product_category}</div>
                <div className="detail-row"><strong>Brand style:</strong> {selectedJob.brand_style}</div>
                <div className="detail-row"><strong>Prompt:</strong> {selectedJob.prompt}</div>
                <div className="detail-row"><strong>Metadata:</strong> <pre className="metadata-block">{JSON.stringify(selectedJob.metadata || {}, null, 2)}</pre></div>

                {selectedJob.assets && selectedJob.assets.length > 0 ? (
                  <div className="assets-panel">
                    <div className="panel-title">Generated outputs</div>
                    <div className="image-grid">
                      {selectedJob.assets.map((asset) => (
                        <div key={asset.id} className="grid-item" style={{ position: 'relative' }}>
                          <img
                            src={asset.asset_url}
                            alt={asset.label || `Output ${asset.output_index}`}
                            className="grid-image"
                            onClick={() => window.open(asset.asset_url, '_blank')}
                          />
                          <div className="asset-metadata">
                            <div className="asset-label">{asset.label || `Output ${asset.output_index}`}</div>
                            <div className="asset-details">{asset.file_format?.toUpperCase()} · {asset.width}×{asset.height}</div>
                          </div>
                          <button type="button" className="link-button" onClick={() => window.open(asset.asset_url, '_blank')}>Download</button>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="empty-state">
                    <p>No generated assets have been saved for this job yet.</p>
                  </div>
                )}
              </>
            ) : (
              <div className="empty-state">
                <p>Select a job from the list to view its details.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default JobHistory;
