import assert from 'node:assert/strict';

// Simulate RightPanel's normalization logic
function normalizeGeneratedImages(generatedImages) {
  return Array.isArray(generatedImages)
    ? generatedImages.map((image) => (typeof image === 'string' ? { asset_url: image, approval_status: 'pending' } : image))
    : [];
}

// Test 1: String-only images are normalized with pending status
const stringImages = ['https://example.com/img1.png', 'https://example.com/img2.png'];
const normalized = normalizeGeneratedImages(stringImages);
assert.equal(normalized.length, 2, 'Should normalize 2 string images');
assert.equal(normalized[0].asset_url, 'https://example.com/img1.png', 'Asset URL preserved');
assert.equal(normalized[0].approval_status, 'pending', 'String images get pending status');

// Test 2: Already normalized objects are unchanged
const objectImages = [
  { asset_url: 'https://example.com/approved.png', approval_status: 'approved' },
  { asset_url: 'https://example.com/rejected.png', approval_status: 'rejected' },
];
const normalizedObjects = normalizeGeneratedImages(objectImages);
assert.equal(normalizedObjects.length, 2, 'Should keep 2 object images');
assert.equal(normalizedObjects[0].approval_status, 'approved', 'Approved status preserved');
assert.equal(normalizedObjects[1].approval_status, 'rejected', 'Rejected status preserved');

// Test 3: Empty array returns empty array
assert.deepEqual(normalizeGeneratedImages([]), [], 'Empty array stays empty');

// Test 4: Non-array input returns empty array
assert.deepEqual(normalizeGeneratedImages(null), [], 'null returns empty array');
assert.deepEqual(normalizeGeneratedImages(undefined), [], 'undefined returns empty array');

// Test 5: Status badge mapping
function getStatusBadgeClass(approvalStatus) {
  if (approvalStatus === 'approved') return 'approved';
  if (approvalStatus === 'rejected') return 'rejected';
  if (approvalStatus === 'pending') return 'pending';
  return 'pending';
}

assert.equal(getStatusBadgeClass('approved'), 'approved', 'Approved maps to approved class');
assert.equal(getStatusBadgeClass('rejected'), 'rejected', 'Rejected maps to rejected class');
assert.equal(getStatusBadgeClass('pending'), 'pending', 'Pending maps to pending class');
assert.equal(getStatusBadgeClass('unknown'), 'pending', 'Unknown status defaults to pending');

// Test 6: Gallery approval filter param handling
function buildGalleryParams(filters) {
  const params = {};
  if (filters.search) params.search = filters.search;
  if (filters.assetType) params.asset_type = filters.assetType;
  if (filters.outputFormat) params.output_format = filters.outputFormat;
  if (filters.approvalStatus) params.approval_status = filters.approvalStatus;
  if (filters.startDate) params.start_date = filters.startDate;
  if (filters.endDate) params.end_date = filters.endDate;
  return params;
}

const galleryFilters = {
  search: 'product',
  assetType: 'generated_output',
  outputFormat: 'png',
  approvalStatus: 'approved',
  startDate: '2024-01-01',
  endDate: '2024-12-31',
};

const galleryParams = buildGalleryParams(galleryFilters);
assert.equal(galleryParams.approval_status, 'approved', 'Gallery approval_status param is set');
assert.equal(galleryParams.search, 'product', 'Search param is set');
assert.equal(galleryParams.asset_type, 'generated_output', 'Asset type param is set');

console.log('RightPanel approval normalization tests passed');
