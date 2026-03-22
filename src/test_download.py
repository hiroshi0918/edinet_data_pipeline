import os
import zipfile
import requests
import io
import pandas as pd
import psycopg2
import traceback

API_KEY = "990a7fd392ef4d22a81e211f4e4a4656" 

def test_download():
    # Get one doc_id from DB
    conn = psycopg2.connect(host="db", database="edinet_db", user="user", password="password")
    cursor = conn.cursor()
    cursor.execute("SELECT doc_id FROM financial_reports LIMIT 1")
    row = cursor.fetchone()
    if not row:
        print("No documents found in DB.")
        return
    doc_id = row[0]
    conn.close()
    
    print(f"Testing download for doc_id: {doc_id}")
    url = f"https://api.edinet-fsa.go.jp/api/v2/documents/{doc_id}"
    params = {"type": 5, "Subscription-Key": API_KEY}
    
    response = requests.get(url, params=params)
    if response.status_code == 200:
        print("Download successful. Extracting ZIP...")
        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                csv_files = [f for f in z.namelist() if f.endswith('.csv')]
                print(f"Found CSV files: {csv_files}")
                for csv_file in csv_files:
                    if 'jpcrp' in csv_file.lower() or 'xbrl_to_csv' in csv_file.lower():
                        print(f"\n--- Analyzing {csv_file} ---")
                        with z.open(csv_file) as f:
                            # Read briefly
                            df = pd.read_csv(f, encoding='utf-16le', sep='\t')
                            print(f"Columns: {df.columns.tolist()}")
                            
                            keywords = ['売上', '利益', '従業員', '女性', '育児', '賃金']
                            for col in df.columns:
                                if '要素' in col or '項目' in col or '名称' in col:
                                    for kw in keywords:
                                        matches = df[df[col].astype(str).str.contains(kw, na=False)]
                                        if not matches.empty:
                                            print(f"\nMatches for '{kw}' in {col}:")
                                            val_cols = [c for c in df.columns if '値' in c]
                                            print(matches[[col] + val_cols].head(30))
        except Exception as e:
            print("Error parsing zip/csv:")
            traceback.print_exc()
    else:
        print(f"Error {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    test_download()
