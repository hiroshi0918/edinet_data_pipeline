// LT スライド生成 — Theme: Jobs Stage (Charcoal Minimal)
// 台本: docs/LT_script.md

const pptxgen = require("pptxgenjs");
const fs = require("fs");
const CHART = JSON.parse(fs.readFileSync("chartdata.json", "utf8"));
const R2DATA = JSON.parse(fs.readFileSync("r2_data.json", "utf8"));
const CHILD = JSON.parse(fs.readFileSync("childcare_hist.json", "utf8"));

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10" x 5.625"
pres.author = "寺嶋 裕";
pres.title = "EDINET 4,000 社を覗いて見えた『見えていない格差』";

// === Theme: Jobs Stage (Light) ===
const BG = "FFFFFF";        // 白背景
const BG_LIGHT = "0A0A0A";  // 反転用
const FG = "0A0A0A";        // メインテキスト (ほぼ黒)
const FG_DARK = "FFFFFF";   // 反転背景用
const MUTED = "666666";     // サブテキスト
const ACCENT = "FF3B30";    // アクセント赤
const RULE = "E0E0E0";      // 罫線 (薄いグレー)

const FONT_HEAD = "Arial Black";
const FONT_BODY = "Calibri Light";
const FONT_CODE = "Consolas";

// helper: フッタ（控えめページ番号）
function addFooter(slide, num, total, dark = true) {
  slide.addText(`${num} / ${total}`, {
    x: 9.0, y: 5.25, w: 0.9, h: 0.3,
    fontSize: 9, fontFace: FONT_BODY,
    color: dark ? MUTED : MUTED,
    align: "right", valign: "middle", margin: 0,
  });
}

const TOTAL = 13;

// === Speaker Notes (キーポイント箇条書きメモ) ===
const NOTES = {
  1: `- タイトル読み上げ
- 名乗る、よろしく`,

  2: `- 経歴3社を順に
- 1社目: SMBC日興 (営業) → 有報を読む下地
- 2社目: ビジネスコーチ (PM) → 人的資本という言葉に出会う
- 在籍中に開示義務化開始 (偶然のタイミング)
- 動機:「データ取ったら面白いんじゃない？」
- 3社目 FLINTERS BASE 移籍後に個人プロジェクト化`,

  3: `- EDINET = 金融庁の有報電子開示システム
- 提出義務: 全上場 (約4,000社) + 株主1,000人以上の非上場 = 計約4,300社
- 2023年3月期決算から義務化された塊は2つ:
  ① 人材育成・社内環境の方針 (文章)
  ② 数値3指標 (女性管理職比率/男性育休取得率/男女の賃金格差)
- 4,300社×2年分を分析した
- 「楽しみに始めたんですが——」で次へ橋渡し`,

  4: `- 構成はざっくり: EDINET API → PostgreSQL → DuckDB/Parquet → Streamlit
- 運用DBと分析DBを分離 (← 失敗談の伏線)
- 詳細は GitHub README`,

  5: `- 分析の道のりをそのまま話す形式
- ① 業界別指標、② 売上との相関、③ 気づき
- ③「気づき」が今日いちばん伝えたいこと`,

  6: `- 女性管理職比率の業界平均: 下位5(グレー) vs 上位5(赤)
- 下=重工業系 約3-4% (鉄鋼が最低)
- 上=サービス・情報通信・金融系 約16-21% (サービス業21%)
- 最大7倍の差
- メッセージ: 個社の数字は業界平均と比べないと意味がない`,

  7: `- 男性育休取得率の業界平均
- 下=流通系 約47-54% (倉庫・小売・卸売・サービス)
- 上=金融・公益系 約70-94% (銀行業94.5%が最高)
- 最大2倍の差
- 構図: 金融・公益で取得率高、流通で低`,

  8: `- 男女の賃金格差 (100=平等、低い=女性給与少)
- 上の赤=重工業系60-69% (最も平等寄り)
- 下のグレー=金融系38-47% (証券・先物38%が最低 = 格差最大)
- ★ 伏線投げ:「金融系は育休取得率高いのに賃金格差はワースト。なぜ？」
- → スライド10で回収`,

  9: `- 売上規模で3指標を回帰した結果
- R² の説明は1行:「1=完全説明 / 0=無関係」
- 数字: 0.035 / 0.001 / 0.012 (順に読み上げ、0.001で間)
- 3つともほぼゼロ = 規模では予測できない
- ★ ただし「本当に規模と無関係?」と疑問形で締めて次へ橋渡し`,

  10: `- 今日のメイン
- 算出式を3指標とも調べたら、全部に欠陥があった

[1] 女性管理職比率 = 女性管理職 ÷ 全管理職
  → 女性社員の母数を見ていない (女性社員10%なら構造的に当然)

[2] 男性育休取得率 = 取得男性 ÷ 配偶者出産男性
  → 取得期間を見ていない (1日も半年も同じ100%)

[3] 男女の賃金格差 = 女性平均賃金 ÷ 男性平均賃金
  → 4要因が混在: ①真の差別 ②非正規率差 ③職階差 ④勤続差
  → 非正規率: 男22% / 女53% → これだけで大きく動く

- ★ Slide8伏線回収: 金融系の格差大は「女性社員の多くが非正規・一般職」の構成効果
- 分析2のR²がほぼゼロも、指標がノイズだらけだったせいかもしれない`,

  11: `- 学び3つを言い直す
  1. 相対的に見る (絶対値だけでは判断不能)
  2. 相関を見る (ただし指標が正しい前提)
  3. 指標の背景を読む ← 今日いちばん伝えたい
- メインメッセージ: 数字の前に、指標が何を測っているかを必ず確認`,

  12: `- 笑いトーンで:「いちばん伝えたかったかも (笑)」
- AIに「テスト走らせて」→ 全グリーン
- DB確認したら 8,481行 → 2行
- 原因: テストのTRUNCATEが環境変数間違いで本番に着弾
- 救い: 分析DBを別系統にしていた (序盤の伏線回収)
- 結び: AI時代の安全装置は人間が事前に仕込む

★ 読み方:「8,481行 → 2行」で2秒沈黙`,

  13: `- お礼
- Streamlit Cloud: edinet-dashboard.streamlit.app
- GitHub (public): github.com/hiroshi0918
- 「興味ある業界を覗いてみて」で締め`,
};

