SELECT printf('# Known profiles');
SELECT printf('profiles:');
SELECT printf(
    e'  %s:\n    description: "%s"\n    bits: %d\n    flags:\n      mandatory:\n      optional:\n    extensions:\n      mandatory:\n      optional:',
    name, long_name, base)
FROM udb.profiles
ORDER BY name
;
SELECT printf('####');
SELECT printf('');
