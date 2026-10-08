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
      <p className="text-xs font-medium tracking-[0.18em] text-muted-foreground uppercase">
        {kicker}
      </p>
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="max-w-3xl text-sm text-muted-foreground">{description}</p>
    </div>
  )
}
