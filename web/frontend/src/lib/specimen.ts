// 提出者業種を標本の一字と絵のファイルに対応させる。
// 絵は業種ごとに1枚で、段階はキャプションだけが変わる。絵が無い業種は卵。
// 図鑑番号は東証33業種の並び。卵は 0。

type Specimen = {
  label: string
  file: string | null
  no: number
}

const PLAIN: Specimen = { label: '卵', file: null, no: 0 }

const SPECIMENS: Record<string, Specimen> = {
  '水産・農林業': { label: '穂', file: '水産・農林業', no: 1 },
  鉱業: { label: '鉱', file: '鉱業', no: 2 },
  建設業: { label: '棟', file: '建設業', no: 3 },
  食料品: { label: '鍋', file: '食料品', no: 4 },
  繊維製品: { label: '糸', file: '繊維製品', no: 5 },
  'パルプ・紙': { label: '紙', file: 'パルプ・紙', no: 6 },
  化学: { label: '瓶', file: '化学', no: 7 },
  医薬品: { label: '薬', file: '医薬品', no: 8 },
  '石油・石炭製品': { label: '炎', file: '石油・石炭製品', no: 9 },
  ゴム製品: { label: '輪', file: 'ゴム製品', no: 10 },
  'ガラス・土石製品': { label: '窯', file: 'ガラス・土石製品', no: 11 },
  鉄鋼: { label: '岩', file: '鉄鋼', no: 12 },
  非鉄金属: { label: '晶', file: '非鉄金属', no: 13 },
  金属製品: { label: '鈑', file: '金属製品', no: 14 },
  機械: { label: '機', file: '機械', no: 15 },
  電気機器: { label: '灯', file: '電気機器', no: 16 },
  輸送用機器: { label: '車', file: '輸送用機器', no: 17 },
  精密機器: { label: '鏡', file: '精密機器', no: 18 },
  その他製品: { label: '箱', file: 'その他製品', no: 19 },
  '電気・ガス業': { label: '電', file: '電気・ガス業', no: 20 },
  陸運業: { label: '路', file: '陸運業', no: 21 },
  運輸業: { label: '路', file: '陸運業', no: 21 },
  海運業: { label: '船', file: '海運業', no: 22 },
  空運業: { label: '翼', file: '空運業', no: 23 },
  '倉庫・運輸関連業': { label: '倉', file: '倉庫・運輸関連', no: 24 },
  '倉庫・運輸関連': { label: '倉', file: '倉庫・運輸関連', no: 24 },
  '情報・通信業': { label: '信', file: '情報・通信業', no: 25 },
  卸売業: { label: '俵', file: '卸売業', no: 26 },
  小売業: { label: '店', file: '小売業', no: 27 },
  銀行業: { label: '庫', file: '銀行業', no: 28 },
  '証券、商品先物取引業': { label: '秤', file: '証券、商品先物取引業', no: 29 },
  保険業: { label: '盾', file: '保険業', no: 30 },
  その他金融業: { label: '券', file: 'その他金融業', no: 31 },
  不動産業: { label: '邸', file: '不動産業', no: 32 },
  サービス業: { label: '傘', file: 'サービス業', no: 33 },
  '内国法人・組合（有価証券報告書等の提出義務者以外）': PLAIN,
}

export type SpecimenStage = 0 | 1 | 2 | 3 | 4

export const STAGE_LABEL = ['たまご', 'こども', 'わかもの', 'おとな', 'おや'] as const

function specimenOf(industry: string | null | undefined): Specimen {
  const key = industry?.trim()
  if (!key) return PLAIN
  return SPECIMENS[key] ?? PLAIN
}

// 0–39 こども、40–69 わかもの、70–84 おとな、85–100 おや。点がないときだけたまご。
export function specimenStage(level: number | null | undefined): SpecimenStage {
  if (level == null || Number.isNaN(level)) return 0
  if (level < 40) return 1
  if (level < 70) return 2
  if (level < 85) return 3
  return 4
}

export function specimenLabel(industry: string | null | undefined): string {
  return specimenOf(industry).label
}

export function specimenCaption(industry: string | null | undefined, level: number | null | undefined): string {
  return `${specimenOf(industry).label}・${STAGE_LABEL[specimenStage(level)]}`
}

export function specimenNo(industry: string | null | undefined): string {
  return `No.${String(specimenOf(industry).no).padStart(3, '0')}`
}

function characterPath(dir: 'webp' | 'thumb', file: string): string {
  return `/characters/${dir}/${encodeURIComponent(file)}.webp`
}

export function specimenPortrait(industry: string | null | undefined): string | null {
  const file = specimenOf(industry).file
  return file ? characterPath('webp', file) : null
}

export function specimenThumb(industry: string | null | undefined): string | null {
  const file = specimenOf(industry).file
  return file ? characterPath('thumb', file) : null
}

export type IndustryEntry = {
  industry: string
  no: string
  label: string
  companyCount: number | null
}

// 目次の1マス。絵ごとに1つで、別名の社数は足し合わせる。
// リンク先は社数の多い業種名にする。ランキングは業種名の完全一致で絞るため。
export function industryIndex(
  counts: { industry: string | null; company_count: number }[] | undefined,
): IndustryEntry[] {
  const groups = new Map<number, { names: Map<string, number>; specimen: Specimen; canonical: string }>()
  for (const [name, specimen] of Object.entries(SPECIMENS)) {
    if (!groups.has(specimen.no)) groups.set(specimen.no, { names: new Map(), specimen, canonical: name })
  }
  for (const row of counts ?? []) {
    const specimen = specimenOf(row.industry)
    const group = groups.get(specimen.no)
    if (!group || !row.industry) continue
    group.names.set(row.industry, (group.names.get(row.industry) ?? 0) + row.company_count)
  }
  return [...groups.values()]
    .filter((group) => group.specimen.no !== 0 || group.names.size > 0)
    .sort((left, right) => (left.specimen.no || 99) - (right.specimen.no || 99))
    .map((group) => {
      const ranked = [...group.names.entries()].sort((left, right) => right[1] - left[1])
      const total = ranked.reduce((sum, [, count]) => sum + count, 0)
      return {
        industry: ranked[0]?.[0] ?? group.canonical,
        no: `No.${String(group.specimen.no).padStart(3, '0')}`,
        label: group.specimen.label,
        companyCount: counts ? total : null,
      }
    })
}

// EDINET の「提出者業種」には、業種ではない区分名（有報の提出義務が無い法人など）が混ざる。
// 一覧の業種欄ではこれを出さず空欄にする。
const NON_INDUSTRY_PATTERN = /(法人|組合|個人|政府)/

export function industryLabel(industry: string | null | undefined): string | null {
  if (!industry) return null
  return NON_INDUSTRY_PATTERN.test(industry) ? null : industry
}
