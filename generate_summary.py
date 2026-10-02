import pandas as pd
import glob
import sys

sys.stdout.reconfigure(encoding='utf-8')
file_path = glob.glob("*.xlsx")[0]
xls = pd.ExcelFile(file_path)
df = pd.read_excel(xls, sheet_name='Tasks')
df = df.astype(str)
sprint_col = next((c for c in df.columns if "sprint" in c.lower()), None)

tasks_in_completion = ["T-12", "T-13", "T-14", "T-15", "T-16", "T-17", "T-18", "T-20", "T-21", "T-22", "T-23", "T-24", "T-25", "T-26", "T-28", "T-30", "T-31", "T-32", "T-33", "T-34", "T-35"]

completed_tasks = []
for index, row in df.iterrows():
    if row['ID'] in tasks_in_completion:
        completed_tasks.append(row)

with open('ketqua/sprint2_completed_tasks_summary.md', 'w', encoding='utf-8') as f:
    f.write("# Tổng hợp các Task đã hoàn thành trong Sprint 2\n\n")
    f.write("Dưới đây là danh sách các task của Sprint 2 đã được triển khai (dựa trên kết quả trong thư mục `ketqua/`), cùng với giải thích chi tiết về việc **đã làm gì** và **để làm gì**.\n\n")
    
    for row in completed_tasks:
        f.write(f"### {row['ID']}: {row['Title']}\n")
        
        # Đã làm gì (Story/Implementation)
        f.write("**1. Đã làm gì:**\n")
        f.write(f"{row['Story']}\n\n")
        
        # Để làm gì (AC/Purpose)
        f.write("**2. Để làm gì (Mục đích & Nghiệm thu):**\n")
        f.write(f"{row['AC']}\n")
        f.write(f"*(Ràng buộc NFR: {row.get('NFR', '')})*\n\n")
        f.write("---\n\n")

print("Generated ketqua/sprint2_completed_tasks_summary.md")
