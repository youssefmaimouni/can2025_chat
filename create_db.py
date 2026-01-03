import sqlite3
import pandas as pd

# Path to your dataset (CSV)
CSV_PATH = "Caf_finals_and_qualifier.csv"      
DB_PATH = "matches.db"

# Load dataset
df = pd.read_csv(CSV_PATH)

# Connect to SQLite
conn = sqlite3.connect(DB_PATH)

# Create table
df.to_sql(
    "matches",
    conn,
    if_exists="replace",
    index=False
)

conn.close()

print("✅ Database created successfully")
print("📊 Rows inserted:", len(df))
