import { useState, useEffect } from 'react';
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
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [search, setSearch] = useState('');
  const [outputFormat, setOutputFormat] = useState('');
  const [status, setStatus] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchJobs = async () => {
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
  };

  const fetchJobDetails = async (jobId) => {
    try {
      const apiKey = localStorage.getItem('apiKey');
      const response = await axios.get(`/api/jobs/${jobId}`, {
        headers: {
          'X-API-Key': apiKey,
        },
      });
      setSelectedJob(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load job details');
    }
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchJobs();
  };

  const clearFilters = () => {
    setSearch('');
    setOutputFormat('');
    setStatus('');
    setStartDate('');
    setEndDate('');
    setError(null);
    fetchJobs();
  };

  return (
    <div className="job-history-container">
      <div className="card">
        <div className="card-title">🗂️ Job History</div>

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
            {jobs.map((job) => (
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
            ))}
            {jobs.length === 0 && !loading && (
              <div className="empty-state">
                <p>No jobs found. Generate images to build your history.</p>
              </div>
            )}
          </div>

          <div className="history-details">
            {selectedJob ? (
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
