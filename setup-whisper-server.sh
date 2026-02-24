#!/usr/bin/env bash
set -euo pipefail

# Whisp — whisper-server setup for Framework (bare-metal)
# Run this on your AI compute machine (e.g. Framework "tata" at 192.168.1.250)

WHISPER_TAG="v1.7.3"
MODEL="medium.en"
INSTALL_DIR="$HOME/whisper.cpp"
PORT=8788
THREADS=32

echo "==> Installing build dependencies..."
sudo apt-get update
sudo apt-get install -y build-essential cmake libopenblas-dev wget git

echo "==> Cloning whisper.cpp (${WHISPER_TAG})..."
if [ -d "$INSTALL_DIR" ]; then
    echo "    $INSTALL_DIR already exists, pulling..."
    cd "$INSTALL_DIR"
    git fetch --tags
    git checkout "$WHISPER_TAG"
else
    git clone --branch "$WHISPER_TAG" --depth 1 https://github.com/ggerganov/whisper.cpp.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

echo "==> Building whisper.cpp with native CPU optimizations..."
cmake -B build \
    -DGGML_NATIVE=ON \
    -DGGML_BLAS=ON \
    -DGGML_BLAS_VENDOR=OpenBLAS \
    -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j "$(nproc)"

echo "==> Downloading model: ${MODEL}..."
bash models/download-ggml-model.sh "$MODEL"

MODEL_PATH="$INSTALL_DIR/models/ggml-${MODEL}.bin"
SERVER_BIN="$INSTALL_DIR/build/bin/whisper-server"

if [ ! -f "$SERVER_BIN" ]; then
    # Older whisper.cpp versions put the binary elsewhere
    SERVER_BIN="$INSTALL_DIR/build/bin/server"
fi

if [ ! -f "$SERVER_BIN" ]; then
    echo "ERROR: Could not find whisper-server binary. Check build output."
    exit 1
fi

echo "==> Creating systemd service..."
sudo tee /etc/systemd/system/whisper-server.service > /dev/null <<EOF
[Unit]
Description=Whisper.cpp Server
After=network.target

[Service]
Type=simple
User=$USER
ExecStart=$SERVER_BIN \\
    --model $MODEL_PATH \\
    --port $PORT \\
    --threads $THREADS \\
    --no-timestamps
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "==> Enabling and starting whisper-server..."
sudo systemctl daemon-reload
sudo systemctl enable whisper-server
sudo systemctl restart whisper-server

echo ""
echo "Done! whisper-server is running on port ${PORT}."
echo ""
echo "Verify with:"
echo "  systemctl status whisper-server"
echo "  curl http://localhost:${PORT}/"
