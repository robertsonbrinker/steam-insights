import duckdb
import pandas as pd

# Configuration: Minimum thresholds for an attribute pair to be included
MIN_GAME_COUNT = 200  # Minimum number of distinct games with BOTH attributes
MIN_TOTAL_REVIEWS = 27000  # Minimum total reviews across all games with BOTH attributes

# Maximum number of results to display and save
MAX_RESULTS = 100  # Top N pairs by wilson_diff to include in output

# Which pair types to analyze (set to False to skip and save memory)
ANALYZE_TAG_TAG = True
ANALYZE_TAG_GENRE = False
ANALYZE_TAG_CATEGORY = False
ANALYZE_GENRE_GENRE = False
ANALYZE_GENRE_CATEGORY = False
ANALYZE_CATEGORY_CATEGORY = False

con = duckdb.connect('steam_insights.duckdb', read_only=True)

# Optimize DuckDB settings for memory usage
con.execute("SET memory_limit='6GB'")
con.execute("SET max_temp_directory_size='13GB'")
con.execute("SET preserve_insertion_order=false")
con.execute("SET threads=4")

print("Median Wilson Score Analysis for Attribute PAIRS - Indie Games (Developer == Publisher)")
print("=" * 120)
print(f"\nFilters: Min {MIN_GAME_COUNT} games AND min {MIN_TOTAL_REVIEWS:,} total reviews per attribute pair")
print("(Median prevents outliers from skewing results)")
print("(Inverse = median Wilson score for games WITHOUT both attributes in the pair)\n")

all_results = []

# Base CTEs that will be reused - now includes materialized game-attribute mappings
base_query = f"""
WITH indie_dev_pub_games AS (
    -- Get games where developer == publisher and have 'Indie' tag
    SELECT DISTINCT g.app_id
    FROM games g
    JOIN steamspy_insights s ON g.app_id = s.app_id
    JOIN tags t ON g.app_id = t.app_id
    WHERE s.developer = s.publisher
      AND t.tag = 'Indie'
      AND g.type = 'game'
),
game_wilson_scores AS (
    -- Calculate Wilson score for each game
    SELECT
        r.app_id,
        r.positive,
        r.negative,
        r.total,
        (
            (r.positive::FLOAT / NULLIF(r.total::FLOAT, 0) + 1.96*1.96/(2*r.total::FLOAT) -
             1.96 * SQRT((r.positive::FLOAT / NULLIF(r.total::FLOAT, 0) * (1 - r.positive::FLOAT / NULLIF(r.total::FLOAT, 0)) / r.total::FLOAT) +
                         (1.96*1.96 / (4*r.total::FLOAT*r.total::FLOAT))))
            /
            (1 + 1.96*1.96/r.total::FLOAT)
        ) AS wilson_score
    FROM indie_dev_pub_games idp
    JOIN reviews r ON idp.app_id = r.app_id
    WHERE r.total > 0  -- Only games with reviews
)
"""

