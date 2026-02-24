# Whisp

Self-hosted URL-to-transcript service. Share a link from your phone, get the transcript back.

Whisp is a two-node system: a lightweight API container handles URL downloading and audio conversion, while a dedicated compute machine runs whisper.cpp for transcription.

## Architecture

```
iPhone Share Sheet → iOS Shortcut
    → POST /transcribe  { "url": "https://..." }
    → pve2 (Docker container):
        1. yt-dlp downloads audio
        2. ffmpeg converts to 16kHz mono WAV
        3. Sends WAV to Framework via whisper-server API
    → Framework (bare-metal whisper-server on :8788):
        4. Transcribes with whisper.cpp
        5. Returns transcript
    → pve2 returns { "text": "...", "title": "..." }
    → iOS Shortcut copies to clipboard
```

| Node | Role | What runs |
|------|------|-----------|
| **pve2** | Web-facing API | Docker container: Flask + yt-dlp + ffmpeg |
| **Framework** | AI compute | Bare-metal whisper-server (whisper.cpp) |

## Supported Platforms

Anything yt-dlp supports — YouTube, Twitter/X, TikTok, Instagram, Reddit, Vimeo, and [1000+ more](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

## Setup

### Part 1: whisper-server on the compute machine (Framework)

SSH into your compute machine and run the setup script:

```bash
git clone https://github.com/<you>/whisp.git
cd whisp
chmod +x setup-whisper-server.sh
./setup-whisper-server.sh
```

This builds whisper.cpp with native CPU optimizations, downloads the `medium.en` model, and creates a systemd service on port 8788.

Verify it's running:

```bash
systemctl status whisper-server
```

### Part 2: API container on the web-facing host (pve2)

On pve2:

```bash
git clone https://github.com/<you>/whisp.git
cd whisp
cp .env.example .env
```

Edit `.env`:

```bash
API_KEY=your_secure_key_here
WHISPER_SERVER_URL=http://192.168.1.250:8788
PORT=8787
```

Start the container:

```bash
docker compose up -d
```

Verify:

```bash
curl http://localhost:8787/health
```

### Part 3: iOS Shortcut

Create a new Shortcut on your iPhone:

1. **Receive** input from Share Sheet (URLs)
2. **Get Contents of URL**:
   - URL: `http://<pve2-ip>:8787/transcribe`
   - Method: POST
   - Headers: `X-API-Key: your_key`, `Content-Type: application/json`
   - Body (JSON): `{"url": "<input>"}`
3. **Get Dictionary Value** for key `text`
4. **Copy to Clipboard**
5. **Show Notification**: `Transcript copied!`

Set the shortcut to accept URLs from the Share Sheet. Now share any video link and the transcript lands in your clipboard.

## API

### `POST /transcribe`

Transcribe a URL.

```bash
curl -X POST http://localhost:8787/transcribe \
  -H "X-API-Key: your_key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"}'
```

Response:

```json
{
  "ok": true,
  "title": "Me at the zoo",
  "text": "All right, so here we are...",
  "duration": 4.2
}
```

### `GET /health`

Health check (also verifies whisper-server connectivity).

```bash
curl http://localhost:8787/health
```

Response:

```json
{
  "status": "ok",
  "whisper_server": "ok"
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_KEY` | Required. Key for `X-API-Key` header auth | — |
| `WHISPER_SERVER_URL` | URL of your whisper-server instance | `http://192.168.1.250:8788` |
| `PORT` | Port for the API container | `8787` |

## Single-Machine Setup

If you want to run everything on one machine, just point `WHISPER_SERVER_URL` to `http://localhost:8788` and run both the setup script and the Docker container on the same host.

## License

MIT
