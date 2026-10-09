"""Pipeline runner: builds the views, runs queries, prints results.

Usage:  python run_pipeline.py > pipeline_results.md
"""
import re
import sqlite3
import pandas as pd

conn = sqlite3.connect("data/claims_data.db")

# 1. Create the cohort views
conn.executescript(open("queries/00_create_views.sql").read())

# 2. Run queries in the remaining files and print the result tables
for path in ["queries/01_cohort_identification.sql",
             "queries/02_utilization_metrics.sql",
             "queries/03_data_quality_checks.sql"]:
    print(f"\n## {path}\n")
    buf = ""
    for line in open(path):
        buf += line
        # Uses Python's builtin sqlite3.complete_statement() method to test if the accumulated
        # text buf forms a complete SQL statement (ending with a semicolon or proper termination)
        if sqlite3.complete_statement(buf):
            # Searches the buffer using a regular expression for a SQL comment (--) followed by 
            # a query identifier like Q1. or Q2.
            label = re.search(r"--\s*(Q\d+\..*)", buf) 

            print(f"**{label.group(1) if label else 'Query'}**\n")
            # skip file header comments
            sql = buf[label.start():] if label else buf   
            print("```sql\n" + sql.strip() + "\n```\n")

            # Pass the SQL string buf and an active database connection conn into pandas.read_sql_query, 
            # executing the query and rendering the result set as a clean Markdown table
            print(pd.read_sql_query(buf, conn).to_markdown(index=False), "\n")
            
            # Reset buf to start accumulating the next SQL statement
            buf = ""