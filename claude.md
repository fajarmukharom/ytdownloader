# YouTube Downloader — Project Brief (claude.md)

## Overview

A locally-run YouTube downloader with a simple web UI.
No AI, no external API, no subscription. 100% free & offline-capable.

Built with: **Python 3 + Flask + pytubefix + FFmpeg**
Target OS: **macOS**

---

## File Structure

```
pytube/
├── claude.md        # This file — project brief & spec
├── app.py           # Flask backend + download logic
├── install.sh       # One-time setup script (macOS)
├── run.sh           # Daily runner script (macOS)
├── downloads/       # Output folder (auto-created)
└── templates/
    └── index.html   # Web UI (Jinja2 template)
```

---

## Core Features

### 1. Paste & Download
- User paste YouTube URL di input field
- Klik download → file tersimpan di folder `downloads/`

### 2. Timestamp Clipping (opsional)
- Input start time & end time (format: `MM:SS` atau `HH:MM:SS`)
- Kalau dikosongkan → download full video
- Kalau diisi → download full dulu, lalu crop pakai FFmpeg
- Validasi: end harus > start, format harus benar

### 3. Pilih Resolusi / Format
- 360p (progressive — cepat, kecil)
- 720p (progressive — balanced, audio+video satu file)
- 1080p (adaptive — download video+audio terpisah, merge pakai FFmpeg)
- Audio Only — MP3 (extract audio, convert pakai FFmpeg)

### 4. Download Progress
- Tampilkan progress bar real-time (pakai on_progress_callback)
- Status text: "Mendownload video...", "Mendownload audio...", "Menggabungkan...", "Memotong...", "Selesai!"
- Kalau error → pesan manusiawi (lihat Error Handling section)

---

## Tech Stack & Dependencies

| Package      | Fungsi                                       | Install via |
|------------- |----------------------------------------------|-------------|
| Python 3.8+  | Runtime                                      | Pre-installed / manual |
| Flask        | Web server + routing                         | pip         |
| pytubefix    | YouTube download engine                      | pip         |
| FFmpeg       | Merge adaptive streams, crop, convert to MP3 | Homebrew    |

### Kenapa pytubefix, bukan yt-dlp?
yt-dlp saat ini terkena YouTube SABR streaming enforcement (lihat: github.com/yt-dlp/yt-dlp/issues/12482).
Akibatnya yt-dlp hanya bisa download format 360p (itag 18) — format lain URL-nya di-block.
pytubefix menangani ini lebih baik dan aktif di-maintain.

---

## app.py — Backend Spec

### Routes

| Route                  | Method | Fungsi                                         |
|------------------------|--------|------------------------------------------------|
| `/`                    | GET    | Render halaman utama (index.html)              |
| `/download`            | POST   | Terima URL + options, jalankan download         |
| `/progress/<task_id>`  | GET    | SSE stream untuk progress real-time             |
| `/files`               | GET    | List file yang sudah didownload                 |
| `/files/<filename>`    | GET    | Serve file untuk download ke browser            |

### Download Flow (POST /download)

```
1. Validasi input (URL, timestamp, resolusi)
2. Generate task_id (uuid4)
3. Spawn background thread untuk download
4. Return task_id ke frontend
5. Frontend subscribe ke SSE `/progress/<task_id>`
6. Backend push progress events: percentage, status text
7. Selesai → push event "done" dengan filename + download link
```

### pytubefix Usage Patterns

```python
from pytubefix import YouTube
from pytubefix.cli import on_progress

yt = YouTube(url, on_progress_callback=on_progress)

# === PROGRESSIVE (360p, 720p) — single file, audio+video included ===
# Langsung download, ga perlu merge
stream = yt.streams.filter(
    progressive=True,
    file_extension='mp4',
    res='720p'
).first()

# Fallback: kalau resolusi spesifik ga ada
if not stream:
    stream = yt.streams.get_highest_resolution()

stream.download(output_path='downloads/')


# === ADAPTIVE (1080p) — video & audio terpisah, perlu merge ===
video_stream = yt.streams.filter(
    adaptive=True,
    file_extension='mp4',
    only_video=True,
    res='1080p'
).first()

audio_stream = yt.streams.filter(
    adaptive=True,
    only_audio=True
).order_by('abr').desc().first()

# Download keduanya ke temp files
video_path = video_stream.download(output_path='downloads/', filename_prefix='video_')
audio_path = audio_stream.download(output_path='downloads/', filename_prefix='audio_')

# Merge pakai FFmpeg
# ffmpeg -i video.mp4 -i audio.webm -c:v copy -c:a aac -strict experimental output.mp4
# Hapus temp files setelah merge


# === AUDIO ONLY (MP3) ===
audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
audio_path = audio_stream.download(output_path='downloads/')

# Convert ke MP3 pakai FFmpeg
# ffmpeg -i audio.webm -vn -acodec libmp3lame -q:a 2 output.mp3
# Hapus source file setelah convert
```

