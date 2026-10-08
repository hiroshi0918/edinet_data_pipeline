// 企業セレクタ。searchRemote 時は API 部分一致、それ以外は全件をクライアントで絞る。
import { useQuery } from '@tanstack/react-query'
import { CheckIcon, ChevronsUpDownIcon } from 'lucide-react'
import { useEffect, useState } from 'react'

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
import type { CompanySummary } from '@/lib/types'

type CompanyComboboxProps = {
  selectedCode?: string
  selectedLabel?: string
  onSelect: (company: CompanySummary) => void
  placeholder?: string
  searchRemote?: boolean
}

export function CompanyCombobox({
  selectedCode,
  selectedLabel,
  onSelect,
  placeholder = '企業を検索・選択',
  searchRemote = false,
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

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-label="企業を検索・選択"
          className="w-full justify-between"
        >
          <span className="truncate">
            {selected
              ? `${selected.company_name} (${selected.edinet_code})`
              : selectedLabel
                ? selectedLabel
                : selectedCode
                  ? selectedCode
                  : placeholder}
          </span>
          <ChevronsUpDownIcon className="ml-2 size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
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
                  <span className="truncate">{company.company_name}</span>
                  <span className="ml-auto font-mono text-xs text-muted-foreground">
                    {company.edinet_code}
                  </span>
                  {company.edinet_code === selectedCode ? (
                    <CheckIcon className="size-4" />
                  ) : null}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
