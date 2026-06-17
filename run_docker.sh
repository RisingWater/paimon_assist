#!/bin/bash
set -e

cd "$(dirname "$0")"

IMAGE="paimon_assist"
NAME="paimon_assist"

# 构建
echo "=== Building ==="
docker build -t $IMAGE -f docker/Dockerfile .

# 如果旧容器在运行，先干掉
docker rm -f $NAME 2>/dev/null || true

# 启动
echo "=== Starting ==="
docker run -d \
    --name $NAME \
    --privileged \
    --device /dev/snd:/dev/snd \
    -v /var/run/pulse:/var/run/pulse \
    -v "$(pwd)":/workdir \
    -e PULSE_RUNTIME_PATH=/var/run/pulse \
    -p 8160:8160 \
    --restart unless-stopped \
    $IMAGE

echo ""
echo "Done. Web: http://localhost:8160"
echo "  Logs:  docker logs -f $NAME"
echo "  Shell: docker exec -it $NAME bash"
echo "  Stop:  docker stop $NAME"
