import os
import zipfile
import requests
import io
import pandas as pd
import psycopg2
import time
import re
import unicodedata

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


def mark_csv_unavailable(cursor, doc_id):
    cursor.execute(
        "UPDATE financial_reports SET csv_available = FALSE, processed = TRUE WHERE doc_id = %s",
        (doc_id,),
    )

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


def parse_metric_tokens(compact_text):
    tokens = []
    i = 0
    text = compact_text.replace("－", "-").replace("―", "-")

    while i < len(text):
        if text[i] == "-":
            tokens.append(None)
            i += 1
            continue

        if text[i].isdigit():
            j = i
            while j < len(text) and text[j].isdigit():
                j += 1
            if j < len(text) and text[j] == "." and j + 1 < len(text) and text[j + 1].isdigit():
                tokens.append(float(text[i:j + 2]))
                i = j + 2
                continue
            break

        i += 1

    return tokens


def extract_human_capital_from_text(text):
    if not text or "管理職に占める女性労働者の割合" not in text:
        return {}

    normalized = unicodedata.normalize("NFKC", str(text))
    start = normalized.find("管理職に占める女性労働者の割合")
    section = normalized[start:start + 800]
    section = re.sub(r"[\(（]注[^)）]*[\)）]\s*[0-9０-９]?", "", section)
    section = re.sub(r"\s+", "", section)

    metric_labels = [
        "労働者の男女の賃金の差異(%)",
        "男女の賃金の差異(%)",
        "労働者の男女賃金差異(%)",
    ]
    anchor_index = max((section.rfind(label) for label in metric_labels), default=-1)
    target = section[anchor_index:] if anchor_index >= 0 else section

    cluster_match = re.search(r"[-―－0-9][-.―－0-9]+", target)
    if not cluster_match:
        return {}

    tokens = parse_metric_tokens(cluster_match.group(0))
    numeric_tokens = [token for token in tokens if token is not None]
    if not tokens:
        return {}

    metrics = {
        "female_manager_ratio": tokens[0] if len(tokens) >= 1 else None,
        "male_childcare_leave_ratio": tokens[1] if len(tokens) >= 2 else None,
        "gender_wage_gap": numeric_tokens[-3] if len(numeric_tokens) >= 3 else None,
    }

    return {key: value for key, value in metrics.items() if value is not None}

def process_documents():
    conn = psycopg2.connect(host="db", database="edinet_db", user="user", password="password")
    cursor = conn.cursor()
    ensure_schema(cursor)
    
    # Get up to 10 CSV-downloadable documents that haven't been processed yet
    cursor.execute("""
        SELECT doc_id, edinet_code
        FROM financial_reports
        WHERE COALESCE(csv_available, TRUE) IS TRUE
          AND COALESCE(processed, FALSE) IS FALSE
        ORDER BY doc_id
        LIMIT 10
    """)
    docs = cursor.fetchall()
    
    if not docs:
        print("No pending documents to process.")
        conn.close()
        return
        
    print(f"Found {len(docs)} documents to process.")
    
    for doc_id, edinet_code in docs:
        print(f"\nProcessing {doc_id} for {edinet_code}...")
        url = f"https://api.edinet-fsa.go.jp/api/v2/documents/{doc_id}"
        response = requests.get(url, params={"type": 5, "Subscription-Key": API_KEY})
        if response.status_code != 200:
            print(f"Failed to download {doc_id}: {response.status_code}")
            continue

        if not zipfile.is_zipfile(io.BytesIO(response.content)):
            try:
                payload = response.json()
            except ValueError:
                payload = None

            metadata = (payload or {}).get("metadata", {})
            if metadata.get("status") == "404":
                print(f"CSV download is not available for {doc_id}. Marking it as skipped.")
                mark_csv_unavailable(cursor, doc_id)
                conn.commit()
                continue

            print(
                f"Unexpected non-ZIP response for {doc_id}: "
                f"{response.headers.get('content-type', 'unknown')}"
            )
            if payload:
                print(payload)
            continue
            
        sales = None
        op_profit = None
        net_profit = None
        emp_count = None
        female_mgr = None
        childcare = None
        wage_gap = None
            
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
                            text_metrics = extract_human_capital_from_text(val)
                            if female_mgr is None:
                                female_mgr = text_metrics.get("female_manager_ratio")
                            if childcare is None:
                                childcare = text_metrics.get("male_childcare_leave_ratio")
                            if wage_gap is None:
                                wage_gap = text_metrics.get("gender_wage_gap")

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
                            elif childcare is None and ('男性労働者の育児休業取得率' in name or '男性の育児休業取得率' in name):
                                childcare = val_num
                            elif wage_gap is None and ('男女の賃金の差異' in name or '男女賃金差異' in name):
                                wage_gap = val_num
                                
        except Exception as e:
            print(f"Error parsing ZIP for {doc_id}: {e}")
            
        print(
            f"Extracted -> Sales: {sales}, OpProfit: {op_profit}, NetProfit: {net_profit}, "
            f"Emp: {emp_count}, FemaleMgr: {female_mgr}, Childcare: {childcare}, WageGap: {wage_gap}"
        )
        
        # Update financial_reports
        cursor.execute("""
            UPDATE financial_reports 
            SET sales = %s,
                operating_profit = %s,
                net_profit = %s,
                employee_count = %s,
                processed = TRUE
            WHERE doc_id = %s
        """, (sales, op_profit, net_profit, emp_count, doc_id))
        
        # Insert human capital
        if female_mgr is not None or childcare is not None or wage_gap is not None:
            cursor.execute("SELECT fiscal_year FROM financial_reports WHERE doc_id = %s", (doc_id,))
            fy = cursor.fetchone()[0]
            
            cursor.execute("""
                INSERT INTO human_capital_metrics 
                (
                    edinet_code,
                    fiscal_year,
                    female_manager_ratio,
                    male_childcare_leave_ratio,
                    gender_wage_gap,
                    source_name
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (edinet_code, fy, female_mgr, childcare, wage_gap, "EDINET_CSV"))
            
        conn.commit()
        time.sleep(1) # Avoid EDINET API rate limiting
        
    cursor.close()
    conn.close()
    print("Processing complete.")

if __name__ == "__main__":
    process_documents()
