import test from 'node:test';
import assert from 'node:assert/strict';

import {
  normalizeSku,
  summarizeDeletionMismatch,
  summarizePlannedDeletionRisk,
} from './planExecutionInsights.js';

test('normalizeSku uppercases and trims values', () => {
  assert.equal(normalizeSku(' camtestbrp '), 'CAMTESTBRP');
  assert.equal(normalizeSku(null), '');
});

test('summarizePlannedDeletionRisk returns sensitive parents and totals', () => {
  const summary = summarizePlannedDeletionRisk({
    items: [
      { sku: 'camtest', planned_deletions: ['camtestbrp', 'CAMTESTOWM'] },
      { sku: 'camnoop', planned_deletions: [] },
    ],
  });

  assert.equal(summary.parentsWithPlannedDeletions, 1);
  assert.equal(summary.totalPlannedDeletionSkus, 2);
  assert.deepEqual(summary.sensitiveParents[0], {
    sku: 'CAMTEST',
    count: 2,
    plannedDeletions: ['CAMTESTBRP', 'CAMTESTOWM'],
  });
});

test('summarizeDeletionMismatch detects mismatch details', () => {
  const summary = summarizeDeletionMismatch({
    planned_deletions: ['CAMTESTBRP'],
    unexpected_removed_variations: ['camtestowm'],
    missing_planned_deletions: ['camtestbrp'],
  });

  assert.equal(summary.hasMismatch, true);
  assert.deepEqual(summary.planned, ['CAMTESTBRP']);
  assert.deepEqual(summary.unexpected, ['CAMTESTOWM']);
  assert.deepEqual(summary.missing, ['CAMTESTBRP']);
});