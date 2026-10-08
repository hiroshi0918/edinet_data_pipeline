// logo.dev のティッカー画像。証券コードか token が無いときは null。
export function logoDevSrc(
  securitiesCode: string | null | undefined,
  token: string | null | undefined,
  size: number,
  retry = 0,
): string | null {
  const ticker = tokyoTicker(securitiesCode)
  if (!token || !ticker) return null
  const params = new URLSearchParams({
    token,
    format: 'png',
    size: String(size),
    retina: 'true',
    fallback: '404',
  })
  if (retry > 0) params.set('retry', String(retry))
  return `https://img.logo.dev/ticker/${encodeURIComponent(ticker)}?${params}`
}

// 証券コードを東証ティッカーにする。EDINET が5桁の数字で持つときは先頭4桁。
export function tokyoTicker(securitiesCode: string | null | undefined): string | null {
  const code = securitiesCode?.trim()
  if (!code || !/^[0-9A-Za-z]{4,5}$/.test(code)) return null
  const symbol = /^\d{5}$/.test(code) ? code.slice(0, 4) : code
  return `${symbol}.T`
}

// 株式会社などの接頭辞を外した、社名の先頭1文字。
export function monogramChar(companyName: string): string {
  const stripped = companyName.replace(/^\s*(株式会社|（株）|\(株\)|㈱)\s*/, '').trim()
  const source = stripped || companyName.trim()
  return Array.from(source)[0] ?? '・'
}
