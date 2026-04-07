import { useState, useEffect } from 'react';

import { fetchProducts, publishAssetToShopify } from '../lib/apiClient';

const PublishModal = ({ asset, stores, onClose, onSuccess }) => {
  const [selectedStore, setSelectedStore] = useState(stores && stores.length > 0 ? stores[0].id : '');
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState('');
  const [replaceExisting, setReplaceExisting] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [error, setError] = useState(null);
  const [fetchError, setFetchError] = useState(null);

  useEffect(() => {
    const fetchProductsList = async () => {
      if (!selectedStore) return;

      setIsLoading(true);
      setFetchError(null);
      setProducts([]);
      setSelectedProduct('');

      try {
        const response = await fetchProducts(selectedStore, searchQuery, 20);
        setProducts(response.data.products || []);
      } catch (err) {
        setFetchError(err.response?.data?.detail || 'Failed to fetch products');
      } finally {
        setIsLoading(false);
      }
    };

    const debounceTimer = setTimeout(() => {
      fetchProductsList();
    }, 500);

    return () => clearTimeout(debounceTimer);
  }, [selectedStore, searchQuery]);

  const handlePublish = async () => {
    if (!selectedProduct) {
      setError('Please select a product');
      return;
    }

    setIsPublishing(true);
    setError(null);

    try {
      await publishAssetToShopify(asset.id, {
        store_id: selectedStore,
        shopify_product_id: selectedProduct,
        replace_existing_media: replaceExisting,
      });
      onSuccess();
      onClose();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Failed to publish asset');
    } finally {
      setIsPublishing(false);
    }
  };

  const isPublishDisabled = !selectedProduct || isPublishing || isLoading;

  return (
    <div className="modal-overlay">
      <div className="modal modal--large">
        <div className="modal-header">
          <h3>Publish to Shopify</h3>
          <button className="modal-close" onClick={onClose} disabled={isPublishing}>
            &times;
          </button>
        </div>

        <div className="modal-body">
          <div className="publish-preview">
            <img
              src={asset.asset_url}
              alt="Asset to publish"
              className="publish-preview-image"
            />
            <div className="publish-preview-info">
              <p className="label">Asset: {asset.label || 'Untitled'}</p>
              {asset.shopify_published_at && (
                <p className="status-text">
                  Last published: {new Date(asset.shopify_published_at).toLocaleDateString()}
                </p>
              )}
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="store-select">
              Store <span className="required">*</span>
            </label>
            <select
              id="store-select"
              value={selectedStore}
              onChange={(e) => setSelectedStore(e.target.value)}
              disabled={isPublishing}
            >
              <option value="">Select a store...</option>
              {stores.map((store) => (
                <option key={store.id} value={store.id}>
                  {store.shop_domain}
                </option>
              ))}
            </select>
          </div>

          {selectedStore && (
            <>
              <div className="form-group">
                <label htmlFor="product-search">
                  Search Products <span className="required">*</span>
                </label>
                <input
                  id="product-search"
                  type="text"
                  placeholder="Search by product name..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  disabled={isPublishing || isLoading}
                />
              </div>

              {fetchError && (
                <div className="error-message">{fetchError}</div>
              )}

              {isLoading ? (
                <div className="loading-state">
                  <p>Loading products...</p>
                </div>
              ) : products.length > 0 ? (
                <div className="form-group">
                  <label htmlFor="product-select">
                    Product <span className="required">*</span>
                  </label>
                  <select
                    id="product-select"
                    value={selectedProduct}
                    onChange={(e) => setSelectedProduct(e.target.value)}
                    disabled={isPublishing}
                  >
                    <option value="">Select a product...</option>
                    {products.map((product) => (
                      <option key={product.id} value={product.id}>
                        {product.title}
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <div className="empty-state">
                  <p>No products found. Try a different search.</p>
                </div>
              )}

              <div className="form-group">
                <fieldset className="radio-group">
                  <legend>How do you want to add this image?</legend>
                  <label className="radio-label">
                    <input
                      type="radio"
                      name="media-mode"
                      value="add"
                      checked={!replaceExisting}
                      onChange={() => setReplaceExisting(false)}
                      disabled={isPublishing}
                    />
                    <span>Add as new media</span>
                  </label>
                  <label className="radio-label">
                    <input
                      type="radio"
                      name="media-mode"
                      value="replace"
                      checked={replaceExisting}
                      onChange={() => setReplaceExisting(true)}
                      disabled={isPublishing}
                    />
                    <span>Replace first existing image</span>
                  </label>
                </fieldset>
              </div>
            </>
          )}

          {error && <div className="error-message">{error}</div>}
        </div>

        <div className="modal-footer">
          <button
            className="secondary-button"
            onClick={onClose}
            disabled={isPublishing}
          >
            Cancel
          </button>
          <button
            className="primary-button"
            onClick={handlePublish}
            disabled={isPublishDisabled}
          >
            {isPublishing ? 'Publishing...' : 'Publish to Shopify'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default PublishModal;
