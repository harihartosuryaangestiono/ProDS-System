from flask import Blueprint, request, jsonify, current_app
from flask_socketio import emit
import sys
import os
from datetime import datetime
import threading
import traceback
import logging

# Add scrapers directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scrapers'))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import DB_CONFIG
from task.scraping_tasks import (
    scrape_sinta_dosen_task,
    scrape_sinta_scopus_task,
    scrape_sinta_googlescholar_task,
    scrape_sinta_garuda_task
)
from flask_cors import cross_origin

logger = logging.getLogger(__name__)

scraping_bp = Blueprint('scraping', __name__)

# Store active jobs
active_jobs = {}

# ============================================================================
# GS SCRAPING LOCK — hanya 1 GS job boleh berjalan sekaligus
# (mencegah multiple Chrome instance yang menghabiskan RAM 3.5GB)
# ============================================================================
_gs_lock = threading.Lock()
_gs_running = False
_gs_running_job_id = None
_gs_started_at = None
GS_JOB_TIMEOUT = 7200  # 2 jam maksimum


def _gs_acquire(job_id):
    """
    Coba acquire GS lock.
    Return True jika berhasil (job boleh jalan), False jika sudah ada job lain.
    Auto-release jika job lama sudah melewati timeout.
    """
    global _gs_running, _gs_running_job_id, _gs_started_at
    with _gs_lock:
        # Auto-release jika job lama sudah timeout
        if _gs_running and _gs_started_at:
            elapsed = (datetime.now() - _gs_started_at).total_seconds()
            if elapsed > GS_JOB_TIMEOUT:
                print(f"⚠️ GS job '{_gs_running_job_id}' timeout ({elapsed:.0f}s), auto-releasing lock")
                _gs_running = False
                _gs_running_job_id = None
                _gs_started_at = None

        if _gs_running:
            return False
        _gs_running = True
        _gs_running_job_id = job_id
        _gs_started_at = datetime.now()
        return True


def _gs_release():
    """Lepaskan GS lock setelah job selesai/gagal."""
    global _gs_running, _gs_running_job_id, _gs_started_at
    with _gs_lock:
        _gs_running = False
        _gs_running_job_id = None
        _gs_started_at = None


# ============================================================================
# PROGRESS EMIT
# ============================================================================

def emit_progress(job_id, progress_data):
    """Emit progress update via SocketIO"""
    try:
        from app import socketio
        socketio.emit('scraping_progress', {
            'job_id': job_id,
            'progress': progress_data
        })
        print(f"✅ Progress emitted for job {job_id}: {progress_data.get('message', 'N/A')}")
    except Exception as e:
        print(f"⚠️ Error emitting progress: {e}")


# ============================================================================
# GENERIC SINTA TASK RUNNER
# ============================================================================

def run_scraping_task(job_id, task_func, task_kwargs):
    """Run scraping task in background thread"""
    try:
        print(f"\n🚀 Starting scraping task - Job ID: {job_id}")
        print(f"📝 Task function: {task_func.__name__}")
        print(f"📋 Task kwargs: {list(task_kwargs.keys())}")

        active_jobs[job_id] = {
            'status': 'running',
            'started_at': datetime.now().isoformat(),
            'progress': 0,
            'current': 0,
            'total': task_kwargs.get('target_dosen', 100),
            'message': 'Starting scraping task...'
        }

        emit_progress(job_id, active_jobs[job_id])

        task_kwargs['job_id'] = job_id
        print(f"🔄 Executing task function...")
        result = task_func(**task_kwargs)

        active_jobs[job_id].update({
            'status': 'completed',
            'completed_at': datetime.now().isoformat(),
            'result': result,
            'message': result.get('message', 'Scraping completed successfully!')
        })

        print(f"✅ Task completed successfully - Job ID: {job_id}")

        emit_progress(job_id, {
            'status': 'completed',
            'message': result.get('message', 'Scraping completed!'),
            'result': result
        })

    except Exception as e:
        error_msg = str(e)
        traceback_msg = traceback.format_exc()

        print(f"\n❌ Task failed - Job ID: {job_id}")
        print(f"Error: {error_msg}")
        print(f"Traceback:\n{traceback_msg}")

        active_jobs[job_id].update({
            'status': 'failed',
            'error': error_msg,
            'traceback': traceback_msg,
            'failed_at': datetime.now().isoformat(),
            'message': f'Scraping failed: {error_msg}'
        })

        emit_progress(job_id, {
            'status': 'failed',
            'error': error_msg,
            'message': f'Scraping failed: {error_msg}'
        })


