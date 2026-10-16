// 一覧の絞り込み。読み上げと操作は素の select に任せる。
import { ChevronDownIcon } from 'lucide-react'

export function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: { value: string; label: string }[]
  onChange: (value: string) => void
}) {
  return (
    <label className="inline-flex items-center gap-2 text-sm font-bold text-ink">
      <span>{label}</span>
      <span className="relative inline-flex">
        <select
          aria-label={label}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="press h-11 max-w-[16rem] cursor-pointer appearance-none truncate rounded-[2px] border border-chrome bg-surface pr-9 pl-3 text-sm font-bold text-ink"
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDownIcon className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-ink" />
      </span>
    </label>
  )
}
