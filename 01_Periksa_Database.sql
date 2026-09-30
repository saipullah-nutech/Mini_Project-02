-- Jalankan satu query setiap kali: blok query lalu Ctrl+Enter pada DBeaver.
SELECT COUNT(*) AS total_articles FROM ai_engineer.articles_saipul_ai2;

SELECT table_schema, table_name FROM information_schema.tables
WHERE table_schema = 'ai_engineer' AND table_name ILIKE '%attrition%'
ORDER BY table_name;

SELECT table_name, column_name, data_type FROM information_schema.columns
WHERE table_schema = 'ai_engineer'
AND table_name IN ('articles_saipul_ai2', 'raw_attrition_saipul_ai2')
ORDER BY table_name, ordinal_position;

SELECT source, COUNT(*) AS total, MIN(published_at) AS earliest_date,
MAX(published_at) AS latest_date FROM ai_engineer.articles_saipul_ai2
GROUP BY source ORDER BY source;

-- Query berikut hanya dijalankan setelah tabel attrition dipastikan ada.
SELECT COUNT(*) AS total_employees FROM ai_engineer.raw_attrition_saipul_ai2;

SELECT "Department", COUNT(*) AS total_employees
FROM ai_engineer.raw_attrition_saipul_ai2 GROUP BY "Department" ORDER BY "Department";

-- Pembanding statistik Sales dengan respons Task 3.
SELECT COUNT(*) AS total_employees,
COUNT(*) FILTER (WHERE "Attrition"='Yes') AS attrition_count,
ROUND((COUNT(*) FILTER (WHERE "Attrition"='Yes'))::numeric / NULLIF(COUNT(*),0),4) AS attrition_rate,
ROUND(AVG("MonthlyIncome")::numeric,2) AS avg_income,
MIN("MonthlyIncome") AS min_income, MAX("MonthlyIncome") AS max_income
FROM ai_engineer.raw_attrition_saipul_ai2 WHERE "Department"='Sales';

-- Pembanding Task 4: semua kriteria harus terpenuhi.
WITH dept_avg AS (
 SELECT "Department", AVG("MonthlyIncome") AS avg_income
 FROM ai_engineer.raw_attrition_saipul_ai2 GROUP BY "Department"
)
SELECT e.*, d.avg_income AS department_avg_income
FROM ai_engineer.raw_attrition_saipul_ai2 e
JOIN dept_avg d ON e."Department"=d."Department"
WHERE e."OverTime"='Yes' AND e."YearsAtCompany"<3
AND e."MonthlyIncome"<d.avg_income
ORDER BY e."EmployeeNumber" LIMIT 20;
