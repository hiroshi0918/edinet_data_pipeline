# 動いていた、けど嘘だった
## — 94% のレコードが静かに壊れていた話

> **LT 用メモ** / EDINET 人的資本データパイプライン刷新 (v0.3)

---

## 0. 前提 (15秒)

- EDINET = 金融庁の有価証券報告書 DB。約4,000社/年
- 「女性管理職比率」「男性育休取得率」「男女賃金差異」を抽出するパイプラインを運用中
- データソース: XBRL → CSV (TSV) で 1書類 数千行

---

## 1. ある日、DB を覗いてみた (30秒)

```sql
SELECT COUNT(*) FROM human_capital_metrics
WHERE female_manager_ratio = male_childcare_leave_ratio
  AND female_manager_ratio IS NOT NULL;
```

**結果: 132 / 140 (94%)**

> 女性管理職比率 = 男性育休取得率？
> 物理的に意味不明な値が、9割を超えていた。

エラーは出ていない。テストも通っていた。

---

## 2. 真犯人 (60秒)

抽出ロジックは2段構成だった:

```
Layer A: 項目名と完全一致 → 数値抽出
Layer B: テキストから後方800文字を切り出して正規表現
```

`item_name_match` の件数: **0件**
全件が Layer B (テキスト抽出) 経由 — つまり Layer A は **完全に死んでいた**

そして Layer B のロジックがこうだった:

```python
# ラベル直後の最初の数値を取る
match = re.search(pattern, after_label)
```

ところが有報の人的資本テーブルは:

```
管理職に占める女性労働者の割合(%)
男性労働者の育児休業取得率(%)
労働者の男女の賃金の差異(%)
5.2  36.4  68.2
```

**全部のラベル直後の「最初の数値」が `5.2` になっていた。**

---

## 3. 本当の宝物に気付いていなかった (60秒)

EDINET の CSV には `要素ID` という列がある:

```
jpcrp_cor:RatioOfFemaleEmployeesInManagerialPositionsMetricsOfReportingCompany   = 0.024
jpcrp_cor:AllEmployees...RatioOfMaleEmployeesTakingChildcareLeaveMetricsOfReportingCompany = 0.585
jpcrp_cor:AllEmployeesDifferencesInWagesBetweenMaleAndFemaleEmployeesMetricsOfReportingCompany = 0.743
```

法令で定義された XBRL タクソノミー上の機械判読 ID。
**日本語項目名より圧倒的に信頼できる**。

旧コードは「日本語項目名」しか見ていなかった。
要素 ID は CSV にずっと載っていた。 **3年間、無視され続けていた。**

---

## 4. 直してみた結果 (30秒)

3層抽出戦略に再設計:

```
Layer 1: 要素ID完全一致 (jpcrp_cor:...)        ← 最優先・決定論的
Layer 2: 項目名部分一致                          ← 旧フォーマット救済
Layer 3: テキスト + LLM フォールバック            ← 最終手段
```

| 指標 | Before | After |
|---|---|---|
| F=M 同値率 | **94%** | **4.7%** |
| 賃金差異カバー率 | 64% | **94%** |
| 処理書類数 | 174 | **4,258** |
| 失敗 (`failed`) | 数十件 | **0件** |
| 多次元 (子会社 × 雇用形態) | カラム無し | **6次元保持** |

---

## 5. 教訓 (90秒)

### 教訓 1: 「動いている」≠「正しい」

例外もエラーも出ない。
**サイレントなバグは、ログに出るバグの100倍怖い。**

DB を SELECT して中身を眺める儀式を、定期的に。

### 教訓 2: カバー率は嘘をつく

旧パイプラインの **「カバー率 100%」は嘘** だった。
無理やり数値を引いていただけ。

修正後は 71% に「下がった」。
でもこれが**本当のカバー率**。

> **数字が下がることは、品質が上がることがある。**

### 教訓 3: データソースの構造に敬意を

日本語項目名でマッチさせるのは「人間用の表記」をパースしているということ。
要素 ID は「機械用の識別子」。

> **「人間に見やすい列」と「機械に確実な列」を見間違えない。**

