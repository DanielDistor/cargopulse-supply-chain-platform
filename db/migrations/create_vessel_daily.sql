-- Run this in Supabase SQL Editor
-- Creates the vessel_daily table for tracking distinct vessels per day

CREATE TABLE vessel_daily (
    mmsi TEXT NOT NULL,
    day  DATE NOT NULL DEFAULT CURRENT_DATE,
    PRIMARY KEY (mmsi, day)
);

ALTER TABLE vessel_daily ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_anon_all" ON vessel_daily FOR ALL TO anon
    USING (true) WITH CHECK (true);
