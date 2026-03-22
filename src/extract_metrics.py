import os
import zipfile
import requests
import io
import pandas as pd
import psycopg2
import time
import re
import os

API_KEY = os.environ.get("EDINET_API_KEY", "あなたのAPIキーをここに入力")

def extract_numeric(val):
    try:
        if pd.isna(val):
            return None
        # remove commas
        s = str(val).replace(',', '')
        # extract numeric parts
        m = re.search(r'[-+]?\d*\.\d+|\d+', s)
        if m:
            return float(m.group())
        return None
    except:
        return None

def process_documents():
    conn = psycopg2.connect(host="db", database="edinet_db", user="user", password="password")
    cursor = conn.cursor()
    
    # Get up to 10 documents that haven't been processed yet
    cursor.execute("SELECT doc_id, edinet_code FROM financial_reports WHERE sales IS NULL LIMIT 10")
    docs = cursor.fetchall()
    
    if not docs:
        print("No pending documents to process.")
        conn.close()
        return
        
    print(f"Found {len(docs)} documents to process.")
    
    for doc_id, edinet_code in docs:
        print(f"\nProcessing {doc_id} for {edinet_code}...")
        url = f"https://api.edinet-fsa.go.jp/api/v2/documents/{doc_id}?type=5&Subscription-Key={API_KEY}"
        
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to download {doc_id}: {response.status_code}")
            continue
            
        sales = None
        op_profit = None
        net_profit = None
        emp_count = None
        female_mgr = None
        childcare = None
            
        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                # Find the main standard corporate reporting CSV (usually jpcrp in XBRL_TO_CSV folder)
                csv_files = [f for f in z.namelist() if f.endswith('.csv') and ('jpcrp' in f.lower() or 'jpaud' in f.lower())]
                for csv_file in csv_files:
                    with z.open(csv_file) as f:
                        df = pd.read_csv(f, encoding='utf-16le', sep='\t')
                        
                        if '項目名' not in df.columns or '値' not in df.columns:
                            continue
                            
                        for index, row in df.iterrows():
                            name = str(row['項目名'])
                            val = row['値']
                            period = str(row.get('相対年度', ''))
                            
                            # Filter to current year or None period (for some non-temporal HR stats)
                            if period and '当期' not in period and '提出者' not in period:
                                continue
                                
                            val_num = extract_numeric(val)
                            if val_num is None:
                                continue
                                
                            if sales is None and any(k in name for k in ['売上高', '営業収益', '売上収益', '完成工事高']):
                                sales = val_num
                            elif op_profit is None and ('営業利益' in name or '営業損失' in name):
                                op_profit = val_num
                            elif net_profit is None and any(k in name for k in ['当期純利益', '親会社株主に帰属する']):
                                net_profit = val_num
                            elif emp_count is None and name == '従業員数':
                                emp_count = val_num
                            elif female_mgr is None and '管理職に占める女性労働者の割合' in name:
                                female_mgr = val_num
                            elif childcare is None and '男性労働者の育児休業取得率' in name:
                                childcare = val_num
                                
        except Exception as e:
            print(f"Error parsing ZIP for {doc_id}: {e}")
            
        print(f"Extracted -> Sales: {sales}, OpProfit: {op_profit}, NetProfit: {net_profit}, Emp: {emp_count}, FemaleMgr: {female_mgr}, Childcare: {childcare}")
        
        # Update financial_reports
        cursor.execute("""
            UPDATE financial_reports 
            SET sales = %s, operating_profit = %s, net_profit = %s, employee_count = %s
            WHERE doc_id = %s
        """, (sales, op_profit, net_profit, emp_count, doc_id))
        
        # Insert human capital
        if female_mgr is not None or childcare is not None:
            cursor.execute("SELECT fiscal_year FROM financial_reports WHERE doc_id = %s", (doc_id,))
            fy = cursor.fetchone()[0]
            
            cursor.execute("""
                INSERT INTO human_capital_metrics 
                (edinet_code, fiscal_year, female_manager_ratio, male_childcare_leave_ratio, source_name)
                VALUES (%s, %s, %s, %s, %s)
            """, (edinet_code, fy, female_mgr, childcare, "EDINET_CSV"))
            
        conn.commit()
        time.sleep(1) # Avoid EDINET API rate limiting
        
    cursor.close()
    conn.close()
    print("Processing complete.")

if __name__ == "__main__":
    process_documents()