### 教訓 4: 次元データは次元のまま蓄積する

旧スキーマは 1社1年度1行に潰していた。
新スキーマは `(scope, worker_type)` の多次元で最大6行。

> **集計は利用時にやればいい。蓄積時に潰すと取り返せない。**

---

## 6. メタ教訓 (15秒)

```
正しさ ≠ エラーが出ないこと
正しさ ≠ カバー率が高いこと
正しさ ≠ テストが通ること

正しさ = データを見て「ありえる値」になっていること
```

---

## おまけ: 副産物のハマりどころ

- **Docker `pip install .` 罠**: `-e` を付けないと src/ の編集が反映されない。`/usr/local/lib/python3.10/site-packages/...` というパスをトレースバックで見たら警戒
- **PostgreSQL view 罠**: `CREATE OR REPLACE VIEW` は既存カラムの順序変更を許さない。`DROP → CREATE` が必要
- **SIGINT 罠**: `time.sleep()` を try ブロックの外に置くと、Ctrl+C で `processing` 状態が残る

---

**まとめ**

1日30分、DB を眺める習慣を始めよう。
たまにそこには、3年間誰も気付かなかった 94% のバグがいる。

---
---

# 続編: 「直したつもり」がまた嘘だった話
## — 200% の謎と、本番 DB を AI に消された日 (2026-05-18)

> あれから3年。あの 94% バグは直した。
> もう DB は綺麗だ、と思っていた。

---

## 7. ある日、200% に気付いた (15秒)

ダッシュボードで男性育休取得率の分布を眺めていた。

```
0%, 12%, 23%, 45%, ..., 100%, ..., 200% ←？？？
```

**男性育休取得率 200%**。物理的に意味不明な値、Part 2。

```sql
SELECT COUNT(*) FROM analytics.company_year_metrics
WHERE male_childcare_leave_ratio = 200;
-- 結果: 15件
```

---

## 8. 真犯人 (第一発見) (45秒)

XBRL の同一 element_id を contextRef 違いで複数値持てる仕様を、extractor が無視していた。

```python
def _try_apply_element_id_match(...):
    if hm_builder.has_value(scope, worker_type, metric_name):
        return  # ★ 既に値があれば即 return
    hm_builder.set_value(...)
```

**「最初に出てきた 1 つを採用、残りは捨てる」**

例: 東海旅客鉄道の連結子会社 18 行
```
0.06, 0.25, 0.41, 0.56, 0.64, 0.71, 0.75, 0.75, 0.80,
0.81, 0.83, 1.00, 1.00, 1.00, 0.00, 0.00, 0.06, 2.00 ← この最後の 2.00 が
                                                      たまたまトップに来ると爆発
```

修正: **中央値集約**

```python
# Before: first-wins
# After: 観測値を全部リストに溜めて、to_records で statistics.median()
```

結果: **連結子会社側 7 件中 5 件が正常化** (200% → 75-150% に降下)。

これで全部終わったと思った。

---

## 9. ところが 10 件残った (60秒)

```
連結子会社側  残り 2 件
提出会社側    残り 8 件
```

提出会社側を生 XBRL で覗くと、なんと **raw_value = 2.000 が単独で書かれている**。

```
jpcrp_cor:AllEmployeesCalculatedBasedOnProvisionsOfArticle714Item1...
  RatioOfMaleEmployeesTakingChildcareLeaveMetricsOfReportingCompany
unit_id  = pure
raw_value = 2.000
```

**パイプラインは何も間違っていない。EDINET 原本にそう書かれている。**

「企業側の集計ミスでは？」と疑った。
でも 8 社の業種・規模はバラバラで、特定の業界の癖でもなさそう。

---

## 10. 時系列を見たら謎が深まった (45秒)

```
                2024年度  2025年度
─────────────────────────────────
イノテック       200% → 80%
パウダーテック   200% → 83%
ダイコー通産     200% → 50%
ゴールドクレスト   0% → 200%
ピー・ビー       50% → 200%
ギックス         80% → 200%
```

**200% は単年度のスパイク**。永続バグなら毎年出るはずなのに。

