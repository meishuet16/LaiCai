import assert from 'node:assert/strict';
import test from 'node:test';
import { fixtureDataSource } from '../services/retainIQService.ts';
import { matchesCurrencyFilter } from './customerFilters.ts';

test('currency filtering keeps accounts with unknown MRR visible as N/A', async () => {
  const accounts = await fixtureDataSource.listAccounts();
  const withoutMrr = accounts.find(account => account.mrr == null)!;
  assert.equal(matchesCurrencyFilter(withoutMrr, 'MYR'), true);
  assert.equal(matchesCurrencyFilter(withoutMrr, 'SGD'), true);
  assert.equal(matchesCurrencyFilter(accounts.find(account => account.mrr?.currency === 'SGD')!, 'MYR'), false);
  assert.equal(matchesCurrencyFilter(accounts.find(account => account.mrr?.currency === 'MYR')!, 'All'), true);
});
