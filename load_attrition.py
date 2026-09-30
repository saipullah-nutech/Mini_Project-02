"""Opsional: muat CSV IBM HR mentah ke tabel baru. Tidak menimpa tabel existing."""
import argparse
from pathlib import Path
import pandas as pd
from db import engine, SCHEMA, ATTRITION_TABLE_NAME

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('csv_file', type=Path)
    args = parser.parse_args()
    df = pd.read_csv(args.csv_file)
    required = {'EmployeeNumber','Department','Attrition','JobRole','MonthlyIncome','OverTime','YearsAtCompany'}
    if required - set(df.columns):
        raise ValueError(f'Kolom wajib tidak ada: {sorted(required - set(df.columns))}')
    if df.empty or df['EmployeeNumber'].isna().any() or df['EmployeeNumber'].duplicated().any():
        raise ValueError('CSV kosong atau EmployeeNumber kosong/duplikat; periksa dataset.')
    # Raw CSV tetap disimpan tanpa agregasi; transformasi dilakukan saat query API.
    with engine.begin() as conn:
        df.to_sql(ATTRITION_TABLE_NAME, conn, schema=SCHEMA, index=False, if_exists='fail')
    print(f'{len(df)} karyawan dimuat ke {SCHEMA}.{ATTRITION_TABLE_NAME}')

if __name__ == '__main__':
    main()
