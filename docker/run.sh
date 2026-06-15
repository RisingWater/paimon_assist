#!/bin/bash
set -e

cd /workdir

# 更新代码（如果可访问 git）
if [ -d .git ] && git status &> /dev/null; then
    echo "Updating code..."
    git pull || true
fi

# ---- PulseAudio ----
echo "Starting PulseAudio..."

pulseaudio --kill 2>/dev/null || true
sleep 2

pulseaudio --start --exit-idle-time=-1 --log-target=stderr &

MAX_RETRIES=30
RETRY_COUNT=0
PULSE_STARTED=false

echo "Waiting for PulseAudio to start..."
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if pactl info &> /dev/null; then
        PULSE_STARTED=true
        echo "PulseAudio started successfully"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ "$PULSE_STARTED" = false ]; then
    echo "PulseAudio failed, retrying forcefully..."
    killall pulseaudio 2>/dev/null || true
    sleep 3
    pulseaudio --start --exit-idle-time=-1 --log-target=stderr &
    sleep 5
    if pactl info &> /dev/null; then
        PULSE_STARTED=true
    else
        echo "PulseAudio startup failed, exiting"
        exit 1
    fi
fi

if [ "$PULSE_STARTED" = true ]; then
    echo "Enabling anonymous connections..."
    pactl load-module module-native-protocol-unix auth-anonymous=1

    echo "Cleaning up existing audio modules..."
    pactl unload-module module-null-sink 2>/dev/null || true
    pactl unload-module module-alsa-sink 2>/dev/null || true
    pactl unload-module module-alsa-source 2>/dev/null || true
    sleep 1

    # 加载扬声器 (sink)
    echo "Loading ALSA sink (speaker)..."
    SINK_MODULE=$(pactl load-module module-alsa-sink device=hw:0,0 sink_name=alsa_output 2>/dev/null || true)
    if [ -n "$SINK_MODULE" ]; then
        echo "ALSA sink loaded, module: $SINK_MODULE"
        pactl set-default-sink alsa_output
        pactl set-sink-volume alsa_output 80%
    else
        echo "WARNING: ALSA sink load failed, speaker may not work"
    fi

    # 加载麦克风 (source)
    echo "Loading ALSA source (mic)..."
    SOURCE_MODULE=$(pactl load-module module-alsa-source device=hw:0,0 source_name=alsa_input 2>/dev/null || true)
    if [ -n "$SOURCE_MODULE" ]; then
        echo "ALSA source loaded, module: $SOURCE_MODULE"
        pactl set-default-source alsa_input
    else
        echo "WARNING: ALSA source load failed, mic may not work"
    fi

    echo "Audio devices:"
    pactl list sinks short
    pactl list sources short
    echo "Audio initialization complete"
fi

# ---- 启动应用 ----
echo "Starting 派萌助手..."
exec python3 src/main.py