### Timestamp Crop (FFmpeg post-processing)

pytubefix TIDAK support download by timestamp.
Strategy: download full video dulu, lalu crop pakai FFmpeg.

```bash
# Crop tanpa re-encode (cepat, tapi bisa kurang presisi di keyframe)
ffmpeg -i input.mp4 -ss 00:01:30 -to 00:03:00 -c copy -avoid_negative_ts make_zero output.mp4

# Crop dengan re-encode (lebih lambat, tapi presisi frame-accurate)
ffmpeg -i input.mp4 -ss 00:01:30 -to 00:03:00 -c:v libx264 -c:a aac output.mp4
```

Gunakan versi **re-encode** sebagai default agar hasilnya presisi.
Hapus file full-video setelah crop selesai.

### File Naming
- Default: `{sanitized_video_title}.{ext}`
- Sanitize: hapus karakter special, replace spasi dengan underscore, limit 80 chars
- Kalau ada timestamp: `{title}_clip_{start}-{end}.{ext}`
- Kalau duplikat: tambah `_(1)`, `_(2)`, dst.

---

## templates/index.html — Frontend Spec

### Layout
- Single page, centered, max-width 600px
- Clean & minimal — pure HTML/CSS/JS, no framework
- Mobile responsive

### Components

1. **Header**
   - Title: "YouTube Downloader"
   - Subtitle: "Download & crop video YouTube langsung dari browser"

2. **URL Input**
   - Text field, placeholder: "Paste URL YouTube di sini..."
   - Auto-detect: kalau bukan YouTube URL, tampilkan warning inline

3. **Timestamp Section** (collapsible, default hidden)
   - Toggle: "Mau potong bagian tertentu?"
   - Start time input (placeholder: `00:00`)
   - End time input (placeholder: `00:00`)
   - Helper text: "Kosongkan untuk download full video"
   - Validasi real-time: format check, end > start

4. **Format Selector** (radio buttons)
   - 🎬 360p — Cepat & hemat storage
   - 🎬 720p — Kualitas bagus (recommended)
   - 🎬 1080p — Kualitas terbaik (butuh waktu lebih)
   - 🎵 Audio only (MP3)

5. **Download Button**
   - Text: "Mulai Download"
   - Disabled saat proses berjalan
   - Berubah jadi "Sedang memproses..." saat aktif

6. **Progress Area**
   - Progress bar (0-100%)
   - Status text: stage-aware
   - Error message: merah, friendly, dengan saran aksi

7. **Result Area** (muncul setelah selesai)
   - Filename + file size
   - Button: "Download File" → trigger browser download
   - Button: "Download Lagi" → reset form

8. **Download History** (bottom section)
   - List file yang sudah didownload
   - Klik untuk download ulang
   - Tombol hapus per-file (opsional)

### UX Details
- Enter key = submit
- Paste event detection: auto-focus ke URL field
- Smooth transitions antar state (idle → processing → done → error)
- No page reload — semua via fetch + SSE

---

## Error Handling — COMPREHENSIVE

### Prinsip Utama
1. **JANGAN** tampilkan raw Python error / stack trace ke user
2. **SEMUA** error punya pesan Bahasa Indonesia, casual, non-teknis
3. **SEMUA** error di-catch di level tertinggi (global handler)
4. **LOG** detail teknis ke terminal untuk debugging
5. **SETIAP** error message kasih saran aksi ke user

### Custom Error Class

```python
class DownloadError(Exception):
    def __init__(self, user_message, suggestion=None, technical_detail=None):
        self.user_message = user_message
        self.suggestion = suggestion  # Saran aksi untuk user
        self.technical_detail = technical_detail  # Untuk logging
```

### Error Messages — Input Validation

| Kondisi                | Pesan                                                          | Saran                                    |
|------------------------|----------------------------------------------------------------|------------------------------------------|
| URL kosong             | "Masukkan URL YouTube dulu ya."                                | —                                        |
| URL bukan YouTube      | "URL-nya kayaknya bukan dari YouTube."                         | "Coba cek lagi URL-nya."                 |
| URL format salah       | "Format URL-nya nggak valid."                                  | "Paste ulang langsung dari browser ya."  |
| Timestamp format salah | "Format waktu salah."                                          | "Pakai format MM:SS atau HH:MM:SS."     |
| Timestamp end ≤ start  | "Waktu akhir harus lebih besar dari waktu mulai dong."         | —                                        |
| Timestamp > durasi     | "Waktu yang dimasukkan melebihi durasi video."                 | "Durasi video ini cuma {duration}."      |

