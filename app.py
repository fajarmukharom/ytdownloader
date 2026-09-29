import os
import re
import uuid
import json
import threading
import subprocess
import shutil
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response, send_from_directory

app = Flask(__name__)

DOWNLOADS_DIR = Path(__file__).parent / 'downloads'
DOWNLOADS_DIR.mkdir(exist_ok=True)

# task_id -> dict with keys: progress, status, done, error, suggestion, filename, filesize
tasks = {}
tasks_lock = threading.Lock()


# ── Custom exception ────────────────────────────────────────────────────────────

class DownloadError(Exception):
    def __init__(self, user_message, suggestion=None, technical_detail=None):
        self.user_message = user_message
        self.suggestion = suggestion
        self.technical_detail = technical_detail
        super().__init__(user_message)


# ── Error maps ──────────────────────────────────────────────────────────────────

PYTUBEFIX_STRING_ERRORS = {
    'Private video':       ("Video ini private.", "Nggak bisa didownload, maaf!"),
    'blocked':             ("Video di-block di region kamu.", "Coba pakai VPN."),
    'is live':             ("Ini live stream yang masih berlangsung.", "Tunggu sampai selesai."),
    'urlopen error':       ("Nggak bisa konek ke internet.", "Cek koneksi kamu dulu."),
    'getaddrinfo failed':  ("Gagal akses YouTube.", "Cek koneksi internet kamu."),
    'No space left':       ("Penyimpanan hampir penuh.", "Hapus beberapa file dulu."),
    'Permission denied':   ("Nggak bisa nulis file.", "Cek permission folder downloads/."),
}


def classify_pytubefix_error(e):
    try:
        from pytubefix import exceptions as ex
        from pytubefix.exceptions import VideoUnavailable, RegexMatchError, AgeRestrictedError
        specific = [
            ('BotDetection', "YouTube mendeteksi request sebagai bot.", "Update pytubefix: pip install -U pytubefix, lalu coba lagi."),
            ('PoTokenRequired', "YouTube minta PO token untuk video ini.", "Update pytubefix: pip install -U pytubefix."),
            ('LoginRequired', "Video ini butuh login.", "Nggak bisa didownload tanpa akun."),
            ('MembersOnly', "Video ini khusus member channel.", "Nggak bisa didownload."),
            ('VideoPrivate', "Video ini private.", "Nggak bisa didownload, maaf!"),
            ('VideoRegionBlocked', "Video di-block di region kamu.", "Coba pakai VPN."),
            ('LiveStreamOffline', "Live stream belum dimulai.", "Coba lagi setelah live-nya mulai."),
            ('LiveStreamError', "Live stream masih berlangsung.", "Tunggu sampai selesai."),
            ('LiveStreamEnded', "Live stream sudah selesai tapi rekamannya belum siap.", "Coba lagi beberapa saat lagi."),
            ('RecordingUnavailable', "Rekaman live ini belum tersedia.", "Coba lagi beberapa saat lagi."),
            ('VideoBlockedByCopyright', "Video di-block karena copyright.", "Nggak bisa didownload."),
        ]
        for name, user_msg, suggestion in specific:
            cls = getattr(ex, name, None)
            if cls and isinstance(e, cls):
                return user_msg, suggestion
        if isinstance(e, AgeRestrictedError):
            return "Video ini dibatasi usia.", "Coba video lain ya."
        if isinstance(e, VideoUnavailable):
            return "Video nggak ditemukan.", "Mungkin sudah dihapus atau di-private."
        if isinstance(e, RegexMatchError):
            return "Gagal memproses video ini.", "YouTube mungkin lagi berubah, coba lagi nanti."
    except ImportError:
        pass

    msg = str(e)
    for key, (user_msg, suggestion) in PYTUBEFIX_STRING_ERRORS.items():
        if key.lower() in msg.lower():
            return user_msg, suggestion

    return None, None


# ── Helpers ─────────────────────────────────────────────────────────────────────

def sanitize_filename(title, max_len=80):
    title = re.sub(r'[^\w\s-]', '', title)
    title = re.sub(r'\s+', '_', title.strip())
    return title[:max_len]


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    i = 1
    while True:
        candidate = path.parent / f"{stem}_({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def parse_timestamp(ts: str) -> int:
    """Convert MM:SS or HH:MM:SS to seconds. Returns -1 if empty."""
    ts = ts.strip()
    if not ts:
        return -1
    parts = ts.split(':')
    if len(parts) == 2:
        m, s = parts
        return int(m) * 60 + int(s)
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + int(s)
    raise ValueError("Bad format")


