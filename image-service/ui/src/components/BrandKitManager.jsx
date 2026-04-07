import { useEffect, useState } from 'react';

import { apiClient } from '../lib/apiClient';
import { emptyBrandKitDraft } from '../lib/brandKits';

const BrandKitManager = ({ onApply }) => {
  const [brandKits, setBrandKits] = useState([]);
  const [draft, setDraft] = useState(emptyBrandKitDraft);
  const [editingId, setEditingId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const loadBrandKits = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('/brand-kits');
      setBrandKits(response.data.brand_kits || []);
      setError(null);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Failed to load brand kits.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBrandKits();
  }, []);

  const resetForm = () => {
    setDraft(emptyBrandKitDraft);
    setEditingId(null);
  };

  const handleDraftChange = (field, value) => {
    setDraft((current) => ({ ...current, [field]: value }));
  };

  const handleEdit = (brandKit) => {
    setDraft({
      name: brandKit.name || '',
      background: brandKit.background || '',
      lighting: brandKit.lighting || '',
      tone: brandKit.tone || '',
      framing: brandKit.framing || '',
    });
    setEditingId(brandKit.id);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (editingId) {
        await apiClient.patch(`/brand-kits/${editingId}`, draft);
      } else {
        await apiClient.post('/brand-kits', draft);
      }
      await loadBrandKits();
      resetForm();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Could not save brand kit.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="brand-kit-manager">
      <div className="panel-subtitle">Saved kits</div>

      {loading ? (
        <div className="note-text">Loading brand kits...</div>
      ) : brandKits.length === 0 ? (
        <div className="note-text">Create your first reusable style profile for a store, collection, or campaign.</div>
      ) : (
        <div className="brand-kit-list">
          {brandKits.map((brandKit) => (
            <div key={brandKit.id} className="brand-kit-card">
              <div className="brand-kit-card__header">
                <div>
                  <div className="brand-kit-card__title">{brandKit.name}</div>
                  <div className="brand-kit-card__meta">
                    {brandKit.tone} · {brandKit.lighting}
                  </div>
                </div>
                <div className="brand-kit-card__actions">
                  <button type="button" className="secondary-button" onClick={() => onApply?.(brandKit)}>
                    Apply
                  </button>
                  <button type="button" className="secondary-button" onClick={() => handleEdit(brandKit)}>
                    Edit
                  </button>
                </div>
              </div>
              <div className="brand-kit-card__details">
                <span>Background: {brandKit.background}</span>
                <span>Framing: {brandKit.framing}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="brand-kit-form">
        <div className="panel-subtitle">{editingId ? 'Edit brand kit' : 'Create a brand kit'}</div>

        <div className="form-group">
          <label htmlFor="brandKitName">Name</label>
          <input
            id="brandKitName"
            value={draft.name}
            onChange={(event) => handleDraftChange('name', event.target.value)}
            placeholder="e.g. Premium storefront"
            required
          />
        </div>

        <div className="form-grid">
          <div className="form-group">
            <label htmlFor="brandKitBackground">Background</label>
            <input
              id="brandKitBackground"
              value={draft.background}
              onChange={(event) => handleDraftChange('background', event.target.value)}
              placeholder="e.g. bright marble surface"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="brandKitLighting">Lighting</label>
            <input
              id="brandKitLighting"
              value={draft.lighting}
              onChange={(event) => handleDraftChange('lighting', event.target.value)}
              placeholder="e.g. soft natural side light"
              required
            />
          </div>
        </div>

        <div className="form-grid">
          <div className="form-group">
            <label htmlFor="brandKitTone">Tone</label>
            <input
              id="brandKitTone"
              value={draft.tone}
              onChange={(event) => handleDraftChange('tone', event.target.value)}
              placeholder="e.g. modern and elevated"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="brandKitFraming">Framing</label>
            <input
              id="brandKitFraming"
              value={draft.framing}
              onChange={(event) => handleDraftChange('framing', event.target.value)}
              placeholder="e.g. centered hero composition"
              required
            />
          </div>
        </div>

        <div className="brand-kit-form__actions">
          <button type="submit" className="primary-button" disabled={saving}>
            {saving ? 'Saving...' : editingId ? 'Update brand kit' : 'Save brand kit'}
          </button>
          {editingId && (
            <button type="button" className="secondary-button" onClick={resetForm}>
              Cancel edit
            </button>
          )}
        </div>

        {error && <div className="error-message">{error}</div>}
      </form>
    </div>
  );
};

export default BrandKitManager;
