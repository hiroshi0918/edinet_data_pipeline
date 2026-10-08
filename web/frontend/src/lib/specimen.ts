// 提出者業種を標本の一字と絵のファイルに対応させる。
// 絵は業種ごとに1枚で、段階はキャプションだけが変わる。絵が無い業種は卵。

type Specimen = {
  label: string
  file: string | null
}

const PLAIN: Specimen = { label: '卵', file: null }

const SPECIMENS: Record<string, Specimen> = {
  鉄鋼: { label: '岩', file: '鉄鋼' },
  非鉄金属: { label: '晶', file: '非鉄金属' },
  鉱業: { label: '鉱', file: '鉱業' },
  金属製品: { label: '鈑', file: '金属製品' },
  'ガラス・土石製品': { label: '窯', file: 'ガラス・土石製品' },
  輸送用機器: { label: '車', file: '輸送用機器' },
  陸運業: { label: '路', file: '陸運業' },
  運輸業: { label: '路', file: '陸運業' },
  海運業: { label: '船', file: '海運業' },
  空運業: { label: '翼', file: '空運業' },
  '倉庫・運輸関連': { label: '倉', file: '倉庫・運輸関連' },
  '倉庫・運輸関連業': { label: '倉', file: '倉庫・運輸関連' },
  '水産・農林業': { label: '穂', file: '水産・農林業' },
  食料品: { label: '鍋', file: '食料品' },
  繊維製品: { label: '糸', file: '繊維製品' },
  'パルプ・紙': { label: '紙', file: 'パルプ・紙' },
  化学: { label: '瓶', file: '化学' },
  医薬品: { label: '薬', file: '医薬品' },
  '石油・石炭製品': { label: '炎', file: '石油・石炭製品' },
  ゴム製品: { label: '輪', file: 'ゴム製品' },
  機械: { label: '機', file: '機械' },
  電気機器: { label: '灯', file: '電気機器' },
  '電気・ガス業': { label: '電', file: '電気・ガス業' },
  精密機器: { label: '鏡', file: '精密機器' },
  建設業: { label: '棟', file: '建設業' },
  銀行業: { label: '庫', file: '銀行業' },
  '証券、商品先物取引業': { label: '秤', file: '証券、商品先物取引業' },
  保険業: { label: '盾', file: '保険業' },
  その他金融業: { label: '券', file: 'その他金融業' },
  小売業: { label: '店', file: '小売業' },
  卸売業: { label: '俵', file: '卸売業' },
  不動産業: { label: '邸', file: '不動産業' },
  '情報・通信業': { label: '信', file: '情報・通信業' },
  サービス業: { label: '傘', file: 'サービス業' },
  その他製品: { label: '箱', file: 'その他製品' },
  '内国法人・組合（有価証券報告書等の提出義務者以外）': PLAIN,
}

type SpecimenStage = 0 | 1 | 2 | 3 | 4

const STAGE_LABEL = ['たまご', 'こども', 'わかもの', 'おとな', 'おや'] as const

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

export function specimenCaption(industry: string | null | undefined, level: number | null | undefined): string {
  return `${specimenOf(industry).label}・${STAGE_LABEL[specimenStage(level)]}`
}

export function specimenPortrait(industry: string | null | undefined): string | null {
  const file = specimenOf(industry).file
  if (!file) return null
  return `/characters/${encodeURIComponent(file)}.png`
}
