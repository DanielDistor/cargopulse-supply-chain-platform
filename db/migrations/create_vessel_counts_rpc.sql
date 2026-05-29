-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New query)
-- Creates a server-side function that returns distinct vessel counts per day.
-- This bypasses PostgREST's row-count cap by doing GROUP BY in Postgres.

CREATE OR REPLACE FUNCTION get_daily_vessel_counts(days_back integer DEFAULT 7)
RETURNS TABLE(day date, vessel_count bigint)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT vd.day, COUNT(*)::bigint AS vessel_count
  FROM vessel_daily vd
  WHERE vd.day >= CURRENT_DATE - days_back
  GROUP BY vd.day
  ORDER BY vd.day;
END;
$$;