def seconds_to_ts(secs: int) -> str:
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def check_ffmpeg():
    if not shutil.which('ffmpeg'):
        raise DownloadError("FFmpeg belum terinstall.", "Jalankan install.sh dulu ya.")


def push_progress(task_id, percent, status):
    with tasks_lock:
        if task_id in tasks:
            tasks[task_id]['progress'] = percent
            tasks[task_id]['status'] = status


def push_done(task_id, filename, filesize):
    with tasks_lock:
        if task_id in tasks:
            tasks[task_id]['done'] = True
            tasks[task_id]['filename'] = filename
            tasks[task_id]['filesize'] = filesize


def push_error(task_id, user_message, suggestion=None):
    with tasks_lock:
        if task_id in tasks:
            tasks[task_id]['error'] = user_message
            tasks[task_id]['suggestion'] = suggestion
            tasks[task_id]['done'] = True


# ── Download worker ──────────────────────────────────────────────────────────────

def download_worker(task_id, url, resolution, start_sec, end_sec):
    try:
        from pytubefix import YouTube

        push_progress(task_id, 5, "Mengambil info video...")

        def on_progress(stream, chunk, bytes_remaining):
            total = stream.filesize
            downloaded = total - bytes_remaining
            pct = int(downloaded / total * 60) + 10  # 10-70%
            push_progress(task_id, pct, "Mendownload...")

        yt = YouTube(url, on_progress_callback=on_progress)
        title = sanitize_filename(yt.title)
        duration = yt.length  # seconds

        # Validate timestamps against video duration
        if start_sec >= 0 and duration:
            if start_sec >= duration:
                raise DownloadError(
                    "Waktu yang dimasukkan melebihi durasi video.",
                    f"Durasi video ini cuma {seconds_to_ts(duration)}."
                )
            if end_sec >= 0 and end_sec > duration:
                raise DownloadError(
                    "Waktu yang dimasukkan melebihi durasi video.",
                    f"Durasi video ini cuma {seconds_to_ts(duration)}."
                )

        need_clip = start_sec >= 0 and end_sec > start_sec

        if resolution == 'audio':
            _download_audio(task_id, yt, title, need_clip, start_sec, end_sec)
        elif resolution in ADAPTIVE_RESOLUTIONS:
            _download_adaptive(task_id, yt, title, resolution, need_clip, start_sec, end_sec)
        else:
            _download_progressive(task_id, yt, title, resolution, need_clip, start_sec, end_sec)

    except DownloadError as e:
        app.logger.error(f"[{task_id}] DownloadError: {e.technical_detail or e.user_message}")
        push_error(task_id, e.user_message, e.suggestion)
    except Exception as e:
        user_msg, suggestion = classify_pytubefix_error(e)
        if user_msg:
            push_error(task_id, user_msg, suggestion)
        else:
            app.logger.error(f"[{task_id}] Unexpected {type(e).__name__}: {e}", exc_info=True)
            push_error(task_id, "Waduh, ada yang error nih.", "Coba lagi, atau restart app-nya.")


def _download_progressive(task_id, yt, title, resolution, need_clip, start_sec, end_sec):
    push_progress(task_id, 10, "Mendownload video...")

    stream = yt.streams.filter(progressive=True, file_extension='mp4', res=resolution).first()
    if not stream:
        # Progressive stream nggak ada, pakai adaptive path (butuh FFmpeg merge)
        _download_adaptive(task_id, yt, title, resolution, need_clip, start_sec, end_sec)
        return

    if need_clip:
        tmp_path = unique_path(DOWNLOADS_DIR / f"_tmp_{title}.mp4")
        stream.download(output_path=str(DOWNLOADS_DIR), filename=tmp_path.name)
        push_progress(task_id, 75, "Memotong video...")
        start_ts = seconds_to_ts(start_sec)
        end_ts = seconds_to_ts(end_sec)
        out_name = f"{title}_clip_{start_ts.replace(':', '')}-{end_ts.replace(':', '')}.mp4"
        out_path = unique_path(DOWNLOADS_DIR / out_name)
        _ffmpeg_crop(tmp_path, out_path, start_ts, end_ts)
        tmp_path.unlink(missing_ok=True)
    else:
        out_path = unique_path(DOWNLOADS_DIR / f"{title}.mp4")
        stream.download(output_path=str(DOWNLOADS_DIR), filename=out_path.name)

    _finish(task_id, out_path)


