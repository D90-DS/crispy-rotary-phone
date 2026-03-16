DROP TABLE IF EXISTS financials;
DROP TABLE IF EXISTS properties;
CREATE TABLE properties (
    property_id BIGINT PRIMARY KEY,
    address TEXT NOT NULL,
    metro_area TEXT,
    sq_footage BIGINT,
    property_type TEXT
);
CREATE TABLE financials (
    property_id BIGINT REFERENCES properties(property_id),
    revenue NUMERIC(18, 2),
    net_income NUMERIC(18, 2),
    expenses NUMERIC(18, 2)
);
INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES (1013730001, '40 RIVER ROAD', 'UPPER EAST SIDE (59-79) / Manhattan', 4786701, 'multifamily');
INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES (2051410120, '2049 BARTOW AVENUE', 'CO-OP CITY / Bronx', 13540113, 'multifamily');
INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES (4124950002, '163-15 BAISLEY BOULEVARD', 'SPRINGFIELD GARDENS / Queens', 6940450, 'multifamily');
INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES (2051350051, '120 ERSKINE PLACE', 'CO-OP CITY / Bronx', 5541031, 'multifamily');
INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES (1000940001, '80 GOLD STREET', 'SOUTHBRIDGE / Manhattan', 2163399, 'multifamily');
INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES (1002899001, '1 BOWERY', 'CHINATOWN / Manhattan', 1217600, 'multifamily');
INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES (1003110013, '357 GRAND STREET', 'LOWER EAST SIDE / Manhattan', 1025341, 'multifamily');
INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES (1002630008, '453 FDR DRIVE', 'LOWER EAST SIDE / Manhattan', 923000, 'multifamily');
INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES (1013700015, '425 EAST 58 STREET', 'MIDTOWN EAST / Manhattan', 988829, 'multifamily');
INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES (1013670001, '400 EAST 56 STREET', 'MIDTOWN EAST / Manhattan', 967300, 'multifamily');
INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES (1014030033, '150 EAST 69TH STREET', 'UPPER EAST SIDE (59-79) / Manhattan', 914921, 'multifamily');
INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES (1011250024, '15 WEST 72 STREET', 'UPPER WEST SIDE (59-79) / Manhattan', 667517, 'multifamily');
INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES (1003150001, '409 GRAND STREET', 'LOWER EAST SIDE / Manhattan', 1054290, 'multifamily');
INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES (1009290001, '401 1 AVENUE', 'KIPS BAY / Manhattan', 927591, 'multifamily');
INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES (1004320001, '66 1 AVENUE', 'EAST VILLAGE / Manhattan', 780062, 'multifamily');
INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES (1005550001, '772 BROADWAY', 'GREENWICH VILLAGE-CENTRAL / Manhattan', 718220, 'multifamily');
INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES (3072680001, '2885 WEST 12 STREET', 'CONEY ISLAND / Brooklyn', 1736700, 'multifamily');
INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES (1019780001, '100 LA SALLE STREET', 'MORNINGSIDE HEIGHTS / Manhattan', 1288976, 'multifamily');
INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES (1010300029, '200 CENTRAL PARK SOUTH', 'MIDTOWN WEST / Manhattan', 564196, 'multifamily');
INSERT INTO properties (property_id, address, metro_area, sq_footage, property_type) VALUES (1012040029, '300 CENTRAL PARK WEST', 'UPPER WEST SIDE (79-96) / Manhattan', 608532, 'multifamily');
INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES (1013730001, 213247530.0, 132304416.0, 80943114.0);
INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES (2051410120, 207163729.0, 77855650.0, 129308079.0);
INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES (4124950002, 124858696.0, 60243106.0, 64615590.0);
INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES (2051350051, 87492879.0, 35407188.0, 52085691.0);
INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES (1000940001, 68233604.0, 43549222.0, 24684383.0);
INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES (1002899001, 64447568.0, 31584544.0, 32863024.0);
INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES (1003110013, 54271299.0, 19532746.0, 34738553.0);
INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES (1002630008, 48854390.0, 19050720.0, 29803670.0);
INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES (1013700015, 44971943.0, 28656264.0, 16315679.0);
INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES (1013670001, 43683268.0, 28796521.0, 14886747.0);
INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES (1014030033, 42690214.0, 27228049.0, 15462165.0);
INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES (1011250024, 38669260.0, 25338945.0, 13330314.0);
INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES (1003150001, 37427295.0, 20221282.0, 17206013.0);
INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES (1009290001, 36983053.0, 21696353.0, 15286700.0);
INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES (1004320001, 36826727.0, 20453226.0, 16373501.0);
INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES (1005550001, 35192780.0, 20009609.0, 15183171.0);
INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES (3072680001, 35029239.0, 18217983.0, 16811256.0);
INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES (1019780001, 33796951.0, 18960837.0, 14836114.0);
INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES (1010300029, 31713457.0, 19662231.0, 12051227.0);
INSERT INTO financials (property_id, revenue, net_income, expenses) VALUES (1012040029, 31661920.0, 17665684.0, 13996236.0);