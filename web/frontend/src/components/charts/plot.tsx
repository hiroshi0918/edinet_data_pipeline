// plotly.js の薄いラッパ。箱ひげと violin だけ使う。
import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'
import type { Config, Data, Layout } from 'plotly.js'

type PlotProps = {
  data: Data[]
  layout?: Partial<Layout>
  config?: Partial<Config>
  className?: string
  height?: number
}

export function Plot({ data, layout, config, className, height = 420 }: PlotProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const mergedLayout: Partial<Layout> = {
      autosize: true,
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Geist Variable, Hiragino Sans, sans-serif', size: 12 },
      margin: { l: 120, r: 24, t: 32, b: 48 },
      height,
      ...layout,
    }
    const mergedConfig: Partial<Config> = {
      responsive: true,
      displayModeBar: false,
      ...config,
    }
    void Plotly.react(el, data, mergedLayout, mergedConfig)
    return () => {
      Plotly.purge(el)
    }
  }, [data, layout, config, height])

  return <div ref={ref} className={className} data-testid="plotly-chart" />
}
