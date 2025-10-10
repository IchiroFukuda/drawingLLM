#!/usr/bin/env python3

"""
Supabase/PostgreSQL 接続テストスクリプト
環境変数やデータベース接続を確認する
"""

import os
import sys

try:
    import psycopg2
except ImportError:
    print("ERROR: psycopg2 is not installed. Please run: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)


def test_connection():
    """データベース接続をテスト"""
    
    # 環境変数の確認
    print("=" * 60)
    print("環境変数の確認")
    print("=" * 60)
    
    db_url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    
    if not db_url:
        print("❌ DATABASE_URL または SUPABASE_DB_URL が設定されていません")
        print("\n設定方法:")
        print("  export DATABASE_URL='postgresql://user:password@host:port/dbname'")
        print("\nSupabase の場合:")
        print("  1. Supabase ダッシュボード → Settings → Database")
        print("  2. Connection string の URI をコピー")
        print("  3. export DATABASE_URL='postgresql://postgres:[password]@[host]:5432/postgres'")
        return False
    
    # セキュリティのため、パスワード部分を隠して表示
    safe_url = db_url
    if "@" in db_url and ":" in db_url:
        parts = db_url.split("@")
        if ":" in parts[0]:
            user_pass = parts[0].split("://")[1]
            if ":" in user_pass:
                user = user_pass.split(":")[0]
                safe_url = db_url.replace(user_pass, f"{user}:***")
    
    print(f"✓ DATABASE_URL: {safe_url}")
    
    # 接続テスト
    print("\n" + "=" * 60)
    print("データベース接続テスト")
    print("=" * 60)
    
    try:
        conn = psycopg2.connect(db_url)
        print("✓ データベースに接続成功")
        
        # バージョン確認
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            print(f"✓ PostgreSQL バージョン: {version.split(',')[0]}")
        
        # テーブルの存在確認
        print("\n" + "=" * 60)
        print("テーブルの確認")
        print("=" * 60)
        
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """)
            tables = [row[0] for row in cur.fetchall()]
            
            if 'drawings' in tables and 'entities' in tables:
                print("✓ drawings テーブルが存在します")
                print("✓ entities テーブルが存在します")
                
                # レコード数の確認
                cur.execute("SELECT COUNT(*) FROM drawings;")
                drawing_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM entities;")
                entity_count = cur.fetchone()[0]
                
                print(f"\n現在のレコード数:")
                print(f"  - drawings: {drawing_count:,} 件")
                print(f"  - entities: {entity_count:,} 件")
            else:
                print("⚠ drawings または entities テーブルが見つかりません")
                print("\nスキーマを作成するには:")
                print("  psql $DATABASE_URL -f schema.sql")
                print("\nまたは:")
                print("  cat schema.sql | psql $DATABASE_URL")
                
                if tables:
                    print(f"\n既存のテーブル: {', '.join(tables)}")
                else:
                    print("\nテーブルが1つも存在しません")
        
        # 拡張機能の確認
        print("\n" + "=" * 60)
        print("PostgreSQL拡張機能の確認")
        print("=" * 60)
        
        with conn.cursor() as cur:
            cur.execute("""
                SELECT extname, extversion 
                FROM pg_extension 
                WHERE extname IN ('uuid-ossp', 'vector', 'pg_trgm')
                ORDER BY extname;
            """)
            extensions = cur.fetchall()
            
            ext_dict = {name: version for name, version in extensions}
            
            # uuid-ossp
            if 'uuid-ossp' in ext_dict:
                print(f"✓ uuid-ossp: {ext_dict['uuid-ossp']} (UUID生成)")
            else:
                print("⚠ uuid-ossp: 未インストール (推奨)")
            
            # vector (pgvector)
            if 'vector' in ext_dict:
                print(f"✓ pgvector: {ext_dict['vector']} (Embedding検索)")
            else:
                print("⚠ pgvector: 未インストール (Embedding機能に必要)")
                print("  インストール: CREATE EXTENSION vector;")
            
            # pg_trgm
            if 'pg_trgm' in ext_dict:
                print(f"✓ pg_trgm: {ext_dict['pg_trgm']} (全文検索)")
            else:
                print("ℹ pg_trgm: 未インストール (オプション)")
        
        conn.close()
        
        print("\n" + "=" * 60)
        print("✓ すべてのテストが完了しました")
        print("=" * 60)
        
        return True
        
    except psycopg2.Error as e:
        print(f"❌ データベース接続エラー: {e}")
        return False
    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
