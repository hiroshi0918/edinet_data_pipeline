import requests
import json
import psycopg2
from datetime import datetime

# 取得したい日付を設定
target_date = "2024-03-29" 
# 取得したAPIキーを環境変数から取得します
import os
API_KEY = os.environ.get("EDINET_API_KEY", "あなたのAPIキーをここに入力")

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
                
                inserted_count = 0
                for doc in data['results']:
                    edinet_code = doc.get('edinetCode')
                    doc_id = doc.get('docID')
                    filer_name = doc.get('filerName')
                    submit_datetime = doc.get('submitDateTime')
                    doc_desc = str(doc.get('docDescription'))
                    
                    if edinet_code and doc_id:
                        # 企業マスタへの登録 (重複無視)
                        cursor.execute("""
                            INSERT INTO companies (edinet_code, company_name) 
                            VALUES (%s, %s) ON CONFLICT (edinet_code) DO NOTHING
                        """, (edinet_code, filer_name))
                        
                        # 財務データ（有価証券報告書のみ抽出）
                        if "有価証券報告書" in doc_desc:
                            date_str = submit_datetime.split(' ')[0] if submit_datetime else None
                            cursor.execute("""
                                INSERT INTO financial_reports (doc_id, edinet_code, fiscal_year, submitted_date)
                                VALUES (%s, %s, %s, %s) ON CONFLICT (doc_id) DO NOTHING
                            """, (doc_id, edinet_code, 2023, date_str))
                            inserted_count += 1
                
                conn.commit()
                cursor.close()
                conn.close()
                print(f"データベースへの有価証券報告書の記録が完了しました。（対象: {inserted_count}件）")
        else:
            print("期待したメタデータキーが見つかりませんでした。レスポンス内容:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"エラーが発生しました: {response.status_code}")

if __name__ == "__main__":
    fetch_document_list(target_date, API_KEY)
