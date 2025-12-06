import duckdb

# Connect to the database
con = duckdb.connect('steam_insights.duckdb', read_only=True)

# Example: Find top indie games where developer == publisher
query = """
SELECT
    g.name,
    s.developer,
    r.positive,
    r.negative,
    r.review_score_description
FROM games g
JOIN steamspy_insights s ON g.app_id = s.app_id
JOIN reviews r ON g.app_id = r.app_id
JOIN tags t ON g.app_id = t.app_id
WHERE s.developer = s.publisher
  AND t.tag = 'Indie'
  AND r.total > 1000
ORDER BY r.positive DESC
LIMIT 10;
"""

print("Top 10 Indie Games (Developer == Publisher) by positive reviews:\n")
result = con.execute(query).df()
print(result.to_string(index=False))

con.close()