### Error Messages — Download Errors

| Kondisi                    | Pesan                                                          | Saran                                       |
|----------------------------|----------------------------------------------------------------|---------------------------------------------|
| Video private              | "Video ini private."                                           | "Nggak bisa didownload, maaf!"              |
| Video dihapus              | "Video nggak ditemukan."                                       | "Mungkin sudah dihapus."                    |
| Video age-restricted       | "Video ini dibatasi usia."                                     | "Coba video lain ya."                       |
| Video region-blocked       | "Video di-block di region kamu."                               | "Coba pakai VPN."                           |
| Live stream                | "Ini live stream yang masih berlangsung."                      | "Tunggu sampai selesai baru bisa download." |
| Resolusi tidak tersedia    | "Resolusi ini nggak tersedia untuk video ini."                 | "Coba pilih resolusi yang lain."            |
| Playlist URL               | "Ini URL playlist."                                            | "Saat ini cuma support single video ya."    |
| Download timeout           | "Download kelamaan."                                           | "Kemungkinan koneksi lagi lambat."          |

### Error Messages — System / Environment

| Kondisi                    | Pesan                                                          | Saran                                        |
|----------------------------|----------------------------------------------------------------|----------------------------------------------|
| FFmpeg tidak ditemukan     | "FFmpeg belum terinstall."                                     | "Jalankan install.sh dulu ya."               |
| Koneksi internet mati      | "Nggak bisa konek ke internet."                                | "Cek koneksi kamu dulu."                     |
| DNS gagal resolve          | "Gagal akses YouTube."                                         | "Cek koneksi internet kamu."                 |
| Disk penuh                 | "Penyimpanan hampir penuh."                                    | "Hapus beberapa file dulu."                  |
| Permission denied          | "Nggak bisa nulis file."                                       | "Cek permission folder downloads/."          |
| Port sudah dipakai         | "Port 5000 sudah dipakai app lain."                            | "Tutup app lain di port itu dulu."           |

### Error Messages — Post-processing (FFmpeg)

| Kondisi                    | Pesan                                                          | Saran                                        |
|----------------------------|----------------------------------------------------------------|----------------------------------------------|
| Merge video+audio gagal    | "Gagal menggabungkan video dan audio."                         | "Pastikan FFmpeg terinstall."                |
| Convert ke MP3 gagal       | "Gagal convert ke MP3."                                        | "Pastikan FFmpeg terinstall."                |
| Crop gagal                 | "Gagal memotong video."                                        | "Cek lagi timestamp-nya."                    |
| Output 0 bytes / corrupt   | "File hasil download rusak."                                   | "Coba download ulang."                       |

### Catch-All

| Kondisi               | Pesan                                                              | Saran                       |
|------------------------|--------------------------------------------------------------------|-----------------------------|
| Error tidak dikenal    | "Waduh, ada yang error nih."                                       | "Coba lagi, atau restart app-nya." |

### Error Detection — pytubefix exceptions

```python
from pytubefix.exceptions import (
    VideoUnavailable,
    RegexMatchError,
    AgeRestrictedError,
)

PYTUBEFIX_ERROR_MAP = {
    VideoUnavailable:   ("Video nggak ditemukan.", "Mungkin sudah dihapus atau di-private."),
    AgeRestrictedError: ("Video ini dibatasi usia.", "Coba video lain ya."),
    RegexMatchError:    ("Gagal memproses video ini.", "YouTube mungkin lagi berubah, coba lagi nanti."),
}

# Fallback string matching untuk error yang nggak punya exception class
PYTUBEFIX_STRING_ERRORS = {
    'Private video':      ("Video ini private.", "Nggak bisa didownload, maaf!"),
    'blocked':            ("Video di-block di region kamu.", "Coba pakai VPN."),
    'is live':            ("Ini live stream yang masih berlangsung.", "Tunggu sampai selesai."),
    'urlopen error':      ("Nggak bisa konek ke internet.", "Cek koneksi kamu dulu."),
    'getaddrinfo failed': ("Gagal akses YouTube.", "Cek koneksi internet kamu."),
    'No space left':      ("Penyimpanan hampir penuh.", "Hapus beberapa file dulu."),
    'Permission denied':  ("Nggak bisa nulis file.", "Cek permission folder downloads/."),
}
```

### Global Error Handler

