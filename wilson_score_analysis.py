import duckdb
import math

con = duckdb.connect('steam_insights.duckdb', read_only=True)

# Example query: Median Wilson scores by tag for indie games where developer == publisher
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
tag_median_wilson AS (
    -- For each tag, calculate median Wilson score of games WITH that tag
    SELECT
        t.tag,
        COUNT(DISTINCT gws.app_id) AS game_count,
        MEDIAN(gws.wilson_score) AS median_wilson_score,
        SUM(gws.total) AS total_reviews
    FROM tags t
    JOIN game_wilson_scores gws ON t.app_id = gws.app_id
    GROUP BY t.tag
    HAVING COUNT(DISTINCT gws.app_id) >= 10  -- At least 10 games
),
tag_median_wilson_inverse AS (
    -- For each tag, calculate median Wilson score of games WITHOUT that tag
    SELECT
        all_tags.tag,
        COUNT(DISTINCT gws.app_id) AS game_count_inverse,
        MEDIAN(gws.wilson_score) AS median_wilson_score_inverse,
        SUM(gws.total) AS total_reviews_inverse
    FROM (SELECT DISTINCT tag FROM tags) all_tags
    CROSS JOIN game_wilson_scores gws
    WHERE NOT EXISTS (
        SELECT 1 FROM tags t2
        WHERE t2.app_id = gws.app_id
        AND t2.tag = all_tags.tag
    )
    GROUP BY all_tags.tag
    HAVING COUNT(DISTINCT gws.app_id) >= 10
)
SELECT
    tmw.tag,
    tmw.game_count,
    ROUND(tmw.median_wilson_score::NUMERIC, 4) AS median_wilson_score,
    tmw.total_reviews,
    tmwi.game_count_inverse,
    ROUND(tmwi.median_wilson_score_inverse::NUMERIC, 4) AS median_wilson_score_inverse,
    tmwi.total_reviews_inverse,
    ROUND((tmw.median_wilson_score - tmwi.median_wilson_score_inverse)::NUMERIC, 4) AS wilson_diff
FROM tag_median_wilson tmw
LEFT JOIN tag_median_wilson_inverse tmwi ON tmw.tag = tmwi.tag
ORDER BY wilson_diff DESC NULLS LAST
LIMIT 50;
"""

print("Median Wilson Score Analysis for Indie Games (Developer == Publisher)")
print("=" * 100)
print("\nTop tags by median Wilson score difference (prevents outliers from skewing results):\n")

result = con.execute(query).df()
print(result.to_string(index=False))

# Save to CSV
result.to_csv('wilson_scores_by_tag_median.csv', index=False)
print("\n✓ Results saved to wilson_scores_by_tag_median.csv")

con.close()
