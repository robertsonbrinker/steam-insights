import duckdb

con = duckdb.connect('steam_insights.duckdb', read_only=True)

print("=" * 100)
print("ATTRIBUTE COUNT STATISTICS FOR INDIE DEV==PUBLISHER GAMES")
print("=" * 100)

query = """
WITH indie_dev_pub_games AS (
    SELECT DISTINCT g.app_id
    FROM games g
    JOIN steamspy_insights s ON g.app_id = s.app_id
    JOIN tags t ON g.app_id = t.app_id
    WHERE s.developer = s.publisher
      AND t.tag = 'Indie'
      AND g.type = 'game'
),
-- Count tags per game
tag_counts AS (
    SELECT
        idp.app_id,
        COUNT(DISTINCT t.tag) AS tag_count
    FROM indie_dev_pub_games idp
    LEFT JOIN tags t ON idp.app_id = t.app_id
    GROUP BY idp.app_id
),
-- Count genres per game
genre_counts AS (
    SELECT
        idp.app_id,
        COUNT(DISTINCT g.genre) AS genre_count
    FROM indie_dev_pub_games idp
    LEFT JOIN genres g ON idp.app_id = g.app_id
    GROUP BY idp.app_id
),
-- Count categories per game
category_counts AS (
    SELECT
        idp.app_id,
        COUNT(DISTINCT c.category) AS category_count
    FROM indie_dev_pub_games idp
    LEFT JOIN categories c ON idp.app_id = c.app_id
    GROUP BY idp.app_id
),
-- Get price (just 1 per game, but consistent format)
price_info AS (
    SELECT
        TRY_CAST(g.app_id AS INTEGER) AS app_id,
        CASE
            WHEN g.is_free = '1' THEN 'Free'
            WHEN g.price_overview IS NOT NULL
                AND LENGTH(g.price_overview) > 5
                AND SUBSTRING(g.price_overview, 1, 1) = '{'
            THEN '$' || CAST(ROUND(TRY_CAST(json_extract_string(g.price_overview, '$.final') AS INTEGER) / 100.0, 2) AS VARCHAR)
            ELSE 'Unknown'
        END AS price
    FROM games g
    WHERE g.app_id IN (SELECT CAST(app_id AS VARCHAR) FROM indie_dev_pub_games)
      AND g.type = 'game'
),
-- Combine all counts
all_counts AS (
    SELECT
        tc.app_id,
        tc.tag_count,
        gc.genre_count,
        cc.category_count,
        CASE WHEN pi.price IS NOT NULL THEN 1 ELSE 0 END AS has_price
    FROM tag_counts tc
    LEFT JOIN genre_counts gc ON tc.app_id = gc.app_id
    LEFT JOIN category_counts cc ON tc.app_id = cc.app_id
    LEFT JOIN price_info pi ON tc.app_id = pi.app_id
)
SELECT
    COUNT(*) AS total_games,

    -- Tags
    ROUND(AVG(tag_count), 2) AS avg_tags_per_game,
    MEDIAN(tag_count) AS median_tags_per_game,
    MIN(tag_count) AS min_tags_per_game,
    MAX(tag_count) AS max_tags_per_game,

    -- Genres
    ROUND(AVG(genre_count), 2) AS avg_genres_per_game,
    MEDIAN(genre_count) AS median_genres_per_game,
    MIN(genre_count) AS min_genres_per_game,
    MAX(genre_count) AS max_genres_per_game,

    -- Categories
    ROUND(AVG(category_count), 2) AS avg_categories_per_game,
    MEDIAN(category_count) AS median_categories_per_game,
    MIN(category_count) AS min_categories_per_game,
    MAX(category_count) AS max_categories_per_game
FROM all_counts;
"""

result = con.execute(query).fetchone()

print(f"\nTotal games analyzed: {result[0]:,}")
print("\n" + "-" * 100)

print("\nTAGS per game:")
print(f"  Average:  {result[1]}")
print(f"  Median:   {int(result[2])}")
print(f"  Min:      {result[3]}")
print(f"  Max:      {result[4]}")

print("\nGENRES per game:")
print(f"  Average:  {result[5]}")
print(f"  Median:   {int(result[6])}")
print(f"  Min:      {result[7]}")
print(f"  Max:      {result[8]}")

print("\nCATEGORIES per game:")
print(f"  Average:  {result[9]}")
print(f"  Median:   {int(result[10])}")
print(f"  Min:      {result[11]}")
print(f"  Max:      {result[12]}")

# Get distribution details
distribution_query = """
WITH indie_dev_pub_games AS (
    SELECT DISTINCT g.app_id
    FROM games g
    JOIN steamspy_insights s ON g.app_id = s.app_id
    JOIN tags t ON g.app_id = t.app_id
    WHERE s.developer = s.publisher
      AND t.tag = 'Indie'
      AND g.type = 'game'
),
tag_counts AS (
    SELECT
        idp.app_id,
        COUNT(DISTINCT t.tag) AS tag_count
    FROM indie_dev_pub_games idp
    LEFT JOIN tags t ON idp.app_id = t.app_id
    GROUP BY idp.app_id
),
genre_counts AS (
    SELECT
        idp.app_id,
        COUNT(DISTINCT g.genre) AS genre_count
    FROM indie_dev_pub_games idp
    LEFT JOIN genres g ON idp.app_id = g.app_id
    GROUP BY idp.app_id
),
category_counts AS (
    SELECT
        idp.app_id,
        COUNT(DISTINCT c.category) AS category_count
    FROM indie_dev_pub_games idp
    LEFT JOIN categories c ON idp.app_id = c.app_id
    GROUP BY idp.app_id
)
SELECT
    'Tags' AS attribute_type,
    tag_count AS count,
    COUNT(*) AS num_games
FROM tag_counts
GROUP BY tag_count
UNION ALL
SELECT
    'Genres' AS attribute_type,
    genre_count AS count,
    COUNT(*) AS num_games
FROM genre_counts
GROUP BY genre_count
UNION ALL
SELECT
    'Categories' AS attribute_type,
    category_count AS count,
    COUNT(*) AS num_games
FROM category_counts
GROUP BY category_count
ORDER BY attribute_type, count;
"""

print("\n" + "=" * 100)
print("DISTRIBUTION BREAKDOWN")
print("=" * 100)

dist_df = con.execute(distribution_query).df()

for attr_type in ['Tags', 'Genres', 'Categories']:
    type_data = dist_df[dist_df['attribute_type'] == attr_type]
    print(f"\n{attr_type} distribution:")
    print(f"  Count | Number of Games | Percentage")
    print(f"  ------|-----------------|------------")
    total = type_data['num_games'].sum()
    for _, row in type_data.head(15).iterrows():
        pct = row['num_games'] / total * 100
        print(f"  {int(row['count']):5} | {row['num_games']:15,} | {pct:6.1f}%")
    if len(type_data) > 15:
        remaining = len(type_data) - 15
        print(f"  ... and {remaining} more values")

print("\n" + "=" * 100)

con.close()
