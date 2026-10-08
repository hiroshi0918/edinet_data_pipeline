import { describe, expect, it } from 'vitest'

import { axisUnit, buildAxis, formatTick, niceTicks, yearLabelIndexes } from './chart-scale'

describe('niceTicks', () => {
  it('正の値だけでも 0 から始める', () => {
    const { ticks, min, max } = niceTicks([980, 1000, 1020])
    expect(min).toBe(0)
    expect(max).toBeGreaterThanOrEqual(1020)
    expect(ticks[0]).toBe(0)
  })

  it('赤字を含むと 0 をまたぐ', () => {
    const { ticks } = niceTicks([-30, 120])
    expect(ticks).toContain(0)
    expect(ticks[0]).toBeLessThan(0)
    expect(ticks[ticks.length - 1]).toBeGreaterThanOrEqual(120)
  })

  it('全部 0 でも幅を持つ', () => {
    const { min, max } = niceTicks([0, 0])
    expect(min).toBe(0)
    expect(max).toBeGreaterThan(0)
  })

  it('小数の刻みで誤差を残さない', () => {
    expect(niceTicks([0.03, 0.12]).ticks).toEqual([0, 0.05, 0.1, 0.15])
  })
})

describe('axisUnit', () => {
  it('1兆円以上は兆円、未満は億円', () => {
    expect(axisUnit('yen', 3e12).unit).toBe('兆円')
    expect(axisUnit('yen', 5e11).unit).toBe('億円')
  })

  it('1万人以上は万人', () => {
    expect(axisUnit('people', 38_000).unit).toBe('万人')
    expect(axisUnit('people', 800).unit).toBe('人')
  })
})

describe('buildAxis / formatTick', () => {
  it('億円の目盛りを読める数にする', () => {
    const axis = buildAxis([1.2e11, 1.5e11], 'yen')
    expect(axis.unit).toBe('億円')
    expect(axis.ticks.map((tick) => formatTick(tick, axis.divisor))).toContain('1,000')
  })

  it('率は % で出す', () => {
    const axis = buildAxis([0.04, 0.11], 'pct')
    expect(formatTick(0.05, axis.divisor)).toBe('5')
  })
})

describe('yearLabelIndexes', () => {
  it('10年なら1年おきで最新年を含む', () => {
    expect(yearLabelIndexes(10)).toEqual([1, 3, 5, 7, 9])
  })

  it('短ければ全部', () => {
    expect(yearLabelIndexes(4)).toEqual([0, 1, 2, 3])
  })
})