```python
@app.errorhandler(Exception)
def handle_error(e):
    if isinstance(e, DownloadError):
        return jsonify({
            'error': e.user_message,
            'suggestion': e.suggestion
        }), 400
    
    # Log technical detail ke terminal
    app.logger.error(f"Unexpected error: {str(e)}", exc_info=True)
    
    return jsonify({
        'error': 'Waduh, ada yang error nih.',
        'suggestion': 'Coba lagi, atau restart app-nya.'
    }), 500
```

---

## install.sh — Spec (macOS)

### Flow
```
========================================
  YouTube Downloader — Installer
========================================

[1/6] ⏳ Mengecek Python 3...          ✅ Python 3.x.x ditemukan
[2/6] ⏳ Mengecek Homebrew...           ✅ Homebrew sudah terinstall
[3/6] ⏳ Menginstall FFmpeg...          ✅ FFmpeg terinstall
[4/6] ⏳ Menginstall pytubefix...       ✅ pytubefix terinstall
[5/6] ⏳ Menginstall Flask...           ✅ Flask terinstall
[6/6] ⏳ Menyiapkan folder downloads... ✅ Folder siap

========================================
✅ Instalasi selesai!
   Jalankan ./run.sh untuk mulai.
========================================
```

### Error Messages (Terminal)

| Step gagal              | Pesan                                                               |
|-------------------------|---------------------------------------------------------------------|
| Python tidak ada        | "❌ Python 3 belum terinstall. Install dulu di python.org/downloads" |
| Homebrew gagal install  | "❌ Gagal install Homebrew. Coba install manual di brew.sh"          |
| FFmpeg gagal install    | "❌ Gagal install FFmpeg. Coba manual: brew install ffmpeg"          |
| pip gagal               | "❌ Gagal install Python packages. Coba: pip3 install pytubefix flask" |
| Semua sudah ada         | "ℹ️  Semua sudah terinstall! Langsung jalankan ./run.sh aja."        |

### Script Details
- Setiap step: cek dulu apakah sudah terinstall → skip kalau sudah
- Warna terminal: hijau (✅), merah (❌), kuning (⚠️), biru (ℹ️)
- Kalau satu step gagal → hentikan proses, jangan lanjut ke step berikutnya
- chmod +x run.sh otomatis di akhir

---

## run.sh — Spec (macOS)

### Flow
```
1. Cek app.py ada di folder yang sama
2. Cek dependencies (python3, pytubefix, flask, ffmpeg)
3. Buat folder downloads/ kalau belum ada
4. Jalankan: python3 app.py
5. Tunggu 2 detik
6. Auto buka browser: open http://localhost:5000
7. Print:
   ✅ App running di http://localhost:5000
   Tekan Ctrl+C untuk stop.
```

### Error Messages (Terminal)

| Kondisi               | Pesan                                                                   |
|-----------------------|-------------------------------------------------------------------------|
| app.py tidak ditemukan | "❌ File app.py nggak ketemu. Pastikan kamu di folder yang benar."       |
| Python not found      | "❌ Python 3 nggak ketemu. Jalankan install.sh dulu."                    |
| Dependencies missing  | "❌ Ada dependency yang belum terinstall. Jalankan install.sh dulu."     |
| Port 5000 dipakai     | "❌ Port 5000 sudah dipakai. Tutup app lain di port itu dulu."          |

---

## UI Design Notes

### Aesthetic
- Dark theme (#1a1a2e background, #16213e cards)
- Font: system stack (-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif)
- Accent: merah YouTube (#FF0000) untuk button utama, atau custom warm color
- Border radius: 8px (inputs), 12px (cards)
- Subtle box-shadow pada card utama
- Compact — semua muat di 1 screen tanpa scroll

### Bahasa UI
- Full Bahasa Indonesia, casual
- Button: "Mulai Download", "Download File", "Download Lagi"
- Placeholder: "Paste URL YouTube di sini..."
- Toggle: "Mau potong bagian tertentu?"
- Status: "Mendownload...", "Menggabungkan audio & video...", "Memotong video...", "Selesai!"
- Error: friendly, nggak teknis, kasih saran aksi

---

## Limitations (Documented)

- Hanya support YouTube (bukan Instagram, TikTok, dll)
- Single video only (bukan playlist)
- Progressive stream max 720p; 1080p butuh FFmpeg merge (otomatis)
- Timestamp crop download full dulu baru potong (bukan partial download)
- Perlu internet untuk download
- macOS only (saat ini)

---

## Future Ideas (Out of Scope)

- [ ] Support platform lain (Instagram, TikTok)
- [ ] Batch download / playlist support
- [ ] Windows & Linux support
- [ ] Electron / Tauri wrapper (no terminal needed)
- [ ] Auto-update pytubefix
- [ ] Drag & drop URL
- [ ] Preview thumbnail sebelum download
- [ ] OAuth support untuk private/age-restricted videos
