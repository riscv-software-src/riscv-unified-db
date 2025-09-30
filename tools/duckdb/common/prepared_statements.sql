PREPARE profileFilterExtensions AS
SELECT name FROM
    query('SELECT extensions FROM udb.profiles WHERE name=' || $profile)
    WHERE presence=$mandatory_or_optional;
