import duckdb

# Create/connect to database
con = duckdb.connect('steam_insights.duckdb')

print("Re-importing reviews table with correct types...")

# Drop and recreate reviews table with explicit types
con.execute("DROP TABLE IF EXISTS reviews")

# First load as all VARCHAR
con.execute("""
    CREATE TEMP TABLE temp_reviews AS
    SELECT * FROM read_csv_auto('resources/reviews.csv', all_varchar=true)
""")

# Replace \N with NULL and cast to correct types
con.execute("""
    CREATE TABLE reviews AS
    SELECT
        TRY_CAST(CASE WHEN app_id = '\\N' THEN NULL ELSE app_id END AS INTEGER) AS app_id,
        TRY_CAST(CASE WHEN review_score = '\\N' THEN NULL ELSE review_score END AS INTEGER) AS review_score,
        CASE WHEN review_score_description = '\\N' THEN NULL ELSE review_score_description END AS review_score_description,
        TRY_CAST(CASE WHEN positive = '\\N' THEN NULL ELSE positive END AS INTEGER) AS positive,
        TRY_CAST(CASE WHEN negative = '\\N' THEN NULL ELSE negative END AS INTEGER) AS negative,
        TRY_CAST(CASE WHEN total = '\\N' THEN NULL ELSE total END AS INTEGER) AS total,
        TRY_CAST(CASE WHEN metacritic_score = '\\N' THEN NULL ELSE metacritic_score END AS INTEGER) AS metacritic_score,
        TRY_CAST(CASE WHEN reviews = '\\N' THEN NULL ELSE reviews END AS INTEGER) AS reviews,
        TRY_CAST(CASE WHEN recommendations = '\\N' THEN NULL ELSE recommendations END AS INTEGER) AS recommendations,
        TRY_CAST(CASE WHEN steamspy_user_score = '\\N' THEN NULL ELSE steamspy_user_score END AS FLOAT) AS steamspy_user_score,
        CASE WHEN steamspy_score_rank = '\\N' THEN NULL ELSE steamspy_score_rank END AS steamspy_score_rank,
        TRY_CAST(CASE WHEN steamspy_positive = '\\N' THEN NULL ELSE steamspy_positive END AS INTEGER) AS steamspy_positive,
        TRY_CAST(CASE WHEN steamspy_negative = '\\N' THEN NULL ELSE steamspy_negative END AS INTEGER) AS steamspy_negative
    FROM temp_reviews
""")

# Drop temp table
con.execute("DROP TABLE temp_reviews")

# Recreate index
con.execute("CREATE INDEX idx_reviews_app_id ON reviews(app_id)")

count = con.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
print(f"✓ Reviews table updated: {count:,} rows with correct types")

con.close()
