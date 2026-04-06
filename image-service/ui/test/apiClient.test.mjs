import assert from 'node:assert/strict';


const createStorage = () => {
  const state = new Map();
  return {
    getItem: (key) => state.get(key) ?? null,
    setItem: (key, value) => state.set(key, value),
    removeItem: (key) => state.delete(key),
  };
};


global.window = { localStorage: createStorage() };

const apiModule = await import('../src/lib/apiClient.js');


apiModule.setStoredApiKey('secret-key');
assert.equal(apiModule.getStoredApiKey(), 'secret-key');

apiModule.clearStoredApiKey();
assert.equal(apiModule.getStoredApiKey(), '');

apiModule.setStoredApiKey('secret-key');

let requestHeaders;
global.fetch = async (_url, init) => {
  requestHeaders = init.headers;
  return { ok: true };
};

await apiModule.downloadWithAuth('/jobs');
assert.equal(requestHeaders.get('X-API-Key'), 'secret-key');

console.log('apiClient tests passed');
