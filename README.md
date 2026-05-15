# YouTube Downloader

Aplikasi web sederhana untuk download video YouTube langsung dari browser.
Gratis, offline-capable, dan tanpa langganan apapun.

**Fitur:**
- Download video 360p, 480p, 720p, 1080p, 2K, 4K (sesuai yang tersedia di video)
- Download audio saja dalam format MP3
- Potong video berdasarkan timestamp (clip)
- Progress bar real-time
- Riwayat file yang sudah didownload

---

## Persyaratan

Sebelum mulai, pastikan kamu punya:

- **macOS** (aplikasi ini didesain untuk macOS)
- **Python 3.8 ke atas** — cek dengan menjalankan `python3 --version` di Terminal
- **Koneksi internet** — untuk download video dari YouTube

Kalau Python belum terinstall, download di [python.org/downloads](https://www.python.org/downloads/)

---

## Cara Install

### Langkah 1 — Buka Terminal

Tekan `Command + Space`, ketik **Terminal**, lalu tekan Enter.

### Langkah 2 — Masuk ke folder project

Setelah Terminal terbuka, kamu perlu pindah ke folder tempat project ini berada.
Jalankan perintah berikut (sesuaikan dengan lokasi folder kamu):

```bash
cd ~/Downloads/ytdownloader
```

> Kalau kamu menyimpan di lokasi lain, sesuaikan path-nya.
> Contoh: kalau ada di Desktop → `cd ~/Desktop/ytdownloader`
>
> Cara cek lokasi folder yang benar: buka Finder, cari folder `ytdownloader`,
> lalu drag & drop folder itu ke jendela Terminal — path-nya akan otomatis terisi.

### Langkah 3 — Jalankan installer

```bash
./install.sh
```

Script ini akan otomatis menginstall semua yang dibutuhkan:
- Homebrew (package manager untuk macOS)
- FFmpeg (untuk proses merge & convert video)
- pytubefix (untuk download dari YouTube)
- Flask (web server)

Tunggu sampai muncul pesan:

```
✅ Instalasi selesai!
   Jalankan ./run.sh untuk mulai.
```

> Proses install bisa memakan waktu beberapa menit tergantung koneksi internet,
> terutama saat menginstall FFmpeg.

---

## Cara Pakai

### Langkah 1 — Jalankan aplikasi

Pastikan Terminal masih di folder `ytdownloader`, lalu jalankan:

```bash
./run.sh
```

Browser kamu akan otomatis terbuka dan menampilkan halaman aplikasi.
Kalau tidak terbuka otomatis, buka browser dan ketik: `http://localhost:8421`

### Langkah 2 — Paste URL video

Salin URL video YouTube yang ingin didownload dari browser, lalu paste di kolom input.

Aplikasi akan otomatis mengambil info video (judul, durasi, resolusi yang tersedia).

### Langkah 3 — Pilih format

Setelah info video muncul, pilih resolusi atau format yang diinginkan:
- **360p / 480p / 720p** — video standar, proses cepat
- **1080p / 2K / 4K** — kualitas tinggi, butuh waktu lebih lama
- **MP3** — audio saja

### Langkah 4 — (Opsional) Potong video

Kalau hanya ingin bagian tertentu dari video, centang **"Mau potong bagian tertentu?"**
lalu isi waktu mulai dan waktu selesai.

Format waktu: `MM:SS` atau `HH:MM:SS`
Contoh: `01:30` artinya menit ke-1 detik ke-30, `01:15:00` artinya 1 jam 15 menit.

### Langkah 5 — Download

Klik tombol **Mulai Download** dan tunggu prosesnya selesai.
File akan tersimpan otomatis di folder `downloads/` di dalam folder project.

---

## Menghentikan Aplikasi

Di jendela Terminal yang menjalankan `./run.sh`, tekan `Ctrl + C`.

---

## Struktur Folder

```
ytdownloader/
├── app.py              # Backend (Flask)
├── install.sh          # Script instalasi (jalankan sekali)
├── run.sh              # Script menjalankan aplikasi
├── claude.md           # Spesifikasi project
├── README.md           # File ini
├── downloads/          # Folder hasil download (otomatis dibuat)
└── templates/
    └── index.html      # Tampilan web
```

---

## Troubleshooting

**Muncul "Permission denied" saat menjalankan `./install.sh` atau `./run.sh`**

Jalankan perintah ini terlebih dahulu:
```bash
chmod +x install.sh run.sh
```
Lalu coba lagi.

---

**Port 8421 sudah dipakai**

Tutup aplikasi lain yang mungkin berjalan di port tersebut, atau restart komputer.

---

**Download gagal / error**

- Pastikan koneksi internet aktif
- Pastikan URL yang di-paste adalah URL video tunggal (bukan playlist)
- Coba refresh halaman dan download ulang

---

**File hasil download di mana?**

Ada di dalam folder `downloads/` di dalam folder `ytdownloader`.
Bisa juga langsung klik tombol **Download File** setelah proses selesai,
file akan tersimpan ke folder Downloads bawaan browser kamu.

---

## Teknologi yang Digunakan

| Komponen   | Fungsi                                      |
|------------|---------------------------------------------|
| Python 3   | Runtime                                     |
| Flask      | Web server                                  |
| pytubefix  | Engine download YouTube                     |
| FFmpeg     | Merge video+audio, convert MP3, crop video  |
