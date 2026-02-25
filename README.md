# Whisp

Self-hosted URL-to-transcript service. Share a link from your phone, get the transcript back.

Whisp is a two-node system: a lightweight API container handles URL downloading and audio conversion, while a dedicated compute machine runs whisper.cpp for transcription.

## Architecture

```
iPhone Share Sheet → iOS Shortcut
    → POST /transcribe  { "url": "https://..." }
    → API node (Docker container):
        1. yt-dlp downloads audio
        2. ffmpeg converts to 16kHz mono WAV
        3. Sends WAV to compute node via whisper-server API
    → Compute node (bare-metal whisper-server on :8788):
        4. Transcribes with whisper.cpp
        5. Returns transcript
    → API node returns { "text": "...", "title": "..." }
    → iOS Shortcut copies to clipboard
```

| Node | Role | What runs |
|------|------|-----------|
| **API node** | Web-facing API | Docker container: Flask + yt-dlp + ffmpeg |
| **Compute node** | AI compute | Bare-metal whisper-server (whisper.cpp) |

## Supported Platforms

Anything yt-dlp supports — YouTube, Twitter/X, TikTok, Instagram, Reddit, Vimeo, and [1000+ more](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

## Setup

### Part 1: whisper-server on the compute node

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

### Part 2: API container on the API node

On your API node (any machine running Docker):

```bash
git clone https://github.com/<you>/whisp.git
cd whisp
cp .env.example .env
```

Edit `.env`:

```bash
API_KEY=your_secure_key_here
WHISPER_SERVER_URL=http://your-compute-node:8788
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

Install the pre-built shortcut:

[**Download Whisp Shortcut**](https://www.icloud.com/shortcuts/4bd5e36ae36d4da0a80b4672d25900c2)

After installing, you'll need to configure two things inside the shortcut:

1. **API Key** — Replace the placeholder with the `API_KEY` you set in your `.env` file
2. **Server URL** — Update the URL to point to your API node (e.g. `http://<your-api-node>:8787/transcribe`)

The shortcut does the following:

1. Accepts a URL from the Share Sheet (or manual input)
2. POSTs it to your Whisp server with your API key
3. Extracts the transcript text from the response
4. Copies it to your clipboard
5. Shows a "Transcript copied!" notification

Share any video link from Safari or any app and the transcript lands in your clipboard.

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
| `WHISPER_SERVER_URL` | Required. URL of your whisper-server instance (e.g. `http://10.0.0.5:8788`) | — |
| `PORT` | Port for the API container | `8787` |

## Single-Machine Setup

If you want to run everything on one machine, just point `WHISPER_SERVER_URL` to `http://localhost:8788` and run both the setup script and the Docker container on the same host.

## License

MIT
