import psycopg2
import psycopg2.extras
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    'dbname': os.environ.get('DB_NAME', 'ProDSGabungan'),
    'user': os.environ.get('DB_USER', 'postgres'), 
    'password': os.environ.get('DB_PASSWORD', 'hari123'),
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': os.environ.get('DB_PORT', '5432')
}

logger = logging.getLogger(__name__)

def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

def execute_query(query, params=None, fetch=False, fetchone=False):
    """
    Execute a database query
    
    Args:
        query: SQL query string
        params: Query parameters (tuple or list)
        fetch: Whether to fetch all results
        fetchone: Whether to fetch one result
        
    Returns:
        Query results or None
    """
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        if not conn:
            return None
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(query, params)
        
        if fetch:
            results = cursor.fetchall()
            return [dict(row) for row in results]
        elif fetchone:
            result = cursor.fetchone()
            return dict(result) if result else None
        else:
            conn.commit()
            return cursor.rowcount
            
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Query execution error: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def insert_dosen(dosen_data):
    """
    Insert or update dosen data
    
    Args:
        dosen_data: Dictionary with dosen information
        
    Returns:
        Dosen ID or None
    """
    query = """
        INSERT INTO tmp_dosen_dt (
            v_nama_dosen, v_id_googleScholar, n_total_publikasi,
            n_total_sitasi_gs, n_h_index_gs, n_i10_index_gs,
            v_sumber, t_tanggal_unduh, v_link_url
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (v_id_googleScholar) 
        DO UPDATE SET
            v_nama_dosen = EXCLUDED.v_nama_dosen,
            n_total_publikasi = EXCLUDED.n_total_publikasi,
            n_total_sitasi_gs = EXCLUDED.n_total_sitasi_gs,
            n_h_index_gs = EXCLUDED.n_h_index_gs,
            n_i10_index_gs = EXCLUDED.n_i10_index_gs,
            t_tanggal_unduh = EXCLUDED.t_tanggal_unduh
        RETURNING v_id_dosen
    """
    
    params = (
        dosen_data.get('nama'),
        dosen_data.get('scholar_id'),
        dosen_data.get('total_publikasi', 0),
        dosen_data.get('total_sitasi', 0),
        dosen_data.get('h_index', 0),
        dosen_data.get('i10_index', 0),
        'Google Scholar',
        dosen_data.get('tanggal_unduh'),
        dosen_data.get('profile_url')
    )
    
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        if not conn:
            return None
        
        cursor = conn.cursor()
        cursor.execute(query, params)
        dosen_id = cursor.fetchone()[0]
        conn.commit()
        return dosen_id
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error inserting dosen: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def insert_publikasi(publikasi_data):
    """
    Insert publikasi data
    
    Args:
        publikasi_data: Dictionary with publikasi information
        
    Returns:
        Publikasi ID or None
    """
    query = """
        INSERT INTO stg_publikasi_tr (
            v_judul, v_authors, v_tahun_publikasi,
            n_total_sitasi, v_sumber, v_link_url,
            t_tanggal_unduh, v_jenis
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (v_judul) DO NOTHING
        RETURNING v_id_publikasi
    """
    
    params = (
        publikasi_data.get('judul'),
        publikasi_data.get('authors'),
        publikasi_data.get('tahun'),
        publikasi_data.get('sitasi', 0),
        'Google Scholar',
        publikasi_data.get('link'),
        publikasi_data.get('tanggal_unduh'),
        publikasi_data.get('jenis', 'artikel')
    )
    
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        if not conn:
            return None
        
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchone()
        conn.commit()
        
        return result[0] if result else None
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error inserting publikasi: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_scraping_statistics():
    """Get scraping statistics from database"""
    query = """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN v_status = 'completed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN v_status = 'error' THEN 1 ELSE 0 END) as error,
            SUM(CASE WHEN v_status = 'processing' THEN 1 ELSE 0 END) as processing,
            SUM(CASE WHEN v_status IS NULL OR v_status = 'pending' THEN 1 ELSE 0 END) as pending
        FROM temp_dosenGS_scraping
        WHERE v_link IS NOT NULL
    """
    
    result = execute_query(query, fetchone=True)
    
    if result:
        return {
            'total': result.get('total', 0),
            'completed': result.get('completed', 0),
            'error': result.get('error', 0),
            'processing': result.get('processing', 0),
            'pending': result.get('pending', 0)
        }
    
    return {'total': 0, 'completed': 0, 'error': 0, 'processing': 0, 'pending': 0}

def update_scraping_status(author_name, status, error_message=None):
    """Update scraping status for an author"""
    if error_message:
        query = """
            UPDATE temp_dosenGS_scraping
            SET v_status = %s,
                v_error_message = %s,
                t_last_updated = NOW()
            WHERE v_nama = %s
        """
        params = (status, error_message, author_name)
    else:
        query = """
            UPDATE temp_dosenGS_scraping
            SET v_status = %s,
                t_last_updated = NOW()
            WHERE v_nama = %s
        """
        params = (status, author_name)
    
    return execute_query(query, params)

def get_pending_authors(limit=None, scrape_from_beginning=False):
    """Get list of authors pending scraping"""
    if scrape_from_beginning:
        query = """
            SELECT v_nama, v_link, COALESCE(v_status, 'pending') as status
            FROM temp_dosenGS_scraping
            WHERE v_link IS NOT NULL
            ORDER BY v_nama
        """
        params = None
    else:
        query = """
            SELECT v_nama, v_link, COALESCE(v_status, 'pending') as status
            FROM temp_dosenGS_scraping
            WHERE v_link IS NOT NULL
            AND (v_status IS NULL OR v_status IN ('pending', 'error', 'processing'))
            ORDER BY 
                CASE 
                    WHEN v_status = 'processing' THEN 1
                    WHEN v_status = 'error' THEN 2
                    ELSE 3
                END,
                v_nama
        """
        params = None
    
    if limit:
        query += f" LIMIT {limit}"
    
    return execute_query(query, params, fetch=True)