// =========================================================
// Slide 1: タイトル
// =========================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  // 小さなラベル
  s.addText("LT / 2026", {
    x: 0.6, y: 0.5, w: 3, h: 0.3,
    fontSize: 11, fontFace: FONT_BODY,
    color: MUTED, charSpacing: 4, margin: 0,
  });

  // 4000 をアクセントにしたタイトル
  s.addText([
    { text: "4,300", options: { color: ACCENT, bold: true } },
    { text: "社の", options: { color: FG, breakLine: true } },
    { text: "人的資本データ分析してみた", options: { color: FG } },
  ], {
    x: 0.6, y: 1.6, w: 8.8, h: 2.6,
    fontSize: 40, fontFace: FONT_HEAD, bold: true,
    align: "left", valign: "middle", margin: 0,
    paraSpaceAfter: 6,
  });

  // 著者
  s.addText("寺嶋 裕 (Hiroshi Terashima)", {
    x: 0.6, y: 4.7, w: 8.8, h: 0.4,
    fontSize: 13, fontFace: FONT_BODY,
    color: FG, align: "left", valign: "middle", margin: 0,
  });

  s.addNotes(NOTES[1]);
}

// =========================================================
// Slide 2: 自己紹介
// =========================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  // === 左カラム: テキスト ===
  s.addText("自己紹介", {
    x: 0.4, y: 0.4, w: 4.5, h: 0.45,
    fontSize: 13, fontFace: FONT_BODY,
    color: MUTED, charSpacing: 4, margin: 0,
  });

  s.addText("寺嶋 裕", {
    x: 0.4, y: 0.9, w: 4.5, h: 0.8,
    fontSize: 36, fontFace: FONT_HEAD, bold: true,
    color: FG, align: "left", valign: "middle", margin: 0,
  });
  s.addText("テラシマ ヒロシ", {
    x: 0.4, y: 1.75, w: 4.5, h: 0.3,
    fontSize: 12, fontFace: FONT_BODY,
    color: MUTED, align: "left", valign: "middle", margin: 0,
  });

  // 区切り
  s.addShape(pres.shapes.LINE, {
    x: 0.4, y: 2.3, w: 0.5, h: 0,
    line: { color: ACCENT, width: 2 },
  });

  // 経歴 3 社
  const jobs = [
    { n: "1", company: "SMBC 日興証券株式会社", role: "営業" },
    { n: "2", company: "ビジネスコーチ株式会社", role: "アプリ開発 PM" },
    { n: "3", company: "株式会社 FLINTERS BASE", role: "データエンジニア" },
  ];

  jobs.forEach((j, i) => {
    const y = 2.6 + i * 0.75;
    s.addText(j.n, {
      x: 0.4, y, w: 0.7, h: 0.55,
      fontSize: 20, fontFace: FONT_HEAD, bold: true,
      color: ACCENT, align: "left", valign: "middle", margin: 0,
    });
    s.addText(j.company, {
      x: 1.15, y, w: 3.8, h: 0.35,
      fontSize: 14, fontFace: FONT_HEAD, bold: true,
      color: FG, align: "left", valign: "middle", margin: 0,
    });
    s.addText(j.role, {
      x: 1.15, y: y + 0.32, w: 3.8, h: 0.3,
      fontSize: 11, fontFace: FONT_BODY,
      color: MUTED, align: "left", valign: "middle", margin: 0,
    });
  });

  // === 右カラム: スノボ写真 (FLINTERS BASE メンバーと 2025 冬) ===
  // 元画像は 1477x1108 (アスペクト比 1.33:1) — 必ずアスペクト維持
  const photoRatio = 1477 / 1108;
  // 集合写真 (メイン)
  const groupH = 3.4;
  const groupW = groupH * photoRatio; // 4.52
  s.addImage({
    path: "logos/snow_group.jpg",
    x: 5.05, y: 0.5, w: groupW, h: groupH,
  });
  // 自撮り (サブ、右下に少し重ねて)
  const selfH = 1.85;
  const selfW = selfH * photoRatio; // 2.46
  s.addImage({
    path: "logos/snow_two.jpg",
    x: 5.05 + groupW - selfW - 0.05, y: 0.5 + groupH - 0.3,
    w: selfW, h: selfH,
  });
  // キャプション
  s.addText("FLINTERS BASE メンバーと / 2025 冬", {
    x: 5.05, y: 5.3, w: groupW, h: 0.25,
    fontSize: 9, fontFace: FONT_BODY,
    italic: true, color: MUTED, align: "left", valign: "middle", margin: 0,
  });

  s.addNotes(NOTES[2]);
  addFooter(s, 2, TOTAL);
}

