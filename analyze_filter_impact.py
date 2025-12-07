import duckdb
import pandas as pd

con = duckdb.connect('steam_insights.duckdb', read_only=True)

# ============================================================================
# CONFIGURATION: Change these thresholds to see their impact
# ============================================================================

MIN_GAME_COUNT = 20
MIN_TOTAL_REVIEWS = 2700

# 99 for games
# MIN_GAME_COUNT = 20
# MIN_TOTAL_REVIEWS = 0

# 99 for games
# MIN_GAME_COUNT = 0
# MIN_TOTAL_REVIEWS = 2700

# 80/20 games
# MIN_GAME_COUNT = 136
# MIN_TOTAL_REVIEWS = 0

# 80/20 games
# MIN_GAME_COUNT = 0
# MIN_TOTAL_REVIEWS = 62264

# for 50/50 games
# MIN_GAME_COUNT = 443
# MIN_TOTAL_REVIEWS = 0

# for 50/50 games
# MIN_GAME_COUNT = 0
# MIN_TOTAL_REVIEWS = 279358

# for 50/50 of attributes
# MIN_GAME_COUNT = 6
# MIN_TOTAL_REVIEWS = 0

# for 50/50 for attributes
# MIN_GAME_COUNT = 0
# MIN_TOTAL_REVIEWS = 17500 

print("=" * 100)
print("FILTER IMPACT ANALYSIS")
print("=" * 100)
print(f"\nThresholds being tested:")
print(f"  - Minimum games per attribute: {MIN_GAME_COUNT:,}")
print(f"  - Minimum total reviews per attribute: {MIN_TOTAL_REVIEWS:,}")
print("\n" + "=" * 100)

# Query to get stats for all attribute types
query = f"""
WITH indie_dev_pub_games AS (
    SELECT DISTINCT g.app_id
    FROM games g
    JOIN steamspy_insights s ON g.app_id = s.app_id
    JOIN tags t ON g.app_id = t.app_id
    WHERE s.developer = s.publisher
      AND t.tag = 'Indie'
      AND g.type = 'game'
),
game_wilson_scores AS (
    SELECT
        r.app_id,
        r.total
    FROM indie_dev_pub_games idp
    JOIN reviews r ON idp.app_id = r.app_id
    WHERE r.total > 0
),
-- TAGS
tag_stats AS (
    SELECT
        'tag' AS type,
        t.tag AS attribute,
        COUNT(DISTINCT gws.app_id) AS game_count,
        SUM(gws.total) AS total_reviews
    FROM tags t
    JOIN game_wilson_scores gws ON t.app_id = gws.app_id
    GROUP BY t.tag
),
-- GENRES
genre_stats AS (
    SELECT
        'genre' AS type,
        g.genre AS attribute,
        COUNT(DISTINCT gws.app_id) AS game_count,
        SUM(gws.total) AS total_reviews
    FROM genres g
    JOIN game_wilson_scores gws ON g.app_id = gws.app_id
    GROUP BY g.genre
),
-- CATEGORIES
category_stats AS (
    SELECT
        'category' AS type,
        c.category AS attribute,
        COUNT(DISTINCT gws.app_id) AS game_count,
        SUM(gws.total) AS total_reviews
    FROM categories c
    JOIN game_wilson_scores gws ON c.app_id = gws.app_id
    GROUP BY c.category
),
-- PRICE POINTS
price_point_stats AS (
    SELECT
        'price_point' AS type,
        '$' || CAST(ROUND(TRY_CAST(json_extract_string(g.price_overview, '$.final') AS INTEGER) / 100.0, 2) AS VARCHAR) AS attribute,
        COUNT(DISTINCT gws.app_id) AS game_count,
        SUM(gws.total) AS total_reviews
    FROM games g
    JOIN game_wilson_scores gws ON TRY_CAST(g.app_id AS INTEGER) = gws.app_id
    WHERE g.app_id IN (SELECT CAST(app_id AS VARCHAR) FROM indie_dev_pub_games)
      AND g.type = 'game'
      AND g.is_free = '0'
      AND g.price_overview IS NOT NULL
      AND LENGTH(g.price_overview) > 5
      AND SUBSTRING(g.price_overview, 1, 1) = '{{'
    GROUP BY ROUND(TRY_CAST(json_extract_string(g.price_overview, '$.final') AS INTEGER) / 100.0, 2)
),
-- COMBINE ALL
all_stats AS (
    SELECT * FROM tag_stats
    UNION ALL
    SELECT * FROM genre_stats
    UNION ALL
    SELECT * FROM category_stats
    UNION ALL
    SELECT * FROM price_point_stats
)
SELECT
    type,
    attribute,
    game_count,
    total_reviews,
    CASE
        WHEN game_count >= {MIN_GAME_COUNT} AND total_reviews >= {MIN_TOTAL_REVIEWS} THEN 'PASS'
        ELSE 'FAIL'
    END AS filter_result
FROM all_stats
ORDER BY type, game_count DESC;
"""

