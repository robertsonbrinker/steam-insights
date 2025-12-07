import duckdb

con = duckdb.connect('steam_insights.duckdb', read_only=True)

# Find $54 games that are indie dev==publisher
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
game_prices AS (
    SELECT
        TRY_CAST(g.app_id AS INTEGER) AS app_id,
        g.name,
        ROUND(TRY_CAST(json_extract_string(g.price_overview, '$.final') AS INTEGER) / 100.0, 2) AS price
    FROM games g
    WHERE g.app_id IN (SELECT CAST(app_id AS VARCHAR) FROM indie_dev_pub_games)
      AND g.type = 'game'
      AND g.is_free = '0'
      AND g.price_overview IS NOT NULL
      AND LENGTH(g.price_overview) > 5
      AND SUBSTRING(g.price_overview, 1, 1) = '{'
)
SELECT
    gp.app_id,
    gp.name,
    gp.price,
    r.positive,
    r.negative,
    r.total,
    r.review_score_description,
    ROUND((
        (r.positive::FLOAT / NULLIF(r.total::FLOAT, 0) + 1.96*1.96/(2*r.total::FLOAT) -
         1.96 * SQRT((r.positive::FLOAT / NULLIF(r.total::FLOAT, 0) * (1 - r.positive::FLOAT / NULLIF(r.total::FLOAT, 0)) / r.total::FLOAT) +
                     (1.96*1.96 / (4*r.total::FLOAT*r.total::FLOAT))))
        /
        (1 + 1.96*1.96/r.total::FLOAT)
    )::NUMERIC, 4) AS wilson_score
FROM game_prices gp
JOIN reviews r ON gp.app_id = r.app_id
WHERE gp.price = 54.0
  AND r.total > 0
ORDER BY wilson_score DESC;
"""

print("=" * 100)
print("Games priced at $54.00 (Indie, Developer == Publisher)")
print("=" * 100)
print()

result = con.execute(query).df()
print(result.to_string(index=False))

print(f"\n\nTotal games: {len(result)}")
print(f"Median Wilson Score: {result['wilson_score'].median():.4f}")
print(f"Mean Wilson Score: {result['wilson_score'].mean():.4f}")

con.close()