「分母 1 名のミクロケースで偶発？」「集計式が年によってブレる？」

仮説は立つが確証がない。**データだけ見ていても分からない。**

---

## 11. 法令を読みに行った (60秒)

最後の手段: テキストブロック（有報「従業員の状況」の本文）を直接読む。

イノテックの本文より:

> （注）２．育介法施行規則 第71条の４**第１号における育児休業等の取得割合**を
>       算出したものであります。
>       **なお、過年度に配偶者が出産した従業員が、当事業年度に
>       育児休業を取得することがあるため、取得率が100%を超えることがあります。**

**ちょっと待って。**

```
分子 = 当該年度に育休を取得した男性 (過年度配偶者出産者の繰越分も含む)
分母 = 当該年度に配偶者が出産した男性
```

**法令設計上、分子 > 分母 が許容されている。** 200% は完全に合法。

3年前の 94% バグは「データが嘘をついていた」話だった。
今回は **「データソースの仕様を知らずに勝手に嘘だと決めつけていた」** 話だった。

---

## 12. ボーナス発見: 5 社が XBRL タグを間違えていた (45秒)

ついでに本文と XBRL タグの整合性も調べた。

```
                    XBRL タグ         本文の引用条文
─────────────────────────────────────────────
ボルテージ          第71条の 4       第71条の 6
ゴールドクレスト    第71条の 4       第71条の 6
三共                第71条の 4       第71条の 6
コロナ              第71条の 4       第71条の 6
ギックス            第71条の 4 第1号  第71条の 4 第2号
```

**10 社中 5 社で本文と XBRL がズレている。**

EDINET の XBRL チェック機構は緩く、提出担当者が
- `Article714Item1` (大企業・第1号 = 育休のみ)
- `Article714Item2` (大企業・第2号 = 育休 + 育児目的休暇)
- `Article716Item1` (中堅企業・第1号)

の3つを取り違えても誰も止めない。
**ピンと来ない人がタグを選んでいる**。

---

## 13. 番外: AI に本番 DB を全焼させられた日 (90秒)

調査の途中で AI アシスタントに `pytest` を走らせてもらった。

```bash
docker compose run --rm app pytest tests/ -q
# 102 passed in 1.84s ✅
```

テスト全通過、清々しい。

…そのあと PG を覗いた。

```sql
SELECT COUNT(*) FROM financial_reports;
-- 2 ← !?
```

**8,481 件あったデータが 2 件になっていた。**

犯人: `tests/conftest.py`

```python
@pytest.fixture()
def db_connection(migrated_database: str):
    connection.autocommit = True
    cursor.execute("""
        TRUNCATE TABLE raw_edinet_facts, metric_evidence, human_capital_metrics,
        financial_reports, companies, llm_extraction_cache
        RESTART IDENTITY CASCADE
    """)
```

このフィクスチャは `DATABASE_URL` の指す DB に TRUNCATE する。
そして `docker compose run --rm app` で起動した app コンテナの DATABASE_URL は **本番** を指していた。

**autocommit=True なのでロールバックも効かない。一瞬で全焼。**

---

## 14. 復旧と再発防止 (45秒)

**救い**: DuckDB と Parquet は read-only で開いていたので無事 (8,481 件保持)。

**復旧**: `edinet backfill --from 2024-01-01 --to 2025-12-31` で EDINET から 40 分かけて再ダウンロード。

**再発防止**: `conftest.py` を二重ガード化。

```python
_TEST_DB_ENV_VAR = "TEST_DATABASE_URL"  # DATABASE_URL とは独立

def _is_safe_test_database(url: str) -> bool:
    """DB 名に "test" を含むときだけ TRUNCATE を許可"""
    return "test" in urlparse(url).path.lstrip("/").lower()

if not database_url:
    pytest.skip("TEST_DATABASE_URL is not set")
if not _is_safe_test_database(database_url):
    pytest.fail("Refusing to TRUNCATE non-test database")
```

これで以後の事故は構造的に防げる。

---

## 15. 続編の教訓

### 教訓 5: 「データの異常」より先に「データソースの仕様」を疑え

