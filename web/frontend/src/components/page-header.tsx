// 各ページ先頭の英字キッカー + 見出し。
export function PageHeader({
  kicker,
  title,
  description,
}: {
  kicker: string
  title: string
  description: string
}) {
  return (
    <div className="space-y-1">
      <p className="font-mono text-[11px] text-pencil">{kicker}</p>
      <h1 className="text-2xl text-ink">{title}</h1>
      <p className="max-w-3xl text-sm text-pencil">{description}</p>
    </div>
  )
}