# ============================================================================
# SINTA ROUTES
# ============================================================================

@scraping_bp.route('/api/scraping/sinta/dosen', methods=['POST', 'OPTIONS'])
@cross_origin(origins=['http://10.211.1.188:3000'], supports_credentials=True)
def scrape_sinta_dosen():
    """Endpoint untuk scraping SINTA Dosen"""
    print("\n" + "="*60)
    print("📥 Received request to /api/scraping/sinta/dosen")
    print("="*60)

    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.get_json()
        print(f"📋 Request data: {data}")

        required_fields = ['username', 'password']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'error': f'Field {field} is required'}), 400

        affiliation_id = data.get('affiliation_id') or '1397'
        max_cycles = int(data.get('max_cycles') or 20)
        max_pages = data.get('max_pages')
        target_dosen = data.get('target_dosen')

        job_id = f"sinta_dosen_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"🆔 Generated job ID: {job_id}")

        active_jobs[job_id] = {
            'status': 'starting',
            'current': 0,
            'total': target_dosen or 0,
            'message': 'Initializing SINTA Dosen scraping...',
            'started_at': datetime.now().isoformat()
        }

        task_kwargs = {
            'username': data['username'],
            'password': data['password'],
            'affiliation_id': affiliation_id,
            'target_dosen': target_dosen,
            'max_pages': max_pages,
            'max_cycles': max_cycles
        }

        thread = threading.Thread(
            target=run_scraping_task,
            args=(job_id, scrape_sinta_dosen_task, task_kwargs)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'message': 'SINTA Dosen scraping started',
            'job_id': job_id
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@scraping_bp.route('/api/scraping/sinta/scopus', methods=['POST'])
def scrape_sinta_scopus():
    try:
        data = request.get_json()
        for field in ['username', 'password']:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'error': f'Field {field} is required'}), 400

        job_id = f"sinta_scopus_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        active_jobs[job_id] = {
            'status': 'starting',
            'message': 'Initializing Scopus scraping...',
            'started_at': datetime.now().isoformat()
        }

        thread = threading.Thread(
            target=run_scraping_task,
            args=(job_id, scrape_sinta_scopus_task, {
                'username': data['username'],
                'password': data['password']
            })
        )
        thread.daemon = True
        thread.start()

        return jsonify({'success': True, 'message': 'Scopus scraping job started', 'job_id': job_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@scraping_bp.route('/api/scraping/sinta/googlescholar', methods=['POST'])
def scrape_sinta_googlescholar():
    try:
        data = request.get_json()
        for field in ['username', 'password']:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'error': f'Field {field} is required'}), 400

        job_id = f"sinta_gs_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        active_jobs[job_id] = {
            'status': 'starting',
            'message': 'Initializing Google Scholar scraping...',
            'started_at': datetime.now().isoformat()
        }

        thread = threading.Thread(
            target=run_scraping_task,
            args=(job_id, scrape_sinta_googlescholar_task, {
                'username': data['username'],
                'password': data['password']
            })
        )
        thread.daemon = True
        thread.start()

        return jsonify({'success': True, 'message': 'Google Scholar scraping job started', 'job_id': job_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@scraping_bp.route('/api/scraping/sinta/garuda', methods=['POST'])
def scrape_sinta_garuda():
    try:
        data = request.get_json()
        for field in ['username', 'password']:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'error': f'Field {field} is required'}), 400

        job_id = f"sinta_garuda_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        active_jobs[job_id] = {
            'status': 'starting',
            'message': 'Initializing Garuda scraping...',
            'started_at': datetime.now().isoformat()
        }

        thread = threading.Thread(
            target=run_scraping_task,
            args=(job_id, scrape_sinta_garuda_task, {
                'username': data['username'],
                'password': data['password']
            })
        )
        thread.daemon = True
        thread.start()

        return jsonify({'success': True, 'message': 'Garuda scraping job started', 'job_id': job_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# CANCEL ENDPOINT
# ============================================================================

@scraping_bp.route('/api/scraping/jobs/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id):
    try:
        job = active_jobs.get(job_id)
        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404

        # Set cancel flag — dibaca oleh gs_scraper.is_cancelled()
        job['cancel_requested'] = True
        job['status'] = 'cancelling'
        job['message'] = 'Menghentikan scraping, mohon tunggu...'

        emit_progress(job_id, job)

        # ── Fallback: force release lock + set cancelled setelah 60 detik ──
        # Jika scraper tidak merespons cancel flag dalam 60 detik,
        # paksa ubah status jadi cancelled dan lepas lock.
        if job_id.startswith('gs_'):
            def delayed_force_cancel():
                import time as _time
                _time.sleep(60)
                current_job = active_jobs.get(job_id, {})
                # Hanya paksa jika masih dalam status cancelling (belum selesai sendiri)
                if current_job.get('status') == 'cancelling':
                    print(f"⚠️ Force cancelling job {job_id} after 60s timeout")
                    active_jobs[job_id].update({
                        'status': 'cancelled',
                        'message': 'Scraping dihentikan paksa.',
                        'cancelled_at': datetime.now().isoformat()
                    })
                    emit_progress(job_id, active_jobs[job_id])
                    # Lepas GS lock jika masih dipegang job ini
                    if _gs_running and _gs_running_job_id == job_id:
                        _gs_release()
                        print(f"🔓 GS lock force-released for cancelled job {job_id}")

            threading.Thread(target=delayed_force_cancel, daemon=True).start()

        return jsonify({'success': True, 'message': 'Cancellation requested', 'job_id': job_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# GOOGLE SCHOLAR — GS PUBLIKASI
# ============================================================================

def run_google_scholar_scraping(job_id, max_authors, scrape_from_beginning):
    """
    Run Google Scholar publikasi scraping in background thread.
    Dilindungi oleh _gs_lock agar hanya 1 instance Chrome berjalan.
    """
    if not _gs_acquire(job_id):
        msg = (f"Tidak dapat memulai: GS scraping job '{_gs_running_job_id}' "
               f"sedang berjalan. Tunggu hingga selesai lalu coba lagi.")
        print(f"⚠️  {msg}")
        active_jobs[job_id].update({
            'status': 'failed',
            'error': msg,
            'message': msg,
            'failed_at': datetime.now().isoformat()
        })
        emit_progress(job_id, active_jobs[job_id])
        return

    try:
        from gs_scraper import GoogleScholarScraper

        active_jobs[job_id].update({
            'status': 'running',
            'current': 0,
            'total': max_authors,
            'message': 'Initializing scraper...',
            'started_at': datetime.now().isoformat()
        })
        emit_progress(job_id, active_jobs[job_id])

        def progress_callback(data):
            active_jobs[job_id].update(data)
            emit_progress(job_id, data)

        scraper = GoogleScholarScraper(
            db_config=DB_CONFIG,
            job_id=job_id,
            progress_callback=progress_callback
        )

        result = scraper.run(
            max_authors=max_authors,
            scrape_from_beginning=scrape_from_beginning
        )

        if result is None:
            result = {
                'success': False,
                'message': 'Scraper returned no result. Check logs for details.',
                'summary': {}
            }

        # ── Cek apakah job dibatalkan ──────────────────────────────────────
        job_cancelled = active_jobs.get(job_id, {}).get('cancel_requested', False)
        summary = result.get('summary', {})
        is_cancelled = job_cancelled or summary.get('cancelled', False)

        if is_cancelled:
            active_jobs[job_id].update({
                'status': 'cancelled',
                'message': result.get('message', 'Scraping dibatalkan oleh user.'),
                'cancelled_at': datetime.now().isoformat(),
                'result': result
            })
            emit_progress(job_id, {
                'status': 'cancelled',
                'message': result.get('message', 'Scraping dibatalkan oleh user.'),
                'summary': summary
            })
        elif result.get('success') is False:
            active_jobs[job_id].update({
                'status': 'failed',
                'message': result.get('error') or result.get('message', 'Scraping gagal'),
                'error': result.get('error', ''),
                'traceback': result.get('traceback', ''),
                'failed_at': datetime.now().isoformat(),
                'result': result
            })
            emit_progress(job_id, {
                'status': 'failed',
                'error': result.get('error', ''),
                'message': result.get('message', 'Scraping gagal')
            })
        else:
            active_jobs[job_id].update({
                'status': 'completed',
                'message': result.get('message', 'Scraping selesai!'),
                'completed_at': datetime.now().isoformat(),
                'result': result
            })
            emit_progress(job_id, {
                'status': 'completed',
                'message': result.get('message', 'Scraping completed'),
                'summary': summary
            })

    except Exception as e:
        error_msg = str(e)
        traceback_msg = traceback.format_exc()

        print(f"\n❌ GS Publikasi ERROR: {error_msg}")
        print(f"Traceback:\n{traceback_msg}")

        active_jobs[job_id].update({
            'status': 'failed',
            'message': error_msg,
            'error': error_msg,
            'traceback': traceback_msg,
            'failed_at': datetime.now().isoformat()
        })
        emit_progress(job_id, {
            'status': 'failed',
            'error': error_msg,
            'traceback': traceback_msg
        })

    finally:
        _gs_release()
        print(f"🔓 GS lock released by job {job_id}")


@scraping_bp.route('/api/scraping/googlescholar/scrape', methods=['POST'])
def scrape_google_scholar():
    """Endpoint untuk scraping publikasi Google Scholar (GS Publikasi)"""
    try:
        data = request.get_json() or {}
        max_authors = data.get('max_authors', 10)
        scrape_from_beginning = data.get('scrape_from_beginning', False)

        if not isinstance(max_authors, int) or max_authors <= 0:
            return jsonify({'success': False, 'error': 'max_authors must be a positive integer'}), 400

        if _gs_running:
            return jsonify({
                'success': False,
                'error': (f"GS scraping job '{_gs_running_job_id}' sedang berjalan. "
                          f"Tunggu hingga selesai lalu coba lagi.")
            }), 409

        job_id = f"gs_scrape_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        active_jobs[job_id] = {
            'status': 'starting',
            'current': 0,
            'total': max_authors,
            'message': 'Initializing Google Scholar scraping...',
            'started_at': datetime.now().isoformat()
        }

        thread = threading.Thread(
            target=run_google_scholar_scraping,
            args=(job_id, max_authors, scrape_from_beginning)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'message': 'Google Scholar scraping started.',
            'job_id': job_id
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


# ============================================================================
# GOOGLE SCHOLAR — GS DOSEN
# ============================================================================

def run_google_scholar_dosen_scraping(job_id, max_pages, search_query):
    """
    Run Google Scholar dosen profile scraping in background thread.
    Dilindungi oleh _gs_lock agar hanya 1 instance Chrome berjalan.
    """
    if not _gs_acquire(job_id):
        msg = (f"Tidak dapat memulai: GS scraping job '{_gs_running_job_id}' "
               f"sedang berjalan. Tunggu hingga selesai lalu coba lagi.")
        print(f"⚠️  {msg}")
        active_jobs[job_id].update({
            'status': 'failed',
            'error': msg,
            'message': msg,
            'failed_at': datetime.now().isoformat()
        })
        emit_progress(job_id, active_jobs[job_id])
        return

    try:
        from gs_scraper import GoogleScholarScraper

        active_jobs[job_id].update({
            'status': 'running',
            'message': 'Initializing Google Scholar Dosen scraper...'
        })
        emit_progress(job_id, active_jobs[job_id])

        max_authors = max_pages

        print(f"\n🔍 GS Dosen scraping started")
        print(f"   max_authors (from max_pages): {max_authors}")
        print(f"   search_query (not used for DB mode): {search_query}")

        def progress_callback(data):
            active_jobs[job_id].update(data)
            emit_progress(job_id, data)

        scraper = GoogleScholarScraper(
            db_config=DB_CONFIG,
            job_id=job_id,
            progress_callback=progress_callback
        )

        result = scraper.run(
            max_authors=max_authors,
            scrape_from_beginning=False
        )

        if result is None:
            result = {
                'success': False,
                'message': 'Scraper returned no result. Check logs for details.',
                'summary': {}
            }

        # ── Cek apakah job dibatalkan ──────────────────────────────────────
        job_cancelled = active_jobs.get(job_id, {}).get('cancel_requested', False)
        summary = result.get('summary', {})
        is_cancelled = job_cancelled or summary.get('cancelled', False)

        if is_cancelled:
            active_jobs[job_id].update({
                'status': 'cancelled',
                'message': result.get('message', 'Scraping dibatalkan oleh user.'),
                'cancelled_at': datetime.now().isoformat(),
                'result': result
            })
            emit_progress(job_id, {
                'status': 'cancelled',
                'message': result.get('message', 'Scraping dibatalkan oleh user.'),
                'summary': summary
            })
        elif result.get('success') is False:
            active_jobs[job_id].update({
                'status': 'failed',
                'message': result.get('error') or result.get('message', 'Scraping gagal'),
                'error': result.get('error', ''),
                'traceback': result.get('traceback', ''),
                'failed_at': datetime.now().isoformat(),
                'result': result
            })
            emit_progress(job_id, {
                'status': 'failed',
                'error': result.get('error', ''),
                'traceback': result.get('traceback', ''),
                'message': result.get('message', 'Scraping gagal')
            })
        else:
            active_jobs[job_id].update({
                'status': 'completed',
                'message': result.get('message', 'Scraping selesai!'),
                'completed_at': datetime.now().isoformat(),
                'result': result
            })
            emit_progress(job_id, {
                'status': 'completed',
                'message': result.get('message', 'Scraping selesai!'),
                'summary': summary
            })

        print(f"✅ GS Dosen scraping completed: {result}")

    except Exception as e:
        error_msg = str(e)
        traceback_msg = traceback.format_exc()

        print(f"\n❌ GS Dosen ERROR: {error_msg}")
        print(f"Traceback:\n{traceback_msg}")

        active_jobs[job_id].update({
            'status': 'failed',
            'message': error_msg,
            'error': error_msg,
            'traceback': traceback_msg,
            'failed_at': datetime.now().isoformat()
        })
        emit_progress(job_id, {
            'status': 'failed',
            'error': error_msg,
            'traceback': traceback_msg,
            'message': f'Scraping gagal: {error_msg}'
        })

    finally:
        _gs_release()
        print(f"🔓 GS lock released by job {job_id}")


@scraping_bp.route('/api/scraping/googlescholar/dosen', methods=['POST'])
def scrape_google_scholar_dosen():
    try:
        data = request.get_json() or {}
        max_pages = data.get('max_pages', 20)
        search_query = data.get(
            'search_query',
            '"Universitas Katolik Parahyangan" OR "Parahyangan Catholic University" OR "unpar"'
        )

        if not isinstance(max_pages, int) or max_pages <= 0:
            return jsonify({'success': False, 'error': 'max_pages must be a positive integer'}), 400

        if max_pages > 500:
            return jsonify({'success': False, 'error': 'max_pages cannot exceed 500'}), 400

        if _gs_running:
            return jsonify({
                'success': False,
                'error': (f"GS scraping job '{_gs_running_job_id}' sedang berjalan. "
                          f"Tunggu hingga selesai lalu coba lagi.")
            }), 409

        job_id = f"gs_dosen_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        active_jobs[job_id] = {
            'status': 'starting',
            'current': 0,
            'total': max_pages,
            'message': 'Initializing Google Scholar dosen scraping...',
            'started_at': datetime.now().isoformat()
        }

        thread = threading.Thread(
            target=run_google_scholar_dosen_scraping,
            args=(job_id, max_pages, search_query)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'message': 'Google Scholar dosen scraping started.',
            'job_id': job_id,
            'max_pages': max_pages,
            'search_query': search_query
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


# ============================================================================
# JOB STATUS ROUTES
# ============================================================================

@scraping_bp.route('/api/scraping/googlescholar/dosen/status/<job_id>', methods=['GET'])
def get_scraping_status(job_id):
    try:
        if job_id not in active_jobs:
            return jsonify({'success': False, 'error': f'Job {job_id} not found'}), 404
        return jsonify({'success': True, 'job_id': job_id, **active_jobs[job_id]}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@scraping_bp.route('/api/scraping/googlescholar/dosen/jobs', methods=['GET'])
def list_scraping_jobs():
    try:
        jobs_list = [{'job_id': jid, **jdata} for jid, jdata in active_jobs.items()]
        jobs_list.sort(key=lambda x: x.get('started_at', ''), reverse=True)
        return jsonify({'success': True, 'jobs': jobs_list, 'total': len(jobs_list)}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@scraping_bp.route('/api/scraping/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id):
    print(f"\n📊 Job status requested for: {job_id}")
    if job_id in active_jobs:
        return jsonify({'success': True, 'job': active_jobs[job_id]}), 200
    return jsonify({'success': False, 'error': 'Job not found'}), 404


@scraping_bp.route('/api/scraping/jobs', methods=['GET'])
def list_jobs():
    return jsonify({'success': True, 'jobs': active_jobs, 'total_jobs': len(active_jobs)}), 200


@scraping_bp.route('/api/scraping/jobs/<job_id>', methods=['DELETE'])
def delete_job(job_id):
    if job_id in active_jobs:
        del active_jobs[job_id]
        return jsonify({'success': True, 'message': f'Job {job_id} deleted'}), 200
    return jsonify({'success': False, 'error': 'Job not found'}), 404


@scraping_bp.route('/api/scraping/health', methods=['GET'])
def scraping_health():
    running_jobs = len([j for j in active_jobs.values() if j.get('status') == 'running'])
    return jsonify({
        'success': True,
        'status': 'healthy',
        'active_jobs_count': running_jobs,
        'total_jobs': len(active_jobs),
        'jobs': list(active_jobs.keys()),
        'gs_scraping_running': _gs_running,
        'gs_running_job_id': _gs_running_job_id
    }), 200


@scraping_bp.route('/api/scraping/googlescholar/reset-lock', methods=['POST'])
def reset_gs_lock():
    """Force-reset GS lock jika job sebelumnya hang/zombie"""
    old_job_id = _gs_running_job_id
    _gs_release()
    if old_job_id and old_job_id in active_jobs:
        active_jobs[old_job_id].update({
            'status': 'cancelled',
            'message': 'Job dihentikan paksa via reset-lock',
            'cancelled_at': datetime.now().isoformat()
        })
        emit_progress(old_job_id, active_jobs[old_job_id])
    return jsonify({
        'success': True,
        'message': f'GS lock reset. Job lama: {old_job_id}'
    }), 200