import duckdb

# Create/connect to database
con = duckdb.connect('steam_insights.duckdb')

print("Re-importing reviews table with correct types...")

# Drop and recreate reviews table with explicit types
con.execute("DROP TABLE IF EXISTS reviews")
con.execute("""
    CREATE TABLE reviews AS
    SELECT
        TRY_CAST(app_id AS INTEGER) AS app_id,
        TRY_CAST(review_score AS INTEGER) AS review_score,
        review_score_description,
        TRY_CAST(positive AS INTEGER) AS positive,
        TRY_CAST(negative AS INTEGER) AS negative,
        TRY_CAST(total AS INTEGER) AS total,
        TRY_CAST(metacritic_score AS INTEGER) AS metacritic_score,
        TRY_CAST(reviews AS INTEGER) AS reviews,
        TRY_CAST(recommendations AS INTEGER) AS recommendations,
        TRY_CAST(steamspy_user_score AS FLOAT) AS steamspy_user_score,
        steamspy_score_rank,
        TRY_CAST(steamspy_positive AS INTEGER) AS steamspy_positive,
        TRY_CAST(steamspy_negative AS INTEGER) AS steamspy_negative
    FROM read_csv_auto('resources/reviews.csv')
""")

# Recreate index
con.execute("CREATE INDEX idx_reviews_app_id ON reviews(app_id)")

count = con.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
print(f"✓ Reviews table updated: {count:,} rows with correct types")

con.close()
