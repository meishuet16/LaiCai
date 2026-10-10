import assert from 'node:assert/strict';
import test from 'node:test';
import { casePath, navItems, predictionPath, routeFromPath, timelinePath } from './routes.ts';

test('primary navigation has the required five labels and keeps existing paths', () => {
  assert.deepEqual(navItems.map(item => item.label), ['Business Overview', 'Data Integration', 'Churn Prediction', 'Retention Actions', 'Customer Insights']);
  assert.deepEqual(navItems.map(item => item.href), ['/command-center', '/integrations', '/predictions', '/cases', '/customers/c01/timeline']);
});

test('known sections resolve from direct URLs', () => {
  assert.deepEqual(routeFromPath('/predictions'), { section: 'predictions' });
  assert.deepEqual(routeFromPath('/cases/'), { section: 'cases' });
});
test('account timeline IDs survive URL encoding', () => {
  assert.deepEqual(routeFromPath(timelinePath('account/a b')), { section: 'timeline', customerId: 'account/a b' });
});
test('prediction details have a direct URL', () => {
  assert.deepEqual(routeFromPath(predictionPath('pred/a b')), { section: 'prediction-detail', predictionId: 'pred/a b' });
});
test('case details have an encoded direct URL', () => {
  assert.deepEqual(routeFromPath(casePath('case/a b')), { section: 'case-detail', caseId: 'case/a b' });
});
test('unknown or malformed routes fail safely', () => {
  assert.deepEqual(routeFromPath('/missing'), { section: 'command-center' });
  assert.deepEqual(routeFromPath('/customers/%ZZ/timeline'), { section: 'command-center' });
});
