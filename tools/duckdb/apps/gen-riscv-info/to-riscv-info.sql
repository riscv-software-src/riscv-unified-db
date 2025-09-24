ATTACH '../../udb.duckdb';

.mode ascii
.headers off
.output 'riscv_info_udb.yml'

.read preface.sql
SELECT printf('---');

.read base.sql
.read combinations.sql
.read extensions.sql
.read profiles.sql

SELECT printf('###');

.output

DETACH udb;