// =========================================================
// Slide 3: EDINET と人的資本開示
// =========================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  s.addText("EDINET と人的資本開示", {
    x: 0.6, y: 0.7, w: 9, h: 0.7,
    fontSize: 30, fontFace: FONT_HEAD, bold: true,
    color: FG, align: "left", valign: "middle", margin: 0,
  });

  // EDINET 説明（1行に統合）
  s.addText([
    { text: "EDINET", options: { color: ACCENT, bold: true } },
    { text: " : 金融庁の有価証券報告書DB / 約4,300社", options: { color: FG } },
  ], {
    x: 0.6, y: 1.95, w: 9, h: 0.5,
    fontSize: 16, fontFace: FONT_BODY,
    align: "left", valign: "middle", margin: 0,
  });

  // 区切り
  s.addShape(pres.shapes.LINE, {
    x: 0.6, y: 2.85, w: 8.8, h: 0,
    line: { color: RULE, width: 1 },
  });

  // 義務化された開示
  s.addText("2023 年 3 月期決算 〜 義務化", {
    x: 0.6, y: 3.0, w: 6, h: 0.4,
    fontSize: 14, fontFace: FONT_HEAD, bold: true,
    color: ACCENT, align: "left", valign: "middle", margin: 0,
  });

  s.addText([
    { text: "① ", options: { color: MUTED } },
    { text: "人材育成・社内環境の方針", options: { color: FG, breakLine: true } },
    { text: "② ", options: { color: MUTED } },
    { text: "数値3指標: 女性管理職比率 / 男性育休取得率 / 男女の賃金格差", options: { color: FG, bold: true } },
  ], {
    x: 0.6, y: 3.45, w: 9, h: 1.2,
    fontSize: 17, fontFace: FONT_BODY,
    align: "left", valign: "top", margin: 0,
    paraSpaceAfter: 6,
  });

  s.addNotes(NOTES[3]);
  addFooter(s, 3, TOTAL);
}