3年前は「データが嘘」だった。
今回は「データソースの仕様を知らない自分」が嘘だった。

> **異常値を見つけたら、まず法令と仕様書を読め。**
> クレンジングは仕様を理解してからの最終手段。

### 教訓 6: 「最初の1つを採用」は静かに腐る

XBRL の同一 element_id × 複数 contextRef、
CSV の同一カラム × 複数行、
JSON 配列の重複キー —— こういう「同じ意味の値が複数並ぶ」場面で
`if has_value: return` を入れると、入力順依存の不安定なバグになる。

> **配列が来る場所では、入力順依存ではなく集計順依存（中央値/平均/最大）で潰す。**

### 教訓 7: テストフィクスチャの環境変数共用は爆弾

`DATABASE_URL` を本番とテストで共用するのは「設定漏れによる事故」を待っているだけ。
**専用 env var + 名前ガードの二重チェック** を全プロジェクトの標準にすべき。

> **autocommit で TRUNCATE するフィクスチャは、URL に "test" 必須のガードで囲え。**

### 教訓 8: 「全社で同じ運用」は幻想

10 社の 200% の内訳:
- 4 社: 第71条の4 第1号で運用 (合法的 200%)
- 1 社: 第71条の4 第2号で運用 (合法的 200%)
- 4 社: 第71条の6 で運用、XBRL タグ間違い
- 1 社: 第71条の6 で運用、整合

**同じ「200%」でも 4 つの異なる物語がある。** カテゴリ別に分類しないと「クレンジング」も「異常検知」も意味を持たない。

---

## 16. 続編のメタ教訓

```
正しさ ≠ データが綺麗であること
正しさ ≠ 異常値が無いこと
正しさ ≠ パイプラインにバグが無いこと

正しさ = データソースの仕様を理解した上で
        「この値はこのルールでこう出ている」と
        説明できること
```

そして:

```
本番 DB を眺める習慣は、テスト DB を分離してから始めよう。
```

---

**続編のまとめ**

3年前は「動いていた、けど嘘だった」。
今回は **「異常に見えた、けど正常だった」**。

データ品質の旅は、まだ終わらない。

---
---

# 続々編: 「空のまま」と「ログが嘘」の話
## — 自分が 1 年前に置いた爆弾と、ドライバの嘘で 2 度ハマった (2026-05-18 続き)

> 200% の謎を解いた勢いで、次は「業界比較」をやろうとした。
> そこには **二段構えの罠** が待っていた。

---

## 17. 「`industry` カラム、あるのに空」事件 (60秒)

「業界 peer で比較したいから、`companies.industry` を SELECT してね」と
ダッシュボードのクエリを書いた。

結果:

```sql
SELECT industry, COUNT(*) FROM companies GROUP BY 1;
-- (NULL) | 4337  ← 全部 NULL
```

**全 4,337 社で NULL。**

慌てて `industry` の出処を grep してみる:

```bash
$ grep -rn "industry" src/edinet_pipeline/
src/edinet_pipeline/alembic/versions/0001_pipeline_rebuild.py:64:
    sa.Column("industry", sa.String(length=100), nullable=True),
```

**書き込んでるコードがどこにも無い。**

`upsert_company` の INSERT 文:

```python
INSERT INTO companies (edinet_code, company_name)
VALUES (%s, %s)
```

`industry` 列は**最初から書き込まれない設計**。
1年以上前、自分が `nullable=True` で予約だけして放置していた。

---

## 18. なぜ予約だけで終わったか (30秒)

EDINET API のレスポンスを思い出す:

```json
{
  "docID": "...",
  "edinetCode": "...",
  "filerName": "...",
  "docTypeCode": "...",
  // industry: なし
}
```

**業種フィールドが API レスポンスに無い。**

業種を取るには「EDINETコード集約一覧 (`Edinetcode.zip`)」を別途
金融庁からダウンロードする必要がある。
当時の自分は「いつかやる」で放置し、列だけ予約した。

**`nullable=True` カラムは「いつか埋める」と「永久に空のまま」の境界が緩い。**
- `NOT NULL` なら INSERT が失敗して即気づく
- `nullable=True` は黙って NULL が残る

