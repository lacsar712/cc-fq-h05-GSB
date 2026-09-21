import test from 'node:test'
import assert from 'node:assert/strict'

import { cardDefs, LABEL_MEAN, LABEL_NRATE } from './metricLabels.js'

test('详情卡片标题与指标一一对应，两值差异明显且不会互换', () => {
  const cards = cardDefs({ mean_quality: 39.75, n_rate: 0.25, reads: 2 })
  const byLabel = Object.fromEntries(cards.map((c) => [c.label, c.value]))

  assert.equal(LABEL_MEAN, '平均质量 mean_quality')
  assert.equal(LABEL_NRATE, 'N 含量 n_rate')
  assert.equal(byLabel['平均质量 mean_quality'], 39.75)
  assert.equal(byLabel['N 含量 n_rate'], 0.25)
})

test('空指标时卡片值为 undefined 且标题不反挂', () => {
  const cards = cardDefs(null)
  assert.equal(cards[0].label, '平均质量 mean_quality')
  assert.equal(cards[1].label, 'N 含量 n_rate')
})