# Execute query
df = con.execute(query).df()

# Calculate statistics by type
print("\nRESULTS BY ATTRIBUTE TYPE:")
print("-" * 100)

for attr_type in ['tag', 'genre', 'category', 'price_point']:
    type_df = df[df['type'] == attr_type]

    total_count = len(type_df)
    pass_count = len(type_df[type_df['filter_result'] == 'PASS'])
    fail_count = len(type_df[type_df['filter_result'] == 'FAIL'])

    pass_pct = (pass_count / total_count * 100) if total_count > 0 else 0
    fail_pct = (fail_count / total_count * 100) if total_count > 0 else 0

    print(f"\n{attr_type.upper()}:")
    print(f"  Total attributes: {total_count:,}")
    print(f"  ✓ PASS: {pass_count:,} ({pass_pct:.1f}%)")
    print(f"  ✗ FAIL: {fail_count:,} ({fail_pct:.1f}%)")

    # Show some examples of failed attributes
    failed = type_df[type_df['filter_result'] == 'FAIL'].head(5)
    if len(failed) > 0:
        print(f"\n  Examples of FAILED {attr_type}s:")
        for _, row in failed.iterrows():
            print(f"    - {row['attribute']}: {row['game_count']} games, {row['total_reviews']:,.0f} reviews")

# Overall summary
print("\n" + "=" * 100)
print("OVERALL SUMMARY:")
print("-" * 100)
total_attrs = len(df)
total_pass = len(df[df['filter_result'] == 'PASS'])
total_fail = len(df[df['filter_result'] == 'FAIL'])

print(f"\nTotal attributes across all types: {total_attrs:,}")
print(f"✓ Attributes that PASS filters: {total_pass:,} ({total_pass/total_attrs*100:.1f}%)")
print(f"✗ Attributes that FAIL filters: {total_fail:,} ({total_fail/total_attrs*100:.1f}%)")

# Save detailed results to CSV
output_file = f'filter_impact_min{MIN_GAME_COUNT}games_min{MIN_TOTAL_REVIEWS}reviews.csv'
df.to_csv(output_file, index=False)
print(f"\n✓ Detailed results saved to: {output_file}")

# ============================================================================
# GAME-LEVEL IMPACT: What % of games have filtered-out attributes?
# ============================================================================
print("\n" + "=" * 100)
print("GAME-LEVEL IMPACT ANALYSIS")
print("=" * 100)
print("\nHow many games are affected by filtering out low-quality attributes?")
print("-" * 100)

