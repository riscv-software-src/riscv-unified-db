INSTALL yaml FROM community;
LOAD yaml;

-- TODO: Use SET to point to top of spec instead of hard coding path in FROM

-- Query all UDB yaml files for extensions and insert the results into a table
CREATE TABLE extensions AS (SELECT * FROM '../../spec/std/isa/ext/*.yaml');

SHOW TABLES;

ATTACH 'udb.duckdb';
COPY FROM DATABASE memory TO udb;
DETACH udb;
