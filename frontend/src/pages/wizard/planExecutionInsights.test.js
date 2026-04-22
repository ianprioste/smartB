import test from 'node:test';
import assert from 'node:assert/strict';

import {
  normalizeSku,
  summarizeDeletionMismatch,
  summarizeOrphanCompositionDiagnostics,
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

test('summarizeOrphanCompositionDiagnostics aggregates rebuilt and blocked skus', () => {
  const summary = summarizeOrphanCompositionDiagnostics({
    summary: {
      rebuilt_orphan_compositions: ['camtestbrp'],
      blocked_orphan_compositions: ['camblockp'],
      retry_skipped_invalid_compositions: ['camskipp'],
    },
    results: [
      {
        sku: 'camtestowm',
        repair_action: 'orphan_composition_rebuilt',
        repaired_orphan_compositions: ['camtestowm'],
      },
      {
        sku: 'camdropg',
        dropped_orphan_compositions: ['camdropg'],
      },
      {
        sku: 'camblockm',
        error_type: 'missing_base_for_composition',
      },
    ],
  });

  assert.equal(summary.hasDiagnostics, true);
  assert.deepEqual(summary.rebuilt, ['CAMTESTBRP', 'CAMTESTOWM']);
  assert.deepEqual(summary.blocked, ['CAMBLOCKM', 'CAMBLOCKP']);
  assert.deepEqual(summary.dropped, ['CAMDROPG']);
  assert.deepEqual(summary.retrySkipped, ['CAMSKIPP']);
});
