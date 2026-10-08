import { describe, expect, test } from 'vitest'

import { monogramChar, tokyoTicker } from '@/lib/company-mark'
import { specimenCaption, specimenPortrait, specimenStage } from '@/lib/specimen'

describe('specimenStage', () => {
  test('点がないときはたまご、点数で4段階に分かれる', () => {
    expect(specimenStage(null)).toBe(0)
    expect(specimenStage(0)).toBe(1)
    expect(specimenStage(39)).toBe(1)
    expect(specimenStage(40)).toBe(2)
    expect(specimenStage(69)).toBe(2)
    expect(specimenStage(70)).toBe(3)
    expect(specimenStage(84)).toBe(3)
    expect(specimenStage(85)).toBe(4)
    expect(specimenStage(100)).toBe(4)
  })
})

describe('specimenCaption', () => {
  test('サービス業の高い総合点は傘のおや', () => {
    expect(specimenCaption('サービス業', 86)).toBe('傘・おや')
  })

  test('別名は同じラベル', () => {
    expect(specimenCaption('運輸業', 40)).toBe('路・わかもの')
    expect(specimenCaption('陸運業', 40)).toBe(specimenCaption('運輸業', 40))
    expect(specimenCaption('倉庫・運輸関連業', 10)).toBe('倉・こども')
  })

  test('業種が無いときと絵が無い業種は卵', () => {
    expect(specimenCaption(null, null)).toBe('卵・たまご')
    expect(specimenCaption('  ', 90)).toBe('卵・おや')
    expect(specimenCaption('未知の業種', 50)).toBe('卵・わかもの')
    expect(specimenCaption('内国法人・組合（有価証券報告書等の提出義務者以外）', 10)).toBe('卵・こども')
  })
})

describe('specimenPortrait', () => {
  test('33業種の絵を返し、別名は同じファイル、未知は無し', () => {
    expect(specimenPortrait('鉄鋼')).toBe(`/characters/${encodeURIComponent('鉄鋼')}.png`)
    expect(specimenPortrait('運輸業')).toBe(`/characters/${encodeURIComponent('陸運業')}.png`)
    expect(specimenPortrait('運輸業')).toBe(specimenPortrait('陸運業'))
    expect(specimenPortrait('内国法人・組合（有価証券報告書等の提出義務者以外）')).toBeNull()
    expect(specimenPortrait(null)).toBeNull()
    expect(specimenPortrait('未知の業種')).toBeNull()
  })
})

describe('tokyoTicker', () => {
  test('4桁と英字コードを東証ティッカーにする', () => {
    expect(tokyoTicker('7203')).toBe('7203.T')
    expect(tokyoTicker('130A')).toBe('130A.T')
    expect(tokyoTicker('72030')).toBe('7203.T')
    expect(tokyoTicker(null)).toBeNull()
    expect(tokyoTicker('トヨタ')).toBeNull()
  })
})

describe('monogramChar', () => {
  test('株式会社を外して先頭の文字を返す', () => {
    expect(monogramChar('株式会社セプテーニ・ホールディングス')).toBe('セ')
    expect(monogramChar('トヨタ自動車株式会社')).toBe('ト')
  })
})
