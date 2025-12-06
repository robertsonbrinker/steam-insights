import duckdb

# Create/connect to database
con = duckdb.connect('steam_insights.duckdb')

print("Importing CSVs to DuckDB...")

# Import each CSV file as a table
tables = {
    'games': 'resources/games.csv',
    'steamspy_insights': 'resources/steamspy_insights.csv',
    'tags': 'resources/tags.csv',
    'genres': 'resources/genres.csv',
    'categories': 'resources/categories.csv',
    'reviews': 'resources/reviews.csv',
    'descriptions': 'resources/descriptions.csv',
    'promotional': 'resources/promotional.csv'
}

for table_name, csv_path in tables.items():
    print(f"Importing {table_name}...")
    con.execute(f"""
        CREATE TABLE {table_name} AS
        SELECT * FROM read_csv_auto('{csv_path}')
    """)

    # Show row count
    count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    print(f"  ✓ {table_name}: {count:,} rows")

# Create indexes on app_id for faster joins
print("\nCreating indexes...")
for table in ['games', 'steamspy_insights', 'tags', 'genres', 'categories', 'reviews']:
    con.execute(f"CREATE INDEX idx_{table}_app_id ON {table}(app_id)")

print("\n✓ Database created successfully: steam_insights.duckdb")

# Show database stats
print("\nDatabase summary:")
con.execute("PRAGMA database_size").df()
con.close()
