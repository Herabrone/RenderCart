import axios from 'axios';

const STORAGE_KEY = 'rendercart.apiKey';
const LEGACY_STORAGE_KEY = 'apiKey';
const API_BASE_URL = '/api';

export const getStoredApiKey = () =>
  window.localStorage.getItem(STORAGE_KEY) || window.localStorage.getItem(LEGACY_STORAGE_KEY) || '';

export const setStoredApiKey = (apiKey) => {
  const trimmed = apiKey.trim();
  if (!trimmed) {
    clearStoredApiKey();
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, trimmed);
  window.localStorage.setItem(LEGACY_STORAGE_KEY, trimmed);
};

export const clearStoredApiKey = () => {
  window.localStorage.removeItem(STORAGE_KEY);
  window.localStorage.removeItem(LEGACY_STORAGE_KEY);
};

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

apiClient.interceptors.request.use((config) => {
  const apiKey = getStoredApiKey();
  const nextConfig = { ...config, headers: { ...(config.headers || {}) } };
  if (apiKey) {
    nextConfig.headers['X-API-Key'] = apiKey;
  }
  return nextConfig;
});

export const downloadWithAuth = (path, init = {}) => {
  const headers = new Headers(init.headers || {});
  const apiKey = getStoredApiKey();
  if (apiKey) {
    headers.set('X-API-Key', apiKey);
  }
  return fetch(`${API_BASE_URL}${path}`, { ...init, headers });
};

// Shopify Store Management API
export const listShopifyStores = () => apiClient.get('/shopify/stores');

export const connectShopifyStore = (authCode, shop) =>
  apiClient.post('/shopify/connect', { authorization_code: authCode, shop });

export const disconnectStore = (storeId) =>
  apiClient.delete(`/shopify/stores/${storeId}`);

// Shopify Product & Inventory API
export const fetchProducts = (storeId, search = '', limit = 20) =>
  apiClient.get(`/shopify/stores/${storeId}/products`, {
    params: { search, limit },
  });

// Shopify Publish API
export const publishAssetToShopify = (assetId, publishRequest) =>
  apiClient.post(`/assets/${assetId}/publish/shopify`, publishRequest);

export const bulkPublishToShopify = (bulkRequest) =>
  apiClient.post('/assets/bulk-publish/shopify', bulkRequest);

export const getPublishStatus = (assetId) =>
  apiClient.get(`/assets/${assetId}/publish-status`);