これは LT_silent_data_bug の系譜で **「動いていたけど空だった」** バージョン。

---

## 19. 取り込みを書いた → 4337 件成功 → ログは「0 件」 (60秒)

`industry_master.py` を書いて、CLI に `update-industries` を足して、
集約一覧 ZIP から取り込みを実行:

```bash
$ docker compose run --rm app edinet update-industries --source-file Edinetcode.zip
industries_updated: fetched=11309, updated_rows=0
```

**`updated_rows=0`。**

「あれ、集約一覧には 11,309 社いるけど、companies は 4,337 社しかないから、
JOIN で全部マッチしなかったのか？」と一瞬思った。

確認のため SELECT:

```sql
SELECT COUNT(industry) FROM companies;
-- 4337  ← 全件埋まってる
```

**ログは嘘だった。**

犯人は psycopg2 の `execute_values` + `UPDATE FROM VALUES` パターン:

```python
execute_values(cursor, """
    UPDATE companies AS c
       SET industry = data.industry
      FROM (VALUES %s) AS data(edinet_code, industry)
     WHERE c.edinet_code = data.edinet_code
""", mapping)
return cursor.rowcount  # ← 0 を返してくる
```

`execute_values` は内部で複数 INSERT をバッチ化するが、
`UPDATE FROM VALUES` のパターンでは **最終的な `cursor.rowcount` が 0** になる。
PostgreSQL 自体は更新するが、ドライバが行数を拾えていない。

修正版：
```python
# UPDATE 後に SELECT で実数を取り直す
cursor.execute("SELECT COUNT(*) FROM companies WHERE industry IS NOT NULL")
updated_total = cursor.fetchone()[0]
```

**ログの数字を信じる前に、SELECT で実際の状態を見る。**

---

## 20. 続々編の教訓

### 教訓 9: `nullable=True` カラムは時限爆弾

将来用に予約した nullable カラムは、**埋める計画と期限をセット**でコミット
しないと、永久に空のまま静かに残る。

> **「いつかやる」は実装に書け、スキーマに書くな。**
>
> 列を予約するときは「いつ、どこから、どうやって埋めるか」のコメントを
> マイグレーションに書く。または `NOT NULL DEFAULT '不明'` で
> 「埋まってない」ことを能動的に表現する。

### 教訓 10: ドライバの行数は信用するな

ORM/ドライバが返す `rowcount` / `affected_rows` は、内部実装の都合で嘘を
ついてくることがある。書き込み確認は **書いた直後に SELECT** が確実。

> **書き込みのログは「やった気」、SELECT は「やったか」。**

### 教訓 11: API レスポンスに無いものは、別経路で取れ

「外部 API から自動で全部取れる」と思い込むと、足りないカラムが永久に
NULL になる。EDINET の場合、業種は API では取れず別配布の集約一覧が必要。

> **データソースの「取れるもの」と「取りたいもの」を最初に突き合わせる。**
> 取れないなら別経路を用意するか、その列はキッパリ作らない。

---

## 21. 続々編のメタ教訓

```
動いていた     → 嘘だった       (旧編)
異常に見えた   → 正常だった     (続編)
予約していた   → 空のままだった (続々編)
ログは「0」    → 実は「4337」   (続々編)
```

サイレントバグの源泉は **「期待値とのズレを検知する仕組みが無いこと」**。

- 旧編: F=M 同値率を誰も見ていなかった
- 続編: 200% という値の意味を法令まで遡って確認していなかった
- 続々編: nullable カラムの埋まり具合を誰もモニタリングしていなかった

すべてに共通するのは **「SELECT して目で見れば気づけた」** こと。

```
3 年経っても、結論は同じ:
1日30分、DB を眺める習慣を始めよう。
ただし、テスト DB と本番 DB は分離した上で。
そして、ログは信じず SELECT を信じよう。
```

---

**続々編のまとめ**

旧編: **動いていた、けど嘘だった**
続編: **異常に見えた、けど正常だった**
続々編: **予約していた、けど空だった / ログは「0」、けど実は「4337」**

データ品質の旅は、本当に終わらない。