// =========================================================
// Slide 4: アーキテクチャ
// =========================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  s.addText("パイプライン全体像", {
    x: 0.6, y: 0.7, w: 9, h: 0.7,
    fontSize: 30, fontFace: FONT_HEAD, bold: true,
    color: FG, align: "left", valign: "middle", margin: 0,
  });

  // フロー: 4つのボックスを横並び（ロゴ + ラベル）
  const boxes = [
    { label: "EDINET", sub: "公開データ", logo: null, logoRatio: null, skipLabel: true },
    { label: "PostgreSQL", sub: "運用DB", logo: "logos/postgres.png", logoRatio: 540 / 557 },
    { label: "DuckDB", sub: "分析DB", logo: "logos/duckdb.png", logoRatio: 770 / 592, skipLabel: true },
    { label: "Streamlit", sub: "可視化", logo: "logos/streamlit.png", logoRatio: 601 / 330 },
  ];
  const boxW = 2.0, boxH = 2.1, gap = 0.25;
  const totalW = boxes.length * boxW + (boxes.length - 1) * gap;
  const startX = (10 - totalW) / 2;
  const boxY = 2.0;

  boxes.forEach((b, i) => {
    const x = startX + i * (boxW + gap);
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: boxY, w: boxW, h: boxH,
      fill: { color: BG },
      line: { color: RULE, width: 1.5 },
    });

    // ロゴ領域 (上部)
    const logoMaxH = 0.95;
    const logoMaxW = boxW - 0.5;
    const logoAreaY = boxY + 0.2;
    if (b.logo) {
      // アスペクト比を保ってフィット
      let logoH = logoMaxH;
      let logoW = logoH * b.logoRatio;
      if (logoW > logoMaxW) {
        logoW = logoMaxW;
        logoH = logoW / b.logoRatio;
      }
      const logoX = x + (boxW - logoW) / 2;
      const logoY = logoAreaY + (logoMaxH - logoH) / 2;
      s.addImage({ path: b.logo, x: logoX, y: logoY, w: logoW, h: logoH });
    } else {
      // EDINET はテキストで（公式ロゴ非利用）
      s.addText("EDINET", {
        x, y: logoAreaY, w: boxW, h: logoMaxH,
        fontSize: 18, fontFace: FONT_HEAD, bold: true,
        color: FG, align: "center", valign: "middle", margin: 0,
      });
    }

    // ラベル (下部) — 画像や中央テキストに名前が入っている場合はスキップ
    if (!b.skipLabel) {
      s.addText(b.label, {
        x, y: boxY + 1.25, w: boxW, h: 0.4,
        fontSize: 13, fontFace: FONT_HEAD, bold: true,
        color: FG, align: "center", valign: "middle", margin: 0,
      });
    }
    s.addText(b.sub, {
      x, y: boxY + 1.65, w: boxW, h: 0.35,
      fontSize: 11, fontFace: FONT_BODY,
      color: MUTED, align: "center", valign: "middle", margin: 0,
    });

    // 矢印（最後を除く）
    if (i < boxes.length - 1) {
      const arrowX = x + boxW + 0.02;
      const arrowY = boxY + boxH / 2;
      s.addShape(pres.shapes.LINE, {
        x: arrowX, y: arrowY, w: gap - 0.04, h: 0,
        line: { color: ACCENT, width: 2, endArrowType: "triangle" },
      });
    }
  });

  s.addNotes(NOTES[4]);
  addFooter(s, 4, TOTAL);
}

// =========================================================
// Slide 5: 今日の流れ (伏線型予告)
// =========================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  s.addText("Agenda", {
    x: 0.6, y: 0.4, w: 5, h: 0.45,
    fontSize: 13, fontFace: FONT_BODY,
    color: MUTED, charSpacing: 4, margin: 0,
  });
  s.addText("発表内容", {
    x: 0.6, y: 0.85, w: 9, h: 0.7,
    fontSize: 30, fontFace: FONT_HEAD, bold: true,
    color: FG, align: "left", valign: "middle", margin: 0,
  });

  const flow = [
    { n: "1", t: "業界別指標" },
    { n: "2", t: "売上規模との相関" },
    { n: "3", t: "気づき" },
  ];

  flow.forEach((it, i) => {
    const y = 2.05 + i * 1.0;
    s.addText(it.n, {
      x: 0.6, y, w: 1.0, h: 0.85,
      fontSize: 40, fontFace: FONT_HEAD, bold: true,
      color: i === 2 ? ACCENT : MUTED, align: "left", valign: "middle", margin: 0,
    });
    s.addText(it.t, {
      x: 1.7, y, w: 7.8, h: 0.85,
      fontSize: 22, fontFace: FONT_HEAD, bold: true,
      color: i === 2 ? ACCENT : FG, align: "left", valign: "middle", margin: 0,
    });
  });

  s.addNotes(NOTES[5]);
  addFooter(s, 5, TOTAL);
}

// =========================================================
// Slide 6: 衝撃①  業界格差
// =========================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  s.addText("分析 1", {
    x: 0.6, y: 0.4, w: 9, h: 0.45,
    fontSize: 13, fontFace: FONT_BODY,
    color: MUTED, charSpacing: 4, margin: 0,
  });
  s.addText("女性管理職比率", {
    x: 0.6, y: 0.85, w: 9, h: 0.5,
    fontSize: 22, fontFace: FONT_HEAD, bold: true,
    color: FG, align: "left", valign: "middle", margin: 0,
  });

  // 横棒グラフ: 下位5 + 上位5 を1系列で
  const bars = [...CHART.industry_low, ...CHART.industry_high];
  const labels = bars.map(b => b.label);
  const values = bars.map(b => b.value);
  // 各バーの色（下位=グレー、上位=赤）
  const barColors = labels.map((_, i) => (i < 5 ? "BBBBBB" : "FF3B30"));

  s.addChart(pres.charts.BAR, [{
    name: "女性管理職比率(%)",
    labels,
    values,
  }], {
    x: 0.6, y: 1.7, w: 8.8, h: 3.2,
    barDir: "bar",
    chartColors: barColors,
    chartColorsOpacity: 100,
    chartArea: { fill: { color: BG } },
    plotArea: { fill: { color: BG } },
    catAxisLabelColor: FG, catAxisLabelFontSize: 11, catAxisLabelFontFace: FONT_BODY,
    valAxisLabelColor: MUTED, valAxisLabelFontSize: 10, valAxisLabelFontFace: FONT_BODY,
    valGridLine: { color: RULE, size: 0.5 },
    catGridLine: { style: "none" },
    showValue: true, dataLabelPosition: "outEnd",
    dataLabelColor: FG, dataLabelFontSize: 10, dataLabelFontFace: FONT_BODY,
    dataLabelFormatCode: "0.0",
    showLegend: false,
    barGapWidthPct: 50,
  });

  s.addNotes(NOTES[6]);
  addFooter(s, 6, TOTAL);
}