def analyze_pair_type(pair_type, table1, table2, col1, col2, use_ordering=True):
    """
    Analyze a specific pair type and return results.

    This version pre-materializes games with each pair to avoid expensive correlated subqueries.
    """

    ordering_clause = f"AND t1.{col1} < t2.{col2}" if use_ordering else ""

    query = base_query + f"""
-- Materialize which games have which attribute pairs (MEMORY OPTIMIZATION)
, games_with_pairs AS (
    SELECT
        t1.{col1} AS attribute_1,
        t2.{col2} AS attribute_2,
        gws.app_id,
        gws.wilson_score,
        gws.total
    FROM {table1} t1
    JOIN {table2} t2 ON t1.app_id = t2.app_id {ordering_clause}
    JOIN game_wilson_scores gws ON t1.app_id = gws.app_id
),
-- Get pairs with their median Wilson scores (games WITH both attributes)
pairs_median_wilson AS (
    SELECT
        attribute_1,
        attribute_2,
        '{pair_type}' AS type,
        COUNT(DISTINCT app_id) AS game_count,
        MEDIAN(wilson_score) AS median_wilson_score,
        SUM(total) AS total_reviews
    FROM games_with_pairs
    GROUP BY attribute_1, attribute_2
    HAVING COUNT(DISTINCT app_id) >= {MIN_GAME_COUNT}
       AND SUM(total) >= {MIN_TOTAL_REVIEWS}
),
-- For inverse: get all games in a flat table for easy anti-join
all_games_flat AS (
    SELECT
        app_id,
        wilson_score,
        total
    FROM game_wilson_scores
),
-- Calculate inverse metrics by LEFT ANTI JOIN (much faster than correlated subqueries!)
pairs_with_inverse AS (
    SELECT
        pmw.attribute_1,
        pmw.attribute_2,
        pmw.type,
        pmw.game_count,
        pmw.median_wilson_score,
        pmw.total_reviews,
        -- Inverse: games that DON'T have both attributes
        COUNT(DISTINCT agf.app_id) AS game_count_inverse,
        MEDIAN(agf.wilson_score) AS median_wilson_score_inverse,
        SUM(agf.total) AS total_reviews_inverse
    FROM pairs_median_wilson pmw
    CROSS JOIN all_games_flat agf
    -- Anti-join: exclude games that have this specific pair
    LEFT JOIN games_with_pairs gwp
        ON agf.app_id = gwp.app_id
        AND gwp.attribute_1 = pmw.attribute_1
        AND gwp.attribute_2 = pmw.attribute_2
    WHERE gwp.app_id IS NULL  -- Keep only games that DON'T have this pair
    GROUP BY pmw.attribute_1, pmw.attribute_2, pmw.type, pmw.game_count, pmw.median_wilson_score, pmw.total_reviews
)
SELECT
    type,
    attribute_1 || ' + ' || attribute_2 AS attribute_pair,
    attribute_1,
    attribute_2,
    game_count,
    ROUND(median_wilson_score::NUMERIC, 4) AS median_wilson_score,
    total_reviews,
    game_count_inverse,
    ROUND(median_wilson_score_inverse::NUMERIC, 4) AS median_wilson_score_inverse,
    total_reviews_inverse,
    ROUND((median_wilson_score - median_wilson_score_inverse)::NUMERIC, 4) AS wilson_diff
FROM pairs_with_inverse
WHERE game_count_inverse >= {MIN_GAME_COUNT}
  AND total_reviews_inverse >= {MIN_TOTAL_REVIEWS}
ORDER BY wilson_diff DESC
"""

    print(f"\nProcessing {pair_type} pairs...")
    result = con.execute(query).df()
    print(f"  Found {len(result)} pairs meeting criteria")
    return result

# Process each pair type separately
if ANALYZE_TAG_TAG:
    tag_tag_results = analyze_pair_type('tag+tag', 'tags', 'tags', 'tag', 'tag', use_ordering=True)
    all_results.append(tag_tag_results)

if ANALYZE_TAG_GENRE:
    tag_genre_results = analyze_pair_type('tag+genre', 'tags', 'genres', 'tag', 'genre', use_ordering=False)
    all_results.append(tag_genre_results)

if ANALYZE_TAG_CATEGORY:
    tag_category_results = analyze_pair_type('tag+category', 'tags', 'categories', 'tag', 'category', use_ordering=False)
    all_results.append(tag_category_results)

if ANALYZE_GENRE_GENRE:
    genre_genre_results = analyze_pair_type('genre+genre', 'genres', 'genres', 'genre', 'genre', use_ordering=True)
    all_results.append(genre_genre_results)

if ANALYZE_GENRE_CATEGORY:
    genre_category_results = analyze_pair_type('genre+category', 'genres', 'categories', 'genre', 'category', use_ordering=False)
    all_results.append(genre_category_results)

if ANALYZE_CATEGORY_CATEGORY:
    category_category_results = analyze_pair_type('category+category', 'categories', 'categories', 'category', 'category', use_ordering=True)
    all_results.append(category_category_results)

# Combine all results
if all_results:
    combined_results = pd.concat(all_results, ignore_index=True)
    combined_results = combined_results.sort_values('wilson_diff', ascending=False).head(MAX_RESULTS)

    print("\n" + "=" * 120)
    print(f"Top {len(combined_results)} attribute pairs by Wilson score difference (limited to {MAX_RESULTS}):")
    print(combined_results.to_string(index=False))

    # Save to CSV
    combined_results.to_csv('wilson_scores_by_attribute_pairs.csv', index=False)
    print(f"\n✓ Results saved to wilson_scores_by_attribute_pairs.csv ({len(combined_results)} pairs)")
else:
    print("\nNo pair types selected for analysis!")

con.close()
