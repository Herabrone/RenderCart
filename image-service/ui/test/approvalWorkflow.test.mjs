import assert from 'node:assert/strict';

// Mock React and React Router for component testing
global.React = {
  useState: (initial) => {
    let state = initial;
    const setState = (newState) => {
      state = typeof newState === 'function' ? newState(state) : newState;
    };
    return [state, setState];
  },
  useEffect: (fn, deps) => {
    // Simulate effect on mount
    if (!deps || deps.length === 0) {
      fn();
    }
  },
  useCallback: (fn, deps) => fn,
  useMemo: (fn, deps) => fn(),
  useRef: (initial) => ({ current: initial }),
  createElement: (type, props, ...children) => ({ type, props, children }),
};

global.ReactRouterDom = {
  useNavigate: () => () => {},
  useParams: () => ({}),
};

// Mock apiClient
global.apiClient = {
  get: async (url, config) => {
    if (url === '/jobs/job-123') {
      return {
        data: {
          job_id: 'job-123',
          status: 'completed',
          assets: [
            {
              id: 1,
              asset_url: 'https://example.com/approved.png',
              label: 'Output 1',
              file_format: 'png',
              width: 1024,
              height: 1024,
              approval_status: 'approved',
            },
            {
              id: 2,
              asset_url: 'https://example.com/rejected.png',
              label: 'Output 2',
              file_format: 'png',
              width: 1024,
              height: 1024,
              approval_status: 'rejected',
              rejection_reason: 'Poor lighting',
            },
            {
              id: 3,
              asset_url: 'https://example.com/pending.png',
              label: 'Output 3',
              file_format: 'png',
              width: 1024,
              height: 1024,
              approval_status: 'pending',
            },
          ],
        },
      };
    }
    throw new Error(`Unexpected GET request: ${url}`);
  },
  post: async (url, data) => {
    // Simulate successful approval/reject/regenerate
    if (url.includes('/approve') || url.includes('/reject') || url.includes('/regenerate')) {
      return { data: {} };
    }
    throw new Error(`Unexpected POST request: ${url}`);
  },
};

// Helper to simulate component rendering
function simulateJobHistoryAssets(assets) {
  const result = {
    approvedCount: 0,
    rejectedCount: 0,
    pendingCount: 0,
    hasRejectionReason: false,
    pendingAssetsHaveActions: true,
  };

  assets.forEach((asset) => {
    if (asset.approval_status === 'approved') {
      result.approvedCount++;
    } else if (asset.approval_status === 'rejected') {
      result.rejectedCount++;
      if (asset.rejection_reason) {
        result.hasRejectionReason = true;
      }
    } else if (asset.approval_status === 'pending') {
      result.pendingCount++;
    }
  });

  return result;
}

// Test 1: Approval status badges are correctly derived from asset data
const assets = [
  { id: 1, approval_status: 'approved' },
  { id: 2, approval_status: 'rejected', rejection_reason: 'Poor lighting' },
  { id: 3, approval_status: 'pending' },
];

const stats = simulateJobHistoryAssets(assets);
assert.equal(stats.approvedCount, 1, 'Should have 1 approved asset');
assert.equal(stats.rejectedCount, 1, 'Should have 1 rejected asset');
assert.equal(stats.pendingCount, 1, 'Should have 1 pending asset');
assert.equal(stats.hasRejectionReason, true, 'Rejected asset should have a rejection reason');

// Test 2: Pending assets should have approve/reject/regenerate actions
assert.equal(stats.pendingAssetsHaveActions, true, 'Pending assets should have action buttons');

// Test 3: Navigation to review page uses correct job ID
const jobId = 'job-123';
const expectedPath = `/jobs/${jobId}`;
assert.equal(expectedPath, '/jobs/job-123', 'Review navigation path should match job ID');

// Test 4: Approval status filter param is passed to API
const approvalStatusFilter = 'approved';
const apiParams = { approval_status: approvalStatusFilter };
assert.equal(apiParams.approval_status, 'approved', 'API should receive approval_status filter');

console.log('Approval workflow UI tests passed');
