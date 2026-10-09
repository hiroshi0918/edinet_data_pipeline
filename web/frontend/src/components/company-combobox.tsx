// 企業セレクタ。searchRemote 時は API 部分一致、それ以外は全件をクライアントで絞る。
import { useQuery } from '@tanstack/react-query'
import { CheckIcon, ChevronsUpDownIcon, SearchIcon } from 'lucide-react'
import { useEffect, useState } from 'react'

import { CompanyMark } from '@/components/company-mark'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { fetchCompanies } from '@/lib/api'
import { tokyoTicker } from '@/lib/company-mark'
import type { CompanySummary } from '@/lib/types'

type CompanyComboboxProps = {
  selectedCode?: string
  selectedLabel?: string
  onSelect: (company: CompanySummary) => void
  placeholder?: string
  searchRemote?: boolean
  size?: 'default' | 'hero'
}

export function CompanyCombobox({
  selectedCode,
  selectedLabel,
  onSelect,
  placeholder = '企業を検索・選択',
  searchRemote = false,
  size = 'default',
}: CompanyComboboxProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')

  useEffect(() => {
    if (!searchRemote) return
    const timer = window.setTimeout(() => setDebouncedQuery(query), 250)
    return () => window.clearTimeout(timer)
  }, [query, searchRemote])

  const companiesQuery = useQuery({
    queryKey: ['companies', searchRemote ? debouncedQuery : 'all'],
    queryFn: () =>
      searchRemote
        ? fetchCompanies(debouncedQuery || undefined, 50)
        : fetchCompanies(),
    enabled: searchRemote ? open : true,
  })

  const companies = companiesQuery.data?.companies ?? []
  const selected = companies.find((item) => item.edinet_code === selectedCode)
  const showLogoCredit = Boolean(
    import.meta.env.VITE_LOGO_DEV_PUBLISHABLE_KEY &&
      companies.some((company) => tokyoTicker(company.securities_code)),
  )

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        {size === 'hero' ? (
          <button
            type="button"
            role="combobox"
            aria-expanded={open}
            aria-label="企業を検索・選択"
            className="press flex h-16 w-full cursor-pointer items-center gap-3 rounded-full border-[length:var(--line)] border-ink bg-page pr-2 pl-5 text-left text-base font-bold text-ink-soft sm:h-[4.5rem] sm:text-lg"
          >
            <SearchIcon className="size-6 shrink-0 text-ink" strokeWidth={2.5} />
            <span className="flex-1 truncate">{placeholder}</span>
            <span className="inline-flex h-12 shrink-0 items-center rounded-full border-[length:var(--line)] border-ink bg-shu px-5 text-base font-black text-page sm:h-14 sm:px-7">
              さがす
            </span>
          </button>
        ) : (
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            aria-label="企業を検索・選択"
            className="w-full justify-between"
          >
            <span className="flex min-w-0 items-center gap-2">
              <SearchIcon className="size-4 shrink-0" strokeWidth={2.5} />
              <span className="truncate">
                {selected
                  ? `${selected.company_name} (${selected.edinet_code})`
                  : selectedLabel
                    ? selectedLabel
                    : selectedCode
                      ? selectedCode
                      : placeholder}
              </span>
            </span>
            <ChevronsUpDownIcon className="ml-2 size-4 shrink-0 opacity-60" />
          </Button>
        )}
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-1.5" align="start">
        <Command shouldFilter={!searchRemote}>
          <CommandInput
            placeholder="会社名・コードで絞り込み"
            value={query}
            onValueChange={setQuery}
          />
          <CommandList>
            <CommandEmpty>
              {companiesQuery.isLoading ? '読み込み中…' : '該当する企業がありません'}
            </CommandEmpty>
            <CommandGroup>
              {companies.map((company) => (
                <CommandItem
                  key={company.edinet_code}
                  value={`${company.company_name} ${company.edinet_code} ${company.industry ?? ''}`}
                  onSelect={() => {
                    onSelect(company)
                    setOpen(false)
                  }}
                >
                  <CompanyMark
                    compact
                    name={company.company_name}
                    securitiesCode={company.securities_code}
                  />
                  <span className="truncate font-bold">{company.company_name}</span>
                  <span className="font-num ml-auto text-xs text-muted-foreground">
                    {company.edinet_code}
                  </span>
                  {company.edinet_code === selectedCode ? (
                    <CheckIcon className="size-4" />
                  ) : null}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
          {showLogoCredit ? (
            <a
              href="https://logo.dev"
              className="block px-3 pt-1 pb-1.5 text-center text-[10px] leading-none text-ink-soft underline decoration-ink-soft/60 underline-offset-2"
            >
              ロゴ: logo.dev
            </a>
          ) : null}
        </Command>
      </PopoverContent>
    </Popover>
  )
}
