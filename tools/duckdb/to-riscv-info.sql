-- INSTALL yaml FROM community;
-- LOAD yaml;

-- CREATE TABLE extensions_for_riscv_info(ext YAML);
-- INSERT INTO extensions_for_riscv_info
    -- (SELECT printf("E'%s: %s'", name, long_name) FROM udb.extensions);

ATTACH 'udb.duckdb';

.mode ascii
.headers off
.output 'out/riscv_info_udb.yml'

SELECT printf('# riscv_info_udb -- Generated from RISC-V Unified Database');
SELECT printf('############################################');
SELECT printf('# SPDX-FileCopyrightText = "Qualcomm Technologies, Inc. and/or its subsidiaries."');
SELECT printf('# SPDX-License-Identifier = "BSD-3-Clause-Clear"');
SELECT printf('############################################');
SELECT printf('');

SELECT printf('# Base architecture');
SELECT printf('flags:');

SELECT printf('    %s: %s', name, long_name)
FROM udb.extensions
WHERE length(name) = 1
ORDER BY name
;
SELECT printf('# ');


SELECT printf('# Known extensions');
SELECT printf('extensions:');

SELECT printf('    %s: %s', name, long_name)
FROM udb.extensions
WHERE length(name) > 1
ORDER BY name
;
SELECT printf('# ');


SELECT printf('# Combinations of flags');
SELECT printf('shorthands:');
SELECT printf('# ');

SELECT printf('# Known profiles');
SELECT printf('profiles:');
SELECT printf('# ');

SELECT printf('############################################');

.output

DETACH udb;
