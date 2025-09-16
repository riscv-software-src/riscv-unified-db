INSTALL yaml FROM community;
LOAD yaml;

-- SELECT * FROM '../../spec/std/isa/ext/*.yaml';
-- Query all UDB yaml files for extensions and insert the results into a table
CREATE TABLE extensions AS
SELECT * FROM '../../spec/std/isa/ext/*.yaml';

SHOW TABLES;

ATTACH 'udb.duckdb';
COPY FROM DATABASE memory TO udb;
DETACH udb;
