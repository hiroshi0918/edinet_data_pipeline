// 並び済みの点数から順位を付ける。同点は同じ順位にし、次はその人数ぶん飛ばす（1位・1位・3位）。
// 点が無い行は、並びどおりの位置を順位にする。
export function tiedRanks(scores: (number | null | undefined)[]): number[] {
  const ranks: number[] = []
  scores.forEach((score, index) => {
    const previous = index > 0 ? scores[index - 1] : undefined
    if (score != null && previous != null && score === previous) {
      ranks.push(ranks[index - 1])
    } else {
      ranks.push(index + 1)
    }
  })
  return ranks
}