def _download_adaptive(task_id, yt, title, resolution, need_clip, start_sec, end_sec):
    check_ffmpeg()
    label = RESOLUTION_LABELS.get(resolution, (resolution, ''))[0]
    push_progress(task_id, 10, f"Mendownload video ({label})...")

    video_stream = yt.streams.filter(adaptive=True, file_extension='mp4', only_video=True, res=resolution).first()
    if not video_stream:
        video_stream = yt.streams.filter(adaptive=True, file_extension='mp4', only_video=True).order_by('resolution').desc().first()
    if not video_stream:
        raise DownloadError("Resolusi ini nggak tersedia untuk video ini.", "Coba pilih resolusi yang lain.")

    audio_stream = yt.streams.filter(adaptive=True, only_audio=True).order_by('abr').desc().first()
    if not audio_stream:
        raise DownloadError("Stream audio nggak ditemukan.", "Coba resolusi lain.")

    def on_video_progress(stream, chunk, bytes_remaining):
        total = stream.filesize
        pct = int((total - bytes_remaining) / total * 30) + 10  # 10-40%
        push_progress(task_id, pct, "Mendownload video...")

    def on_audio_progress(stream, chunk, bytes_remaining):
        total = stream.filesize
        pct = int((total - bytes_remaining) / total * 25) + 40  # 40-65%
        push_progress(task_id, pct, "Mendownload audio...")

    yt.register_on_progress_callback(on_video_progress)
    vid_tmp = unique_path(DOWNLOADS_DIR / f"_vid_{title}.mp4")
    video_stream.download(output_path=str(DOWNLOADS_DIR), filename=vid_tmp.name)

    yt.register_on_progress_callback(on_audio_progress)
    aud_tmp = unique_path(DOWNLOADS_DIR / f"_aud_{title}.webm")
    audio_stream.download(output_path=str(DOWNLOADS_DIR), filename=aud_tmp.name)

    push_progress(task_id, 70, "Menggabungkan audio & video...")
    check_ffmpeg()

    if need_clip:
        merged_tmp = unique_path(DOWNLOADS_DIR / f"_merged_{title}.mp4")
        _ffmpeg_merge(vid_tmp, aud_tmp, merged_tmp)
        vid_tmp.unlink(missing_ok=True)
        aud_tmp.unlink(missing_ok=True)
        push_progress(task_id, 85, "Memotong video...")
        start_ts = seconds_to_ts(start_sec)
        end_ts = seconds_to_ts(end_sec)
        out_name = f"{title}_clip_{start_ts.replace(':', '')}-{end_ts.replace(':', '')}.mp4"
        out_path = unique_path(DOWNLOADS_DIR / out_name)
        _ffmpeg_crop(merged_tmp, out_path, start_ts, end_ts)
        merged_tmp.unlink(missing_ok=True)
    else:
        out_path = unique_path(DOWNLOADS_DIR / f"{title}.mp4")
        _ffmpeg_merge(vid_tmp, aud_tmp, out_path)
        vid_tmp.unlink(missing_ok=True)
        aud_tmp.unlink(missing_ok=True)

    _finish(task_id, out_path)


def _download_audio(task_id, yt, title, need_clip, start_sec, end_sec):
    check_ffmpeg()
    push_progress(task_id, 10, "Mendownload audio...")

    audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
    if not audio_stream:
        raise DownloadError("Stream audio nggak ditemukan.", "Coba video lain.")

    aud_tmp = unique_path(DOWNLOADS_DIR / f"_aud_{title}.webm")
    audio_stream.download(output_path=str(DOWNLOADS_DIR), filename=aud_tmp.name)

    push_progress(task_id, 70, "Mengkonversi ke MP3...")
    check_ffmpeg()

    if need_clip:
        start_ts = seconds_to_ts(start_sec)
        end_ts = seconds_to_ts(end_sec)
        out_name = f"{title}_clip_{start_ts.replace(':', '')}-{end_ts.replace(':', '')}.mp3"
        out_path = unique_path(DOWNLOADS_DIR / out_name)
        _ffmpeg_to_mp3_clip(aud_tmp, out_path, start_ts, end_ts)
    else:
        out_path = unique_path(DOWNLOADS_DIR / f"{title}.mp3")
        _ffmpeg_to_mp3(aud_tmp, out_path)

    aud_tmp.unlink(missing_ok=True)
    _finish(task_id, out_path)


