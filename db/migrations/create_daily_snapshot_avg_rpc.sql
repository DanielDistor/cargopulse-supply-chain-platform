-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New query)
-- Replaces the vessel_daily approach with a stable per-day average from snapshots.

CREATE OR REPLACE FUNCTION get_daily_snapshot_avg(days_back integer DEFAULT 7)
RETURNS TABLE(day date, vessel_count integer)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    DATE(logged_at) AS day,
    ROUND(AVG(total))::integer AS vessel_count
  FROM vessel_activity
  WHERE logged_at >= CURRENT_DATE - days_back
  GROUP BY DATE(logged_at)
  ORDER BY day;
END;
$$;