// =========================================================
// Slide 7: 分析 1b - 業界別 男性育休取得率
// =========================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  s.addText("分析 1", {
    x: 0.6, y: 0.4, w: 9, h: 0.45,
    fontSize: 13, fontFace: FONT_BODY,
    color: MUTED, charSpacing: 4, margin: 0,
  });
  s.addText("男性育休取得率", {
    x: 0.6, y: 0.85, w: 9, h: 0.5,
    fontSize: 22, fontFace: FONT_HEAD, bold: true,
    color: FG, align: "left", valign: "middle", margin: 0,
  });

  const bars7 = [...CHART.childcare_low, ...CHART.childcare_high];
  const labels7 = bars7.map(b => b.label);
  const values7 = bars7.map(b => b.value);
  const colors7 = labels7.map((_, i) => (i < 5 ? "BBBBBB" : "FF3B30"));

  s.addChart(pres.charts.BAR, [{
    name: "男性育休取得率(%)",
    labels: labels7,
    values: values7,
  }], {
    x: 0.6, y: 1.7, w: 8.8, h: 3.2,
    barDir: "bar",
    chartColors: colors7,
    chartColorsOpacity: 100,
    chartArea: { fill: { color: BG } },
    plotArea: { fill: { color: BG } },
    catAxisLabelColor: FG, catAxisLabelFontSize: 11, catAxisLabelFontFace: FONT_BODY,
    valAxisLabelColor: MUTED, valAxisLabelFontSize: 10, valAxisLabelFontFace: FONT_BODY,
    valGridLine: { color: RULE, size: 0.5 },
    catGridLine: { style: "none" },
    showValue: true, dataLabelPosition: "outEnd",
    dataLabelColor: FG, dataLabelFontSize: 10, dataLabelFontFace: FONT_BODY,
    dataLabelFormatCode: "0.0",
    showLegend: false,
    barGapWidthPct: 50,
  });

  s.addNotes(NOTES[7]);
  addFooter(s, 7, TOTAL);
}

// =========================================================
// Slide 8: 分析 1c - 業界別 男女の賃金格差
// =========================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  s.addText("分析 1", {
    x: 0.6, y: 0.4, w: 9, h: 0.45,
    fontSize: 13, fontFace: FONT_BODY,
    color: MUTED, charSpacing: 4, margin: 0,
  });
  s.addText("男女の賃金格差", {
    x: 0.6, y: 0.85, w: 9, h: 0.5,
    fontSize: 22, fontFace: FONT_HEAD, bold: true,
    color: FG, align: "left", valign: "middle", margin: 0,
  });

  const bars8 = [...CHART.wage_low, ...CHART.wage_high];
  const labels8 = bars8.map(b => b.label);
  const values8 = bars8.map(b => b.value);
  // 全グラフ統一: 数字が大きい側 (上位5) を赤
  // 賃金格差は 100=平等 なので 赤=平等寄り、グレー=格差大 となる
  const colors8 = labels8.map((_, i) => (i < 5 ? "BBBBBB" : "FF3B30"));

  s.addChart(pres.charts.BAR, [{
    name: "男女の賃金格差(%)",
    labels: labels8,
    values: values8,
  }], {
    x: 0.6, y: 1.7, w: 8.8, h: 3.2,
    barDir: "bar",
    chartColors: colors8,
    chartColorsOpacity: 100,
    chartArea: { fill: { color: BG } },
    plotArea: { fill: { color: BG } },
    catAxisLabelColor: FG, catAxisLabelFontSize: 11, catAxisLabelFontFace: FONT_BODY,
    valAxisLabelColor: MUTED, valAxisLabelFontSize: 10, valAxisLabelFontFace: FONT_BODY,
    valGridLine: { color: RULE, size: 0.5 },
    catGridLine: { style: "none" },
    showValue: true, dataLabelPosition: "outEnd",
    dataLabelColor: FG, dataLabelFontSize: 10, dataLabelFontFace: FONT_BODY,
    dataLabelFormatCode: "0.0",
    showLegend: false,
    barGapWidthPct: 50,
  });

  s.addNotes(NOTES[8]);
  addFooter(s, 8, TOTAL);
}

