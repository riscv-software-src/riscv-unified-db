SELECT printf('# Known extensions');
SELECT printf('extensions:');

SELECT printf('  %s: "%s"', name, long_name)
FROM udb.extensions
WHERE length(name) > 1
ORDER BY name
;
SELECT printf('####');
SELECT printf('');
