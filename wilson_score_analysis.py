import duckdb
import math

con = duckdb.connect('steam_insights.duckdb', read_only=True)

# Define Wilson score calculation in SQL
# Formula: (p + z²/2n - z√(p(1-p)/n + z²/4n²)) / (1 + z²/n)
# where p = positive rate, n = total reviews, z = 1.96 for 95% confidence
wilson_score_sql = """
(
    (positive::FLOAT / NULLIF(total, 0) + 1.96*1.96/(2*total) -
     1.96 * SQRT((positive::FLOAT / NULLIF(total, 0) * (1 - positive::FLOAT / NULLIF(total, 0)) / total) +
                 (1.96*1.96 / (4*total*total))))
    /
    (1 + 1.96*1.96/total)
) AS wilson_score
"""

# Example query: Wilson scores by tag for indie games where developer == publisher
query = f"""
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
tag_wilson_scores AS (
    -- For each tag, calculate Wilson score for games WITH that tag
    SELECT
        t.tag,
        COUNT(DISTINCT r.app_id) AS game_count,
        SUM(r.positive) AS total_positive,
        SUM(r.negative) AS total_negative,
        SUM(r.total) AS total_reviews,
        {wilson_score_sql.replace('positive', 'SUM(r.positive)').replace('total', 'SUM(r.total)')}
    FROM tags t
    JOIN indie_dev_pub_games idp ON t.app_id = idp.app_id
    JOIN reviews r ON t.app_id = r.app_id
    WHERE r.total > 0  -- Only games with reviews
    GROUP BY t.tag
    HAVING COUNT(DISTINCT r.app_id) >= 10  -- At least 10 games
),
tag_wilson_scores_inverse AS (
    -- For each tag, calculate Wilson score for games WITHOUT that tag
    SELECT
        t.tag,
        COUNT(DISTINCT r.app_id) AS game_count_inverse,
        SUM(r.positive) AS total_positive_inverse,
        SUM(r.negative) AS total_negative_inverse,
        SUM(r.total) AS total_reviews_inverse,
        {wilson_score_sql.replace('positive', 'SUM(r.positive)').replace('total', 'SUM(r.total)').replace('AS wilson_score', 'AS wilson_score_inverse')}
    FROM (SELECT DISTINCT tag FROM tags) t
    CROSS JOIN indie_dev_pub_games idp
    JOIN reviews r ON idp.app_id = r.app_id
    WHERE r.total > 0
      AND NOT EXISTS (
          SELECT 1 FROM tags t2
          WHERE t2.app_id = idp.app_id
          AND t2.tag = t.tag
      )
    GROUP BY t.tag
    HAVING COUNT(DISTINCT r.app_id) >= 10
)
SELECT
    tws.tag,
    tws.game_count,
    ROUND(tws.wilson_score::NUMERIC, 4) AS wilson_score,
    tws.total_reviews,
    twsi.game_count_inverse,
    ROUND(twsi.wilson_score_inverse::NUMERIC, 4) AS wilson_score_inverse,
    twsi.total_reviews_inverse,
    ROUND((tws.wilson_score - twsi.wilson_score_inverse)::NUMERIC, 4) AS wilson_diff
FROM tag_wilson_scores tws
LEFT JOIN tag_wilson_scores_inverse twsi ON tws.tag = twsi.tag
ORDER BY wilson_diff DESC NULLS LAST
LIMIT 50;
"""

print("Wilson Score Analysis for Indie Games (Developer == Publisher)")
print("=" * 100)
print("\nTop tags by Wilson score difference:\n")

result = con.execute(query).df()
print(result.to_string(index=False))

# Save to CSV
result.to_csv('wilson_scores_by_tag.csv', index=False)
print("\n✓ Results saved to wilson_scores_by_tag.csv")

con.close()
