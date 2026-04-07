import assert from 'node:assert/strict';

import { buildBrandKitSnapshot, buildBrandStyle } from '../src/lib/brandKits.js';

assert.equal(
  buildBrandStyle({
    background: 'warm cream backdrop',
    lighting: 'soft side light',
    tone: 'premium and calm',
    framing: 'centered hero shot',
  }),
  'background: warm cream backdrop, lighting: soft side light, tone: premium and calm, framing: centered hero shot',
);

assert.equal(
  buildBrandStyle({
    background: '',
    lighting: '',
    tone: 'clean and modern',
    framing: '',
  }),
  'tone: clean and modern',
);

assert.deepEqual(
  buildBrandKitSnapshot({
    name: 'Flagship Store',
    background: 'neutral paper sweep',
    lighting: 'bright daylight',
    tone: 'clean and modern',
    framing: 'tight product crop',
  }),
  {
    name: 'Flagship Store',
    background: 'neutral paper sweep',
    lighting: 'bright daylight',
    tone: 'clean and modern',
    framing: 'tight product crop',
  },
);

console.log('brand kit helper tests passed');
