import duckdb

con = duckdb.connect('steam_insights.duckdb', read_only=True)

print("=" * 80)
print("Checking overlap between is_free column and 'Free to Play' tag/genre")
print("=" * 80)

# 1. Check how many games are marked as free
result = con.execute("""
    SELECT
        is_free,
        COUNT(*) as game_count
    FROM games
    WHERE type = 'game'
    GROUP BY is_free
    ORDER BY is_free
""").df()
print("\n1. Games by is_free flag:")
print(result.to_string(index=False))

# 2. Check how many games have "Free to Play" tag
result = con.execute("""
    SELECT COUNT(DISTINCT app_id) as count
    FROM tags
    WHERE tag = 'Free to Play'
""").fetchone()
print(f"\n2. Games with 'Free to Play' tag: {result[0]:,}")

# 3. Check how many games have "Free to Play" genre
result = con.execute("""
    SELECT COUNT(DISTINCT app_id) as count
    FROM genres
    WHERE genre = 'Free to Play' OR genre = 'Free To Play'
""").fetchone()
print(f"   Games with 'Free to Play' genre: {result[0]:,}")

# 4. Games that are is_free=1 but DON'T have the tag
result = con.execute("""
    SELECT COUNT(DISTINCT g.app_id) as count
    FROM games g
    WHERE g.is_free = '1'
      AND g.type = 'game'
      AND NOT EXISTS (
          SELECT 1 FROM tags t
          WHERE t.app_id = g.app_id
          AND t.tag = 'Free to Play'
      )
""").fetchone()
print(f"\n3. Games marked is_free=1 but WITHOUT 'Free to Play' tag: {result[0]:,}")

# 5. Games that have the tag but are NOT is_free=1
result = con.execute("""
    SELECT COUNT(DISTINCT t.app_id) as count
    FROM tags t
    JOIN games g ON t.app_id = g.app_id
    WHERE t.tag = 'Free to Play'
      AND g.type = 'game'
      AND g.is_free != '1'
""").fetchone()
print(f"   Games with 'Free to Play' tag but is_free != 1: {result[0]:,}")

# 6. Show some examples of mismatches
print("\n4. Sample games where is_free=1 but no 'Free to Play' tag:")
result = con.execute("""
    SELECT
        g.app_id,
        g.name,
        g.is_free
    FROM games g
    WHERE g.is_free = '1'
      AND g.type = 'game'
      AND NOT EXISTS (
          SELECT 1 FROM tags t
          WHERE t.app_id = g.app_id
          AND t.tag = 'Free to Play'
      )
    LIMIT 10
""").df()
print(result.to_string(index=False))

print("\n5. Sample games with 'Free to Play' tag but is_free != 1:")
result = con.execute("""
    SELECT
        g.app_id,
        g.name,
        g.is_free
    FROM tags t
    JOIN games g ON t.app_id = g.app_id
    WHERE t.tag = 'Free to Play'
      AND g.type = 'game'
      AND g.is_free != '1'
    LIMIT 10
""").df()
print(result.to_string(index=False))

con.close()
