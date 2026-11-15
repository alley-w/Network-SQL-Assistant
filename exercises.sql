-- First, inspect the tables.
SELECT name FROM sqlite_master WHERE type = 'table';
SELECT * FROM devices;
PRAGMA table_info(device_metrics);

-- Worked example: associate devices with their sites using a foreign key.
SELECT d.hostname, s.name AS site
FROM devices AS d
JOIN sites AS s ON d.site_id = s.id;

-- Your turn:
-- 1. How many metric samples are there?
-- 2. What was the average CPU percentage for each device over the full week?
-- 3. Which device had the most samples above 80% CPU?
-- 4. Which site had the highest average CPU on November 3 (UTC)?
-- 5. Which devices averaged above 50% memory? (Try HAVING.)