// =========================================================
// Slide 9: 分析 2 - 規模では説明できない (3指標 R² 比較)
// =========================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  s.addText("分析 2", {
    x: 0.6, y: 0.4, w: 9, h: 0.45,
    fontSize: 13, fontFace: FONT_BODY,
    color: MUTED, charSpacing: 4, margin: 0,
  });
  s.addText("売上規模との相関は、ほぼゼロ", {
    x: 0.6, y: 0.85, w: 9, h: 0.55,
    fontSize: 22, fontFace: FONT_HEAD, bold: true,
    color: FG, align: "left", valign: "middle", margin: 0,
  });

  // 3指標の R² 値
  const r2items = [
    { key: "female_manager_ratio", label: "女性管理職比率" },
    { key: "male_childcare_leave_ratio", label: "男性育休取得率" },
    { key: "gender_wage_gap", label: "男女の賃金格差" },
  ];

  // 3カラム配置
  const colW = 3.0, colGap = 0.15;
  const colsTotalW = r2items.length * colW + (r2items.length - 1) * colGap;
  const colStartX = (10 - colsTotalW) / 2;
  const colY = 1.6;
  const colH = 2.6;

  r2items.forEach((item, i) => {
    const data = R2DATA.r2[item.key];
    const r2 = data.r2;
    const x = colStartX + i * (colW + colGap);

    // カードの薄い枠
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: colY, w: colW, h: colH,
      fill: { color: BG }, line: { color: RULE, width: 1 },
    });

    // 指標名
    s.addText(item.label, {
      x, y: colY + 0.2, w: colW, h: 0.4,
      fontSize: 14, fontFace: FONT_HEAD, bold: true,
      color: FG, align: "center", valign: "middle", margin: 0,
    });

    // R² ラベル
    s.addText("R²", {
      x, y: colY + 0.7, w: colW, h: 0.3,
      fontSize: 12, fontFace: FONT_BODY,
      color: MUTED, align: "center", valign: "middle", margin: 0,
    });

    // R² 値 (大)
    s.addText(r2.toFixed(3), {
      x, y: colY + 1.0, w: colW, h: 1.0,
      fontSize: 56, fontFace: FONT_HEAD, bold: true,
      color: ACCENT, align: "center", valign: "middle", margin: 0,
    });

    // 視覚バー (0〜1 のスケール、R² 値分を塗る、最小視認幅を保証)
    const barInnerW = colW - 0.6;
    const barX = x + 0.3;
    const barY = colY + 2.15;
    const barH = 0.12;
    s.addShape(pres.shapes.RECTANGLE, {
      x: barX, y: barY, w: barInnerW, h: barH,
      fill: { color: RULE }, line: { color: RULE, width: 0 },
    });
    const fillW = Math.max(barInnerW * r2, 0.02);
    s.addShape(pres.shapes.RECTANGLE, {
      x: barX, y: barY, w: fillW, h: barH,
      fill: { color: ACCENT }, line: { color: ACCENT, width: 0 },
    });

    // 補足 (xx% しか説明しない)
    s.addText(`売上で ${(r2 * 100).toFixed(1)}% しか説明しない`, {
      x, y: colY + 2.32, w: colW, h: 0.3,
      fontSize: 10, fontFace: FONT_BODY,
      italic: true, color: MUTED, align: "center", valign: "middle", margin: 0,
    });
  });

  // 注釈: R² の意味 + 出典
  s.addText("※ R² = 1 で完全に説明できる / 0 で無関係 (バーは 0〜1 スケール)", {
    x: 0.6, y: 5.05, w: 8.8, h: 0.25,
    fontSize: 10, fontFace: FONT_BODY,
    italic: true, color: MUTED, align: "center", valign: "middle", margin: 0,
  });
  s.addText("N = 4,276 〜 6,391 / 出典: EDINET", {
    x: 0.6, y: 5.3, w: 8.8, h: 0.25,
    fontSize: 9, fontFace: FONT_BODY,
    italic: true, color: MUTED, align: "center", valign: "middle", margin: 0,
  });

  s.addNotes(NOTES[9]);
  addFooter(s, 9, TOTAL);
}