def _ffmpeg_merge(video: Path, audio: Path, output: Path):
    result = subprocess.run(
        ['ffmpeg', '-y', '-i', str(video), '-i', str(audio),
         '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental', str(output)],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not output.exists() or output.stat().st_size == 0:
        app.logger.error(f"FFmpeg merge failed: {result.stderr}")
        raise DownloadError("Gagal menggabungkan video dan audio.", "Pastikan FFmpeg terinstall.")


def _ffmpeg_crop(inp: Path, output: Path, start_ts: str, end_ts: str):
    result = subprocess.run(
        ['ffmpeg', '-y', '-i', str(inp),
         '-ss', start_ts, '-to', end_ts,
         '-c:v', 'libx264', '-c:a', 'aac', str(output)],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not output.exists() or output.stat().st_size == 0:
        app.logger.error(f"FFmpeg crop failed: {result.stderr}")
        raise DownloadError("Gagal memotong video.", "Cek lagi timestamp-nya.")


def _ffmpeg_to_mp3(inp: Path, output: Path):
    result = subprocess.run(
        ['ffmpeg', '-y', '-i', str(inp), '-vn', '-acodec', 'libmp3lame', '-q:a', '2', str(output)],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not output.exists() or output.stat().st_size == 0:
        app.logger.error(f"FFmpeg mp3 failed: {result.stderr}")
        raise DownloadError("Gagal convert ke MP3.", "Pastikan FFmpeg terinstall.")


def _ffmpeg_to_mp3_clip(inp: Path, output: Path, start_ts: str, end_ts: str):
    result = subprocess.run(
        ['ffmpeg', '-y', '-i', str(inp),
         '-ss', start_ts, '-to', end_ts,
         '-vn', '-acodec', 'libmp3lame', '-q:a', '2', str(output)],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not output.exists() or output.stat().st_size == 0:
        app.logger.error(f"FFmpeg mp3 clip failed: {result.stderr}")
        raise DownloadError("Gagal convert ke MP3.", "Pastikan FFmpeg terinstall.")


def _finish(task_id, out_path: Path):
    push_progress(task_id, 100, "Selesai!")
    size = out_path.stat().st_size if out_path.exists() else 0
    if size == 0:
        raise DownloadError("File hasil download rusak.", "Coba download ulang.")
    size_str = _fmt_size(size)
    push_done(task_id, out_path.name, size_str)


def _fmt_size(size: int) -> str:
    for unit in ('B', 'KB', 'MB', 'GB'):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


# ── Validation ───────────────────────────────────────────────────────────────────

YOUTUBE_RE = re.compile(
    r'^(https?://)?(www\.)?(youtube\.com/(watch\?.*v=|shorts/)|youtu\.be/)'
)

ADAPTIVE_RESOLUTIONS = {'1080p', '1440p', '2160p', '4320p'}

RESOLUTION_LABELS = {
    '360p':  ('360p', 'SD'),
    '480p':  ('480p', 'SD+'),
    '720p':  ('720p', 'HD'),
    '1080p': ('1080p', 'FHD'),
    '1440p': ('1440p', '2K'),
    '2160p': ('2160p', '4K'),
    '4320p': ('4320p', '8K'),
    'audio': ('MP3', 'Audio only'),
}


def validate_input(url, resolution, start_raw, end_raw):
    url = url.strip()
    if not url:
        raise DownloadError("Masukkan URL YouTube dulu ya.")
    if not YOUTUBE_RE.match(url):
        raise DownloadError("URL-nya kayaknya bukan dari YouTube.", "Coba cek lagi URL-nya.")
    if 'list=' in url and 'v=' not in url:
        raise DownloadError("Ini URL playlist.", "Saat ini cuma support single video ya.")
    if resolution not in {*ADAPTIVE_RESOLUTIONS, '360p', '480p', '720p', 'audio'}:
        raise DownloadError("Format nggak valid.", "Pilih salah satu format yang tersedia.")

    start_sec = -1
    end_sec = -1
    try:
        start_sec = parse_timestamp(start_raw)
        end_sec = parse_timestamp(end_raw)
    except (ValueError, AttributeError):
        raise DownloadError("Format waktu salah.", "Pakai format MM:SS atau HH:MM:SS.")

    if start_sec >= 0 and end_sec >= 0:
        if end_sec <= start_sec:
            raise DownloadError("Waktu akhir harus lebih besar dari waktu mulai dong.")

    return url, start_sec, end_sec


# ── Routes ───────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/info', methods=['POST'])
def get_info():
    data = request.get_json()
    url = (data.get('url') or '').strip()

    if not url:
        return jsonify({'error': 'Masukkan URL YouTube dulu ya.'}), 400
    if not YOUTUBE_RE.match(url):
        return jsonify({'error': 'URL-nya kayaknya bukan dari YouTube.', 'suggestion': 'Coba cek lagi URL-nya.'}), 400
    if 'list=' in url and 'v=' not in url:
        return jsonify({'error': 'Ini URL playlist.', 'suggestion': 'Saat ini cuma support single video ya.'}), 400

    try:
        from pytubefix import YouTube
        yt = YouTube(url)

        available = []

        for res in ['360p', '480p', '720p', '1080p', '1440p', '2160p', '4320p']:
            progressive = yt.streams.filter(progressive=True, file_extension='mp4', res=res).first()
            adaptive    = yt.streams.filter(adaptive=True, file_extension='mp4', only_video=True, res=res).first()
            if progressive or adaptive:
                available.append(res)

        if yt.streams.filter(only_audio=True).first():
            available.append('audio')

        duration = yt.length or 0
        return jsonify({
            'title': yt.title,
            'thumbnail': yt.thumbnail_url,
            'duration': duration,
            'duration_str': seconds_to_ts(duration) if duration else '??:??',
            'resolutions': available,
        })

    except Exception as e:
        user_msg, suggestion = classify_pytubefix_error(e)
        if user_msg:
            return jsonify({'error': user_msg, 'suggestion': suggestion}), 400
        app.logger.error(f"Info fetch error: {e}", exc_info=True)
        return jsonify({'error': 'Gagal mengambil info video.', 'suggestion': 'Coba lagi.'}), 500


@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    url = data.get('url', '')
    resolution = data.get('resolution', '720p')
    start_raw = data.get('start', '')
    end_raw = data.get('end', '')

    try:
        url, start_sec, end_sec = validate_input(url, resolution, start_raw, end_raw)
    except DownloadError as e:
        return jsonify({'error': e.user_message, 'suggestion': e.suggestion}), 400

    task_id = str(uuid.uuid4())
    with tasks_lock:
        tasks[task_id] = {
            'progress': 0, 'status': 'Memulai...', 'done': False,
            'error': None, 'suggestion': None, 'filename': None, 'filesize': None
        }

    t = threading.Thread(
        target=download_worker,
        args=(task_id, url, resolution, start_sec, end_sec),
        daemon=True
    )
    t.start()

    return jsonify({'task_id': task_id})


@app.route('/progress/<task_id>')
def progress(task_id):
    def stream():
        import time
        while True:
            with tasks_lock:
                task = tasks.get(task_id)
            if task is None:
                yield f"data: {json.dumps({'error': 'Task tidak ditemukan.'})}\n\n"
                break

            payload = {
                'progress': task['progress'],
                'status': task['status'],
            }
            if task['error']:
                payload['error'] = task['error']
                payload['suggestion'] = task['suggestion']
                yield f"data: {json.dumps(payload)}\n\n"
                break
            if task['done'] and task['filename']:
                payload['done'] = True
                payload['filename'] = task['filename']
                payload['filesize'] = task['filesize']
                payload['download_url'] = f"/files/{task['filename']}"
                yield f"data: {json.dumps(payload)}\n\n"
                break

            yield f"data: {json.dumps(payload)}\n\n"
            time.sleep(0.5)

    return Response(stream(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/files')
def list_files():
    files = []
    for f in sorted(DOWNLOADS_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file() and not f.name.startswith('_'):
            files.append({
                'name': f.name,
                'size': _fmt_size(f.stat().st_size),
                'url': f'/files/{f.name}'
            })
    return jsonify(files)


@app.route('/files/<path:filename>')
def serve_file(filename):
    return send_from_directory(str(DOWNLOADS_DIR), filename, as_attachment=True)


@app.route('/files/<path:filename>', methods=['DELETE'])
def delete_file(filename):
    target = DOWNLOADS_DIR / filename
    if target.exists() and target.parent == DOWNLOADS_DIR:
        target.unlink()
        return jsonify({'ok': True})
    return jsonify({'error': 'File tidak ditemukan.'}), 404


@app.errorhandler(Exception)
def handle_error(e):
    if isinstance(e, DownloadError):
        return jsonify({'error': e.user_message, 'suggestion': e.suggestion}), 400
    app.logger.error(f"Unexpected error: {e}", exc_info=True)
    return jsonify({'error': 'Waduh, ada yang error nih.', 'suggestion': 'Coba lagi, atau restart app-nya.'}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8421, threaded=True)
