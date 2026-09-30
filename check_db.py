"""Jalankan sebelum server; hanya SELECT, tidak menulis database."""
from sqlalchemy import text
from db import engine, SCHEMA, ARTICLES_TABLE_NAME, ATTRITION_TABLE_NAME, ARTICLES_TABLE, ATTRITION_TABLE

def main():
    expected = {
        ARTICLES_TABLE_NAME: {'id','title','url','source','content','published_at','scraped_at'},
        ATTRITION_TABLE_NAME: {'EmployeeNumber','Department','Attrition','JobRole','MonthlyIncome','OverTime','YearsAtCompany'},
    }
    ok = True
    with engine.connect() as conn:
        print('Koneksi PostgreSQL OK')
        for name, required in expected.items():
            columns = set(conn.execute(text('''SELECT column_name FROM information_schema.columns
                WHERE table_schema=:schema AND table_name=:name'''), {'schema': SCHEMA, 'name': name}).scalars())
            if not columns:
                print(f'{SCHEMA}.{name}: TIDAK DITEMUKAN / TIDAK TERLIHAT OLEH AKUN')
                ok = False
                continue
            missing = required - columns
            print(f'{SCHEMA}.{name}: kolom kurang = {sorted(missing)}')
            ok = ok and not missing
            table = ARTICLES_TABLE if name == ARTICLES_TABLE_NAME else ATTRITION_TABLE
            n = conn.execute(text(f'SELECT COUNT(*) FROM {table}')).scalar_one()
            print(f'Jumlah baris: {n}')
            if n == 0:
                ok = False
                print('PERLU DIISI sebelum screenshot bukti data.')
        if ok:
            print('Pemeriksaan tabel/kolom/jumlah baris OK. Lanjutkan pengujian endpoint.')
    return 0 if ok else 1

if __name__ == '__main__':
    raise SystemExit(main())
