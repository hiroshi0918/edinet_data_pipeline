---
version: alpha
name: PlayStation-design-analysis
description: |
  会社図鑑に当てる PlayStation の画面。黒・白・PlayStation Blue の帯が章になる。見出しは細い字、進むボタンは青い丸 pill、カードは角 8px で影を置かない。
source: https://github.com/VoltAgent/awesome-design-md/blob/main/design-md/playstation/DESIGN.md

colors:
  primary: "#0070d1"
  primary-pressed: "#0064b7"
  primary-active: "#004d8d"
  on-primary: "#ffffff"
  link: "#0064b7"
  link-dark: "#53b1ff"
  commerce: "#d53b00"
  warning: "#c81b3a"
  ink: "#000000"
  body: "rgba(0,0,0,0.6)"
  mute: "#6b6b6b"
  ash: "#cccccc"
  canvas: "#ffffff"
  surface-soft: "#f3f3f3"
  surface-card: "#f5f7fa"
  canvas-dark: "#000000"
  surface-dark-elevated: "#121314"
  surface-dark-card: "#181818"
  on-dark: "#ffffff"

typography:
  display:
    fontFamily: Noto Sans JP
    fontSize: 54px
    fontWeight: 300
    lineHeight: 1.25
  heading:
    fontFamily: Noto Sans JP
    fontSize: 28px
    fontWeight: 300
    lineHeight: 1.25
  body:
    fontFamily: Noto Sans JP
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.5
  button:
    fontFamily: Noto Sans JP
    fontSize: 14px
    fontWeight: 700
    lineHeight: 1.25

rounded:
  none: 0px
  sm: 4px
  md: 8px
  lg: 16px
  full: 9999px
---

# PlayStation を会社図鑑に当てる

出典は [VoltAgent/awesome-design-md の playstation](https://github.com/VoltAgent/awesome-design-md/blob/main/design-md/playstation/DESIGN.md)。PlayStation のロゴ、商標、ストアの文言は使わない。書体 SST はプロプライエタリなので、日本語の代替として Noto Sans JP を使う。見出しは weight 300。

## 三つの面

- **黒** (`#000000`): 表紙の導入、ナビ、「ほかの入り方」。
- **白** (`#ffffff`): 本文、業種の目次、会社シート以降。
- **PlayStation Blue** (`#0070d1`): 進むボタンと、ページ末尾のフッター。青い帯はフッターだけ。

面の切り替わりが区切りになる。帯と帯のあいだに飾り線は置かない。

## 形

- 進むボタン、絞り込み、検索は `rounded-full`。高さは 48px。
- カード、業種タイル、ダイアログの中身は角 8px。休止時の影は置かない。
- 入力欄は角 4px。フォーカスは 2px の `#0070d1`。ぼかしの輪は付けない。
- 橙 `#d53b00` は注意の印だけ。買うボタンはこのアプリには無い。

## 文字

- ページの題と節の題は細く、大きく。
- 本文は 16px、行間 1.5。補足は `#6b6b6b` か黒の 60%。
- 数字は `font-num`。
