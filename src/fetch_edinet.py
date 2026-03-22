import requests
import json
import psycopg2
import os

# 取得したい日付を設定
target_date = "2024-03-29" 
# 取得したAPIキーを環境変数から取得します
API_KEY = os.environ.get("EDINET_API_KEY", "あなたのAPIキーをここに入力")


def ensure_schema(cursor):
    cursor.execute("""
        ALTER TABLE financial_reports
        ADD COLUMN IF NOT EXISTS csv_available BOOLEAN NOT NULL DEFAULT TRUE
    """)
    cursor.execute("""
        ALTER TABLE financial_reports
        ADD COLUMN IF NOT EXISTS processed BOOLEAN NOT NULL DEFAULT FALSE
    """)


def is_target_report(doc):
    doc_desc = str(doc.get("docDescription", ""))
    return (
        doc_desc.startswith("有価証券報告書－")
        and str(doc.get("ordinanceCode", "")) == "010"
        and str(doc.get("formCode", "")) == "030000"
    )


def remove_non_target_reports(cursor, date, target_doc_ids):
    if not target_doc_ids:
        return 0

    cursor.execute("""
        DELETE FROM financial_reports
        WHERE submitted_date = %s
          AND NOT (doc_id = ANY(%s))
    """, (date, target_doc_ids))
    return cursor.rowcount

def fetch_document_list(date, api_key):
    url = "https://api.edinet-fsa.go.jp/api/v2/documents.json"
    params = {
        "date": date,
        "type": 2,
        "Subscription-Key": api_key
    }
    
    print(f"{date} の書類一覧を取得中...")
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if 'metadata' in data:
            count = data['metadata']['resultset']['count']
            print(f"取得成功！ 合計 {count} 件の書類があります。")
            
            if count > 0:
                conn = psycopg2.connect(
                    host="db",
                    database="edinet_db",
                    user="user",
                    password="password"
                )
                cursor = conn.cursor()
                ensure_schema(cursor)
                
                inserted_count = 0
                csv_enabled_count = 0
                target_doc_ids = []
                for doc in data['results']:
                    edinet_code = doc.get('edinetCode')
                    doc_id = doc.get('docID')
                    filer_name = doc.get('filerName')
                    submit_datetime = doc.get('submitDateTime')
                    csv_available = str(doc.get('csvFlag', '0')) == '1'
                    
                    if not (edinet_code and doc_id and is_target_report(doc)):
                        continue

                    target_doc_ids.append(doc_id)

                    # 企業マスタへの登録 (重複無視)
                    cursor.execute("""
                        INSERT INTO companies (edinet_code, company_name) 
                        VALUES (%s, %s) ON CONFLICT (edinet_code) DO NOTHING
                    """, (edinet_code, filer_name))

                    # 標準の企業有価証券報告書のみ登録
                    date_str = submit_datetime.split(' ')[0] if submit_datetime else None
                    cursor.execute("""
                        INSERT INTO financial_reports (
                            doc_id, edinet_code, fiscal_year, csv_available, submitted_date
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (doc_id) DO UPDATE SET
                            edinet_code = EXCLUDED.edinet_code,
                            fiscal_year = EXCLUDED.fiscal_year,
                            csv_available = EXCLUDED.csv_available,
                            submitted_date = EXCLUDED.submitted_date
                    """, (doc_id, edinet_code, 2023, csv_available, date_str))
                    inserted_count += 1
                    if csv_available:
                        csv_enabled_count += 1

                removed_count = remove_non_target_reports(cursor, date, target_doc_ids)
                
                conn.commit()
                cursor.close()
                conn.close()
                print(
                    "データベースへの標準有価証券報告書の記録が完了しました。"
                    f"（対象: {inserted_count}件 / CSV取得可: {csv_enabled_count}件"
                    f" / 除外: {removed_count}件）"
                )
        else:
            print("期待したメタデータキーが見つかりませんでした。レスポンス内容:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"エラーが発生しました: {response.status_code}")

if __name__ == "__main__":
    fetch_document_list(target_date, API_KEY)
