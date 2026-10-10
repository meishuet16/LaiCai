import assert from 'node:assert/strict';
import test from 'node:test';
import { fixtureDataSource } from '../services/retainIQService.ts';
import { isNonForecastAccount, predictionWarnings, probabilityAt } from './predictionPresentation.ts';

test('prediction presentation uses the stored horizon and keeps non-scores unscored', async () => {
  const accounts = await fixtureDataSource.listAccounts();
  const scored = accounts.find(account => account.customer_id === 'c02')!;
  const abstained = accounts.find(account => account.customer_id === 'c07')!;
  assert.equal(probabilityAt(scored.prediction, 7), 0.3);
  assert.equal(probabilityAt(scored.prediction, 14), 0.45);
  assert.equal(probabilityAt(scored.prediction, 30), 0.7);
  assert.equal(probabilityAt(abstained.prediction, 30), null);
  assert.equal(scored.prediction?.risk_bands_by_horizon, null);
});

test('known cancellations and ineligible accounts stay outside the forecast cohort', async () => {
  const accounts = await fixtureDataSource.listAccounts();
  assert.equal(isNonForecastAccount(accounts.find(account => account.customer_id === 'c06')!), true);
  assert.equal(isNonForecastAccount(accounts.find(account => account.customer_id === 'c09')!), true);
  assert.equal(isNonForecastAccount(accounts.find(account => account.customer_id === 'c07')!), false);
});

test('cumulative horizon violations are surfaced without rewriting supplied values', async () => {
  const accounts = await fixtureDataSource.listAccounts();
  const prediction = structuredClone(accounts.find(account => account.customer_id === 'c02')!.prediction)!;
  prediction.p_churn_7d = 0.51;
  prediction.p_churn_14d = 0.45;
  prediction.p_churn_30d = 0.7;
  assert.deepEqual(predictionWarnings(prediction), ['horizon_order_violation']);
  assert.equal(probabilityAt(prediction, 7), 0.51);
});

test('scored records with missing or out-of-range probabilities are flagged', async () => {
  const accounts = await fixtureDataSource.listAccounts();
  const prediction = structuredClone(accounts.find(account => account.customer_id === 'c02')!.prediction)!;
  prediction.p_churn_7d = -0.1;
  prediction.p_churn_14d = null;
  assert.deepEqual(predictionWarnings(prediction), ['missing_horizon_probability', 'probability_out_of_range']);
});
