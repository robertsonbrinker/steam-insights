import duckdb
import math

con = duckdb.connect('steam_insights.duckdb', read_only=True)

# Example query: Median Wilson scores by tag/genre/category for indie games where developer == publisher
query = """
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
),
-- TAGS ANALYSIS
tag_median_wilson AS (
    SELECT
        t.tag AS attribute,
        'tag' AS type,
        COUNT(DISTINCT gws.app_id) AS game_count,
        MEDIAN(gws.wilson_score) AS median_wilson_score,
        SUM(gws.total) AS total_reviews
    FROM tags t
    JOIN game_wilson_scores gws ON t.app_id = gws.app_id
    GROUP BY t.tag
    HAVING COUNT(DISTINCT gws.app_id) >= 10
),
tag_median_wilson_inverse AS (
    SELECT
        all_attrs.attribute,
        COUNT(DISTINCT gws.app_id) AS game_count_inverse,
        MEDIAN(gws.wilson_score) AS median_wilson_score_inverse,
        SUM(gws.total) AS total_reviews_inverse
    FROM (SELECT DISTINCT tag AS attribute FROM tags) all_attrs
    CROSS JOIN game_wilson_scores gws
    WHERE NOT EXISTS (
        SELECT 1 FROM tags t2
        WHERE t2.app_id = gws.app_id AND t2.tag = all_attrs.attribute
    )
    GROUP BY all_attrs.attribute
    HAVING COUNT(DISTINCT gws.app_id) >= 10
),
-- GENRES ANALYSIS
genre_median_wilson AS (
    SELECT
        g.genre AS attribute,
        'genre' AS type,
        COUNT(DISTINCT gws.app_id) AS game_count,
        MEDIAN(gws.wilson_score) AS median_wilson_score,
        SUM(gws.total) AS total_reviews
    FROM genres g
    JOIN game_wilson_scores gws ON g.app_id = gws.app_id
    GROUP BY g.genre
    HAVING COUNT(DISTINCT gws.app_id) >= 10
),
genre_median_wilson_inverse AS (
    SELECT
        all_attrs.attribute,
        COUNT(DISTINCT gws.app_id) AS game_count_inverse,
        MEDIAN(gws.wilson_score) AS median_wilson_score_inverse,
        SUM(gws.total) AS total_reviews_inverse
    FROM (SELECT DISTINCT genre AS attribute FROM genres) all_attrs
    CROSS JOIN game_wilson_scores gws
    WHERE NOT EXISTS (
        SELECT 1 FROM genres g2
        WHERE g2.app_id = gws.app_id AND g2.genre = all_attrs.attribute
    )
    GROUP BY all_attrs.attribute
    HAVING COUNT(DISTINCT gws.app_id) >= 10
),
-- CATEGORIES ANALYSIS
category_median_wilson AS (
    SELECT
        c.category AS attribute,
        'category' AS type,
        COUNT(DISTINCT gws.app_id) AS game_count,
        MEDIAN(gws.wilson_score) AS median_wilson_score,
        SUM(gws.total) AS total_reviews
    FROM categories c
    JOIN game_wilson_scores gws ON c.app_id = gws.app_id
    GROUP BY c.category
    HAVING COUNT(DISTINCT gws.app_id) >= 10
),
category_median_wilson_inverse AS (
    SELECT
        all_attrs.attribute,
        COUNT(DISTINCT gws.app_id) AS game_count_inverse,
        MEDIAN(gws.wilson_score) AS median_wilson_score_inverse,
        SUM(gws.total) AS total_reviews_inverse
    FROM (SELECT DISTINCT category AS attribute FROM categories) all_attrs
    CROSS JOIN game_wilson_scores gws
    WHERE NOT EXISTS (
        SELECT 1 FROM categories c2
        WHERE c2.app_id = gws.app_id AND c2.category = all_attrs.attribute
    )
    GROUP BY all_attrs.attribute
    HAVING COUNT(DISTINCT gws.app_id) >= 10
),
-- IS_FREE ANALYSIS (Pricing Model)
is_free_median_wilson AS (
    SELECT
        CASE WHEN g.is_free = '1' THEN 'Free' ELSE 'Paid' END AS attribute,
        'pricing' AS type,
        COUNT(DISTINCT gws.app_id) AS game_count,
        MEDIAN(gws.wilson_score) AS median_wilson_score,
        SUM(gws.total) AS total_reviews
    FROM games g
    JOIN game_wilson_scores gws ON g.app_id = gws.app_id
    WHERE g.type = 'game'
    GROUP BY g.is_free
),
is_free_median_wilson_inverse AS (
    SELECT
        CASE WHEN pricing_type = '1' THEN 'Free' ELSE 'Paid' END AS attribute,
        COUNT(DISTINCT gws.app_id) AS game_count_inverse,
        MEDIAN(gws.wilson_score) AS median_wilson_score_inverse,
        SUM(gws.total) AS total_reviews_inverse
    FROM (SELECT DISTINCT is_free AS pricing_type FROM games WHERE type = 'game') pricing_types
    CROSS JOIN game_wilson_scores gws
    JOIN games g ON gws.app_id = g.app_id
    WHERE g.is_free != pricing_types.pricing_type
      AND g.type = 'game'
    GROUP BY pricing_types.pricing_type
),
-- COMBINE ALL FOUR
combined_results AS (
    SELECT
        tmw.type,
        tmw.attribute,
        tmw.game_count,
        ROUND(tmw.median_wilson_score::NUMERIC, 4) AS median_wilson_score,
        tmw.total_reviews,
        tmwi.game_count_inverse,
        ROUND(tmwi.median_wilson_score_inverse::NUMERIC, 4) AS median_wilson_score_inverse,
        tmwi.total_reviews_inverse,
        ROUND((tmw.median_wilson_score - tmwi.median_wilson_score_inverse)::NUMERIC, 4) AS wilson_diff
    FROM tag_median_wilson tmw
    LEFT JOIN tag_median_wilson_inverse tmwi ON tmw.attribute = tmwi.attribute

    UNION ALL

    SELECT
        gmw.type,
        gmw.attribute,
        gmw.game_count,
        ROUND(gmw.median_wilson_score::NUMERIC, 4) AS median_wilson_score,
        gmw.total_reviews,
        gmwi.game_count_inverse,
        ROUND(gmwi.median_wilson_score_inverse::NUMERIC, 4) AS median_wilson_score_inverse,
        gmwi.total_reviews_inverse,
        ROUND((gmw.median_wilson_score - gmwi.median_wilson_score_inverse)::NUMERIC, 4) AS wilson_diff
    FROM genre_median_wilson gmw
    LEFT JOIN genre_median_wilson_inverse gmwi ON gmw.attribute = gmwi.attribute

    UNION ALL

    SELECT
        cmw.type,
        cmw.attribute,
        cmw.game_count,
        ROUND(cmw.median_wilson_score::NUMERIC, 4) AS median_wilson_score,
        cmw.total_reviews,
        cmwi.game_count_inverse,
        ROUND(cmwi.median_wilson_score_inverse::NUMERIC, 4) AS median_wilson_score_inverse,
        cmwi.total_reviews_inverse,
        ROUND((cmw.median_wilson_score - cmwi.median_wilson_score_inverse)::NUMERIC, 4) AS wilson_diff
    FROM category_median_wilson cmw
    LEFT JOIN category_median_wilson_inverse cmwi ON cmw.attribute = cmwi.attribute

    UNION ALL

    SELECT
        ifmw.type,
        ifmw.attribute,
        ifmw.game_count,
        ROUND(ifmw.median_wilson_score::NUMERIC, 4) AS median_wilson_score,
        ifmw.total_reviews,
        ifmwi.game_count_inverse,
        ROUND(ifmwi.median_wilson_score_inverse::NUMERIC, 4) AS median_wilson_score_inverse,
        ifmwi.total_reviews_inverse,
        ROUND((ifmw.median_wilson_score - ifmwi.median_wilson_score_inverse)::NUMERIC, 4) AS wilson_diff
    FROM is_free_median_wilson ifmw
    LEFT JOIN is_free_median_wilson_inverse ifmwi ON ifmw.attribute = ifmwi.attribute
)
SELECT *
FROM combined_results
ORDER BY wilson_diff DESC NULLS LAST
LIMIT 100;
"""

print("Median Wilson Score Analysis for Indie Games (Developer == Publisher)")
print("=" * 100)
print("\nTop attributes (tags/genres/categories/pricing) by median Wilson score difference:")
print("(Median prevents outliers from skewing results)\n")

result = con.execute(query).df()
print(result.to_string(index=False))

# Save to CSV
result.to_csv('wilson_scores_by_attribute.csv', index=False)
print("\n✓ Results saved to wilson_scores_by_attribute.csv")

con.close()
