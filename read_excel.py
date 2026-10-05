import pandas as pd
import glob
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')
file_path = glob.glob("*.xlsx")[0]
xls = pd.ExcelFile(file_path)
df = pd.read_excel(xls, sheet_name='Tasks')
df = df.astype(str)
sprint_col = next((c for c in df.columns if "sprint" in c.lower()), None)

results = []
for index, row in df.iterrows():
    sprint_val = str(row[sprint_col]).lower() if sprint_col else ""
    if "2" in sprint_val:
        results.append(row.to_dict())

print(json.dumps(results, ensure_ascii=False, indent=2))
