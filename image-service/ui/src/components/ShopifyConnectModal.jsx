import { useState } from 'react';

import { connectShopifyStore } from '../lib/apiClient';

const ShopifyConnectModal = ({ onClose, onSuccess }) => {
  const [shopDomain, setShopDomain] = useState('');
  const [authCode, setAuthCode] = useState('');
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState(null);

  const handleConnect = async () => {
    if (!shopDomain.trim()) {
      setError('Shop domain is required');
      return;
    }

    setIsConnecting(true);
    setError(null);

    try {
      await connectShopifyStore(authCode, shopDomain.trim());
      onSuccess();
      onClose();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Failed to connect store');
    } finally {
      setIsConnecting(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal modal--medium">
        <div className="modal-header">
          <h3>Connect Shopify Store</h3>
          <button className="modal-close" onClick={onClose}>
            &times;
          </button>
        </div>
        <div className="modal-body">
          <div className="form-group">
            <label htmlFor="shop-domain">Shop Domain</label>
            <input
              id="shop-domain"
              type="text"
              placeholder="example.myshopify.com"
              value={shopDomain}
              onChange={(e) => setShopDomain(e.target.value)}
              disabled={isConnecting}
            />
            <p className="field-help">Enter your Shopify store domain</p>
          </div>

          <div className="form-group">
            <label htmlFor="auth-code">Authorization Code (optional)</label>
            <input
              id="auth-code"
              type="text"
              placeholder="Paste code from OAuth callback"
              value={authCode}
              onChange={(e) => setAuthCode(e.target.value)}
              disabled={isConnecting}
            />
            <p className="field-help">
              If you completed OAuth flow separately, paste the code here
            </p>
          </div>

          {error && <div className="error-message">{error}</div>}

          <div className="modal-info">
            <p>We'll securely encrypt and store your access token.</p>
          </div>
        </div>

        <div className="modal-footer">
          <button className="secondary-button" onClick={onClose} disabled={isConnecting}>
            Cancel
          </button>
          <button className="primary-button" onClick={handleConnect} disabled={isConnecting}>
            {isConnecting ? 'Connecting...' : 'Connect Store'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ShopifyConnectModal;