// =========================================================
// Slide 10: そして、気づいた — 3 指標すべてに欠陥
// =========================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  s.addText("気づき", {
    x: 0.4, y: 0.35, w: 9, h: 0.4,
    fontSize: 13, fontFace: FONT_BODY,
    color: MUTED, charSpacing: 4, margin: 0,
  });
  s.addText("指標が何を意味しているか", {
    x: 0.4, y: 0.75, w: 9.4, h: 0.55,
    fontSize: 20, fontFace: FONT_HEAD, bold: true,
    color: FG, align: "left", valign: "middle", margin: 0,
  });

  // 3 カラム: 各指標の算出式 + 欠陥 + 具体例
  const metrics = [
    {
      name: "女性管理職比率",
      formula: "女性管理職 ÷ 全管理職",
      flaw: "女性社員の母数を見ていない",
      example: "女性社員が全社の 10% しかいなければ、\n女性管理職比率が低くて当たり前。",
    },
    {
      name: "男性育休取得率",
      formula: "取得した男性 ÷ 配偶者出産男性",
      flaw: "取得日数を見ていない",
      example: "1 日取得も、半年取得も、\n同じ「1 回取得」。同じ 100%。",
    },
    {
      name: "男女の賃金格差",
      formula: "女性平均賃金 ÷ 男性平均賃金",
      flaw: "複数要因が混在",
      example: "非正規率 男 22% / 女 53% など\n雇用形態の差がそのまま入る。",
    },
  ];

  const colW = 3.13, colGap = 0.1;
  const colTotalW = metrics.length * colW + (metrics.length - 1) * colGap;
  const colStartX = (10 - colTotalW) / 2;
  const colY = 1.55;
  const colH = 3.6;

  metrics.forEach((m, i) => {
    const x = colStartX + i * (colW + colGap);

    // カード枠
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: colY, w: colW, h: colH,
      fill: { color: BG }, line: { color: RULE, width: 1 },
    });

    // 指標名
    s.addText(m.name, {
      x, y: colY + 0.2, w: colW, h: 0.4,
      fontSize: 14, fontFace: FONT_HEAD, bold: true,
      color: FG, align: "center", valign: "middle", margin: 0,
    });

    // 区切り 1
    s.addShape(pres.shapes.LINE, {
      x: x + 0.4, y: colY + 0.7, w: colW - 0.8, h: 0,
      line: { color: RULE, width: 1 },
    });

    // 算出式 (1行)
    s.addText(m.formula, {
      x: x + 0.1, y: colY + 0.85, w: colW - 0.2, h: 0.5,
      fontSize: 11, fontFace: FONT_BODY,
      color: FG, align: "center", valign: "middle", margin: 0,
    });

    // 区切り 2
    s.addShape(pres.shapes.LINE, {
      x: x + 0.4, y: colY + 1.5, w: colW - 0.8, h: 0,
      line: { color: RULE, width: 1 },
    });

    // 欠陥（アクセント）
    s.addText(m.flaw, {
      x: x + 0.1, y: colY + 1.65, w: colW - 0.2, h: 0.7,
      fontSize: 15, fontFace: FONT_HEAD, bold: true,
      color: ACCENT, align: "center", valign: "middle", margin: 0,
    });

    // 例 (italic)
    s.addText(m.example, {
      x: x + 0.15, y: colY + 2.5, w: colW - 0.3, h: 1.0,
      fontSize: 10, fontFace: FONT_BODY,
      italic: true, color: MUTED, align: "center", valign: "top", margin: 0,
    });
  });

  s.addNotes(NOTES[10]);
  addFooter(s, 10, TOTAL);
}

// =========================================================
// Slide 11: 学び — 3 つの教訓
// =========================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  s.addText("まとめ", {
    x: 0.6, y: 0.4, w: 5, h: 0.45,
    fontSize: 13, fontFace: FONT_BODY,
    color: MUTED, charSpacing: 4, margin: 0,
  });

  s.addText("分析を通して学んだ 3 つのこと", {
    x: 0.6, y: 0.95, w: 9, h: 0.7,
    fontSize: 28, fontFace: FONT_HEAD, bold: true,
    color: FG, align: "left", valign: "middle", margin: 0,
  });

  const takeaways = [
    { t: "相対的に見る", sub: "絶対値だけ見ても、良いか悪いか分からない" },
    { t: "相関を見る", sub: "ただし、相関も「指標が正しい前提」の話" },
    { t: "指標の背景を読む", sub: "定義を理解しないと、分析全体が空転する" },
  ];

  takeaways.forEach((it, i) => {
    const y = 2.05 + i * 1.0;
    s.addText(String(i + 1), {
      x: 0.6, y, w: 1.0, h: 0.85,
      fontSize: 40, fontFace: FONT_HEAD, bold: true,
      color: ACCENT, align: "left", valign: "middle", margin: 0,
    });
    s.addText(it.t, {
      x: 1.7, y, w: 7.8, h: 0.45,
      fontSize: 22, fontFace: FONT_HEAD, bold: true,
      color: i === 2 ? ACCENT : FG, align: "left", valign: "middle", margin: 0,
    });
    s.addText(it.sub, {
      x: 1.7, y: y + 0.45, w: 7.8, h: 0.35,
      fontSize: 13, fontFace: FONT_BODY,
      color: MUTED, align: "left", valign: "middle", margin: 0,
    });
  });

  s.addNotes(NOTES[11]);
  addFooter(s, 11, TOTAL);
}

