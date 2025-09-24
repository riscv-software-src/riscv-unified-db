SELECT printf('# Base architecture');
SELECT printf('flags:');

SELECT printf('  %s: "%s"', name, long_name)
FROM udb.extensions
WHERE length(name) = 1
ORDER BY name
;
SELECT printf('####');
SELECT printf('');
