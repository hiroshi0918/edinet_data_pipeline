import { describe, expect, test } from 'vitest'

import { logoDevSrc, monogramChar, tokyoTicker } from '@/lib/company-mark'
import {
  industryIndex,
  industryLabel,
  specimenCaption,
  specimenNo,
  specimenPortrait,
  specimenStage,
  specimenThumb,
} from '@/lib/specimen'

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

describe('specimenNo', () => {
  test('東証33業種の並びで番号を振り、卵は 000', () => {
    expect(specimenNo('水産・農林業')).toBe('No.001')
    expect(specimenNo('輸送用機器')).toBe('No.017')
    expect(specimenNo('運輸業')).toBe(specimenNo('陸運業'))
    expect(specimenNo('サービス業')).toBe('No.033')
    expect(specimenNo(null)).toBe('No.000')
  })
})

describe('industryIndex', () => {
  test('絵ごとに1マスで図鑑番号の順。別名の社数は足し、多い方の名前へ進む', () => {
    const entries = industryIndex([
      { industry: 'サービス業', company_count: 10 },
      { industry: '陸運業', company_count: 5 },
      { industry: '運輸業', company_count: 2 },
      { industry: '内国法人・組合（有価証券報告書等の提出義務者以外）', company_count: 3 },
    ])
    expect(entries).toHaveLength(34)
    expect(entries[0]).toMatchObject({ no: 'No.001', industry: '水産・農林業', companyCount: 0 })
    expect(entries.find((entry) => entry.no === 'No.021')).toMatchObject({
      industry: '陸運業',
      companyCount: 7,
    })
    expect(entries.at(-1)).toMatchObject({ no: 'No.000', label: '卵', companyCount: 3 })
  })

  test('社数が来る前は業種だけ並べ、卵は出さない', () => {
    const entries = industryIndex(undefined)
    expect(entries).toHaveLength(33)
    expect(entries.every((entry) => entry.companyCount == null)).toBe(true)
  })
})

describe('specimenPortrait', () => {
  test('33業種の絵を返し、別名は同じファイル、未知は無し', () => {
    expect(specimenPortrait('鉄鋼')).toBe(`/characters/webp/${encodeURIComponent('鉄鋼')}.webp`)
    expect(specimenThumb('鉄鋼')).toBe(`/characters/thumb/${encodeURIComponent('鉄鋼')}.webp`)
    expect(specimenPortrait('運輸業')).toBe(`/characters/webp/${encodeURIComponent('陸運業')}.webp`)
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

describe('logoDevSrc', () => {
  test('証券コードと token から logo.dev の URL を作る', () => {
    expect(logoDevSrc('4293', 'pk_test', 64)).toBe(
      'https://img.logo.dev/ticker/4293.T?token=pk_test&format=png&size=64&retina=true&fallback=404',
    )
    expect(logoDevSrc(null, 'pk_test', 64)).toBeNull()
    expect(logoDevSrc('4293', null, 64)).toBeNull()
  })
})

describe('monogramChar', () => {
  test('株式会社を外して先頭の文字を返す', () => {
    expect(monogramChar('株式会社セプテーニ・ホールディングス')).toBe('セ')
    expect(monogramChar('トヨタ自動車株式会社')).toBe('ト')
  })
})

test('industryLabel は業種でない区分名を空欄にする', () => {
  expect(industryLabel('内国法人・組合（有価証券報告書等の提出義務者以外）')).toBeNull()
  expect(industryLabel('外国法人・組合')).toBeNull()
  expect(industryLabel(null)).toBeNull()
  expect(industryLabel('サービス業')).toBe('サービス業')
})