// =========================================================
// Slide 12: 失敗談 (笑える話、独立)
// =========================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  s.addText("失敗談", {
    x: 0.4, y: 0.35, w: 9, h: 0.4,
    fontSize: 13, fontFace: FONT_BODY,
    color: MUTED, charSpacing: 4, margin: 0,
  });
  s.addText("AI に本番 DB を全焼された", {
    x: 0.4, y: 0.75, w: 9.2, h: 0.6,
    fontSize: 24, fontFace: FONT_HEAD, bold: true,
    color: FG, align: "left", valign: "middle", margin: 0,
  });

  // === 左カラム: 消えたデータを大きく ===
  s.addText("消えたデータ", {
    x: 0.4, y: 1.7, w: 4.5, h: 0.4,
    fontSize: 14, fontFace: FONT_BODY,
    color: MUTED, charSpacing: 3, margin: 0,
  });
  s.addText([
    { text: "8,481", options: { fontSize: 96, fontFace: FONT_HEAD, bold: true, color: ACCENT } },
    { text: "  行", options: { fontSize: 28, fontFace: FONT_BODY, color: FG } },
  ], {
    x: 0.4, y: 2.2, w: 5.5, h: 2.0,
    align: "left", valign: "middle", margin: 0,
  });

  // === 右カラム: スクショ (下部トリミング版) ===
  const capRatio = 943 / 549; // トリミング後の比率
  const capH = 2.6;
  const capW = capH * capRatio; // 約 4.47
  s.addImage({
    path: "logos/claude_truncate_cropped.png",
    x: 5.1, y: 1.7, w: capW, h: capH,
  });
  s.addText("実際のセッション", {
    x: 5.1, y: 4.35, w: capW, h: 0.25,
    fontSize: 9, fontFace: FONT_BODY,
    italic: true, color: MUTED, align: "center", valign: "middle", margin: 0,
  });

  s.addNotes(NOTES[12]);
  addFooter(s, 12, TOTAL);
}

// =========================================================
// Slide 13: お知らせ — Streamlit Cloud / GitHub
// =========================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  // 2カラム: Streamlit / GitHub (実画面のスクショ入り)
  const cards = [
    {
      tag: "DEMO",
      title: "Streamlit Dashboard",
      logo: "logos/streamlit_dashboard.png",
      logoRatio: 2725 / 1275,
      url: "edinet-dashboard.streamlit.app",
    },
    {
      tag: "CODE",
      title: "GitHub",
      logo: "logos/github_profile.png",
      logoRatio: 1293 / 943,
      url: "github.com/hiroshi0918",
    },
  ];

  const cardW = 4.75, cardH = 4.6, cardGap = 0.2;
  const cardTotalW = cards.length * cardW + (cards.length - 1) * cardGap;
  const cardStartX = (10 - cardTotalW) / 2;
  const cardY = 0.5;

  cards.forEach((c, i) => {
    const x = cardStartX + i * (cardW + cardGap);
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: cardY, w: cardW, h: cardH,
      fill: { color: BG },
      line: { color: RULE, width: 1.5 },
    });

    // TAG (左上)
    s.addText(c.tag, {
      x: x + 0.25, y: cardY + 0.25, w: 2.5, h: 0.35,
      fontSize: 12, fontFace: FONT_HEAD, bold: true,
      color: ACCENT, charSpacing: 5, margin: 0,
    });

    // タイトル (TAG の下)
    s.addText(c.title, {
      x: x + 0.25, y: cardY + 0.6, w: cardW - 0.5, h: 0.5,
      fontSize: 22, fontFace: FONT_HEAD, bold: true,
      color: FG, align: "left", valign: "middle", margin: 0,
    });

    // スクショ (アスペクト維持、最大限大きく)
    const imgMaxH = 2.85;
    const imgMaxW = cardW - 0.4;
    let imgH = imgMaxH;
    let imgW = imgH * c.logoRatio;
    if (imgW > imgMaxW) { imgW = imgMaxW; imgH = imgW / c.logoRatio; }
    const imgX = x + (cardW - imgW) / 2;
    const imgY = cardY + 1.25 + (imgMaxH - imgH) / 2;
    s.addShape(pres.shapes.RECTANGLE, {
      x: imgX - 0.02, y: imgY - 0.02, w: imgW + 0.04, h: imgH + 0.04,
      fill: { color: BG }, line: { color: RULE, width: 0.5 },
    });
    s.addImage({ path: c.logo, x: imgX, y: imgY, w: imgW, h: imgH });

    // URL (カード下端)
    s.addText(c.url, {
      x: x + 0.2, y: cardY + cardH - 0.55, w: cardW - 0.4, h: 0.45,
      fontSize: 14, fontFace: FONT_CODE, bold: true,
      color: FG, align: "center", valign: "middle", margin: 0,
    });
  });

  s.addText("Thanks!", {
    x: 0.6, y: 5.25, w: 9, h: 0.3,
    fontSize: 12, fontFace: FONT_HEAD, bold: true,
    color: MUTED, align: "center", valign: "middle", margin: 0,
  });

  s.addNotes(NOTES[13]);
}

// === Write ===
pres.writeFile({ fileName: "LT_slides.pptx" }).then((fn) => {
  console.log("Generated:", fn);
});
