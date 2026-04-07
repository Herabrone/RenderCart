import { useState, useEffect } from 'react';

import { fetchProducts, bulkPublishToShopify } from '../lib/apiClient';

const BulkPublishModal = ({ assets, stores, onClose, onSuccess }) => {
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

    const debounceTimer = setTimeout(fetchProductsList, 500);
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
      const response = await bulkPublishToShopify({
        store_id: selectedStore,
        items: assets.map((asset) => ({
          asset_id: asset.id,
          shopify_product_id: selectedProduct,
          replace_existing_media: replaceExisting,
        })),
      });

      onSuccess(response.data);
      onClose();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Failed to submit bulk publish');
    } finally {
      setIsPublishing(false);
    }
  };

  const isPublishDisabled = !selectedProduct || isPublishing || isLoading;

  return (
    <div className="modal-overlay">
      <div className="modal modal--large">
        <div className="modal-header">
          <h3>Bulk Publish to Shopify</h3>
          <button className="modal-close" onClick={onClose} disabled={isPublishing}>
            &times;
          </button>
        </div>

        <div className="modal-body">
          <div className="modal-info" style={{ marginBottom: '1.5rem' }}>
            <p>
              <strong>{assets.length} approved asset{assets.length !== 1 ? 's' : ''}</strong> will
              be queued for publishing. All assets will be added to the selected product.
            </p>
          </div>

          <div className="form-group">
            <label htmlFor="bulk-store-select">
              Store <span className="required">*</span>
            </label>
            <select
              id="bulk-store-select"
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
                <label htmlFor="bulk-product-search">Search Products</label>
                <input
                  id="bulk-product-search"
                  type="text"
                  placeholder="Search by product name..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  disabled={isPublishing || isLoading}
                />
              </div>

              {fetchError && <div className="error-message">{fetchError}</div>}

              {isLoading ? (
                <div className="loading-state"><p>Loading products...</p></div>
              ) : products.length > 0 ? (
                <div className="form-group">
                  <label htmlFor="bulk-product-select">
                    Product <span className="required">*</span>
                  </label>
                  <select
                    id="bulk-product-select"
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
                <div className="empty-state"><p>No products found.</p></div>
              )}

              <div className="form-group">
                <fieldset className="radio-group">
                  <legend>How do you want to add these images?</legend>
                  <label className="radio-label">
                    <input
                      type="radio"
                      name="bulk-media-mode"
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
                      name="bulk-media-mode"
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
          <button className="secondary-button" onClick={onClose} disabled={isPublishing}>
            Cancel
          </button>
          <button className="primary-button" onClick={handlePublish} disabled={isPublishDisabled}>
            {isPublishing
              ? 'Submitting...'
              : `Publish ${assets.length} Asset${assets.length !== 1 ? 's' : ''}`}
          </button>
        </div>
      </div>
    </div>
  );
};

export default BulkPublishModal;
