import { useState, useEffect } from 'react';

import BrandKitManager from './BrandKitManager';
import ImageUpload from './ImageUpload';
import GenerateForm from './GenerateForm';
import ShopifyConnectModal from './ShopifyConnectModal';
import { listShopifyStores, disconnectStore } from '../lib/apiClient';

const LeftPanel = ({
  uploadedImages,
  onImageUpload,
  onJobCreated,
  onBatchCreated,
  onStatusChange,
  onStoresUpdated,
}) => {
  const [appliedBrandKit, setAppliedBrandKit] = useState(null);
  const [stores, setStores] = useState([]);
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [isLoadingStores, setIsLoadingStores] = useState(true);
  const [storeError, setStoreError] = useState(null);
  const [disconnecting, setDisconnecting] = useState(null);

  useEffect(() => {
    const fetchStores = async () => {
      setIsLoadingStores(true);
      setStoreError(null);

      try {
        const response = await listShopifyStores();
        setStores(response.data.stores || []);
        if (onStoresUpdated) {
          onStoresUpdated(response.data.stores || []);
        }
      } catch (err) {
        setStoreError(err.response?.data?.detail || 'Failed to load stores');
      } finally {
        setIsLoadingStores(false);
      }
    };

    fetchStores();
  }, [onStoresUpdated]);

  const handleConnectSuccess = async () => {
    setShowConnectModal(false);
    const response = await listShopifyStores();
    setStores(response.data.stores || []);
    if (onStoresUpdated) {
      onStoresUpdated(response.data.stores || []);
    }
  };

  const handleDisconnect = async (storeId) => {
    setDisconnecting(storeId);

    try {
      await disconnectStore(storeId);
      setStores((prevStores) => prevStores.filter((s) => s.id !== storeId));
      if (onStoresUpdated) {
        setStores((prevStores) => {
          const updated = prevStores.filter((s) => s.id !== storeId);
          onStoresUpdated(updated);
          return updated;
        });
      }
    } catch (err) {
      setStoreError(err.response?.data?.detail || 'Failed to disconnect store');
    } finally {
      setDisconnecting(null);
    }
  };

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

      <div className="panel-card panel-card--secondary" id="shopify-integration">
        <div className="panel-title">Shopify Stores</div>
        <p className="panel-copy">Connect your Shopify store to publish approved assets directly to products.</p>

        {isLoadingStores ? (
          <div className="loading-state">
            <p>Loading stores...</p>
          </div>
        ) : storeError ? (
          <div className="error-message">
            <p>{storeError}</p>
          </div>
        ) : stores.length > 0 ? (
          <div className="stores-list">
            {stores.map((store) => (
              <div key={store.id} className="store-card">
                <div className="store-info">
                  <p className="store-domain">{store.shop_domain}</p>
                  <p className="store-status">
                    {store.status === 'active' ? '✓ Connected' : '⚠ Disconnected'}
                  </p>
                </div>
                <button
                  className="secondary-button secondary-button--sm"
                  onClick={() => handleDisconnect(store.id)}
                  disabled={disconnecting === store.id}
                >
                  {disconnecting === store.id ? 'Disconnecting...' : 'Disconnect'}
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <p>No stores connected yet.</p>
          </div>
        )}

        <button
          className="primary-button"
          onClick={() => setShowConnectModal(true)}
          style={{ marginTop: '1rem', width: '100%' }}
        >
          + Connect Store
        </button>
      </div>

      <div className="panel-card panel-card--secondary" id="brand-styles">
        <div className="panel-title">Brand styles and presets</div>
        <p className="panel-copy">
          Save time by focusing on product image type, brand tone, and output format instead of raw model settings.
        </p>
        <BrandKitManager onApply={(brandKit) => setAppliedBrandKit({ ...brandKit, appliedAt: Date.now() })} />
      </div>

      {showConnectModal && (
        <ShopifyConnectModal
          onClose={() => setShowConnectModal(false)}
          onSuccess={handleConnectSuccess}
        />
      )}
    </section>
  );
};

export default LeftPanel;