game_impact_query = f"""
WITH indie_dev_pub_games AS (
    SELECT DISTINCT g.app_id
    FROM games g
    JOIN steamspy_insights s ON g.app_id = s.app_id
    JOIN tags t ON g.app_id = t.app_id
    WHERE s.developer = s.publisher
      AND t.tag = 'Indie'
      AND g.type = 'game'
),
game_wilson_scores AS (
    SELECT
        r.app_id,
        r.total
    FROM indie_dev_pub_games idp
    JOIN reviews r ON idp.app_id = r.app_id
    WHERE r.total > 0
),
-- Get stats for each attribute
tag_stats AS (
    SELECT
        t.tag AS attribute,
        COUNT(DISTINCT gws.app_id) AS game_count,
        SUM(gws.total) AS total_reviews
    FROM tags t
    JOIN game_wilson_scores gws ON t.app_id = gws.app_id
    GROUP BY t.tag
),
genre_stats AS (
    SELECT
        g.genre AS attribute,
        COUNT(DISTINCT gws.app_id) AS game_count,
        SUM(gws.total) AS total_reviews
    FROM genres g
    JOIN game_wilson_scores gws ON g.app_id = gws.app_id
    GROUP BY g.genre
),
category_stats AS (
    SELECT
        c.category AS attribute,
        COUNT(DISTINCT gws.app_id) AS game_count,
        SUM(gws.total) AS total_reviews
    FROM categories c
    JOIN game_wilson_scores gws ON c.app_id = gws.app_id
    GROUP BY c.category
),
-- Games with FAILED tags (restricted to indie dev==pub games)
games_with_failed_tags AS (
    SELECT DISTINCT gws.app_id
    FROM tags t
    JOIN tag_stats ts ON t.tag = ts.attribute
    JOIN game_wilson_scores gws ON t.app_id = gws.app_id
    WHERE ts.game_count < {MIN_GAME_COUNT} OR ts.total_reviews < {MIN_TOTAL_REVIEWS}
),
-- Games with FAILED genres (restricted to indie dev==pub games)
games_with_failed_genres AS (
    SELECT DISTINCT gws.app_id
    FROM genres g
    JOIN genre_stats gs ON g.genre = gs.attribute
    JOIN game_wilson_scores gws ON g.app_id = gws.app_id
    WHERE gs.game_count < {MIN_GAME_COUNT} OR gs.total_reviews < {MIN_TOTAL_REVIEWS}
),
-- Games with FAILED categories (restricted to indie dev==pub games)
games_with_failed_categories AS (
    SELECT DISTINCT gws.app_id
    FROM categories c
    JOIN category_stats cs ON c.category = cs.attribute
    JOIN game_wilson_scores gws ON c.app_id = gws.app_id
    WHERE cs.game_count < {MIN_GAME_COUNT} OR cs.total_reviews < {MIN_TOTAL_REVIEWS}
)
SELECT
    (SELECT COUNT(DISTINCT app_id) FROM indie_dev_pub_games) AS total_games,
    (SELECT COUNT(DISTINCT app_id) FROM games_with_failed_tags) AS games_with_failed_tags,
    (SELECT COUNT(DISTINCT app_id) FROM games_with_failed_genres) AS games_with_failed_genres,
    (SELECT COUNT(DISTINCT app_id) FROM games_with_failed_categories) AS games_with_failed_categories,
    (SELECT COUNT(DISTINCT app_id) FROM (
        SELECT app_id FROM games_with_failed_tags
        UNION
        SELECT app_id FROM games_with_failed_genres
        UNION
        SELECT app_id FROM games_with_failed_categories
    )) AS games_with_any_failed_attribute;
"""

game_impact = con.execute(game_impact_query).fetchone()
total_games = game_impact[0]
games_failed_tags = game_impact[1]
games_failed_genres = game_impact[2]
games_failed_categories = game_impact[3]
games_any_failed = game_impact[4]

print(f"\nTotal indie dev==publisher games: {total_games:,}")
print(f"\nGames affected by filtered attributes:")
print(f"  - Have ≥1 filtered TAG: {games_failed_tags:,} ({games_failed_tags/total_games*100:.1f}%)")
print(f"  - Have ≥1 filtered GENRE: {games_failed_genres:,} ({games_failed_genres/total_games*100:.1f}%)")
print(f"  - Have ≥1 filtered CATEGORY: {games_failed_categories:,} ({games_failed_categories/total_games*100:.1f}%)")
print(f"  - Have ≥1 filtered attribute (ANY TYPE): {games_any_failed:,} ({games_any_failed/total_games*100:.1f}%)")

print(f"\nGames with ONLY passing attributes: {total_games - games_any_failed:,} ({(total_games - games_any_failed)/total_games*100:.1f}%)")

print("\n" + "=" * 100)

con.close()

