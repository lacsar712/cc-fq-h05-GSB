export const LABEL_MEAN = '平均质量 mean_quality'
export const LABEL_NRATE = 'N 含量 n_rate'

export function cardDefs(metrics) {
  const m = metrics || {}
  return [
    { label: LABEL_MEAN, value: m.mean_quality },
    { label: LABEL_NRATE, value: m.n_rate },
    { label: 'reads', value: m.reads },
  ]
}
