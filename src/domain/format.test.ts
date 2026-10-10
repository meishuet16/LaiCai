import assert from 'node:assert/strict';
import test from 'node:test';
import { formatMoney, majorToMinor, minorToMajor } from './format.ts';

test('currency-aware formatting supports the project minimum ISO currency set', () => {
  assert.match(formatMoney({ amount_minor: 123456, currency: 'MYR' }), /1,234\.56/);
  assert.match(formatMoney({ amount_minor: 123456, currency: 'USD' }), /1,234\.56/);
  assert.match(formatMoney({ amount_minor: 123456, currency: 'SGD' }), /1,234\.56/);
});

test('minor-unit conversion follows currency fraction digits', () => {
  assert.equal(minorToMajor({ amount_minor: 123, currency: 'JPY' }), 123);
  assert.equal(majorToMinor(1.234, 'KWD'), 1234);
  assert.equal(majorToMinor(1.23, 'MYR'), 123);
});

test('zero is valid while missing, malformed, unsupported, and negative MRR-like money is unavailable', () => {
  assert.notEqual(formatMoney({ amount_minor: 0, currency: 'MYR' }), 'N/A');
  assert.equal(formatMoney(null), 'N/A');
  assert.equal(formatMoney({ amount_minor: -1, currency: 'MYR' }), 'N/A');
  assert.equal(formatMoney({ amount_minor: 1.2, currency: 'MYR' }), 'N/A');
  assert.equal(formatMoney({ amount_minor: 100, currency: 'ZZZ' }), 'N/A');
  assert.equal(minorToMajor({ amount_minor: -100, currency: 'MYR' }), null);
});
