"""Interactive read-only SQL lab."""
import sqlite3
from pathlib import Path
from network_sql.source import database_path, dataset_caption

def main():
    path = database_path()
    print("Network SQL lab | " + dataset_caption())
    print("Type a SQL statement;")
    print("finish it with a semicolon. Type 'quit' to exit. See exercises.sql.")
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only = ON")
        statement = ""
        while True:
            try:
                line = input("sql> " if not statement else "...> ")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if line.strip().lower() == "quit":
                break
            statement += line + "\n"
            if not sqlite3.complete_statement(statement):
                continue
            try:
                cursor = db.execute(statement)
                if cursor.description:
                    print(" | ".join(column[0] for column in cursor.description))
                    rows = cursor.fetchmany(101)
                    for row in rows[:100]:
                        print(" | ".join(str(value) for value in row))
                    if len(rows) > 100:
                        print("Display limited to 100 rows. Use LIMIT in your query.")
            except sqlite3.Error as error:
                print(f"SQL error: {error}")
            statement = ""


if __name__ == "__main__":
    main()
