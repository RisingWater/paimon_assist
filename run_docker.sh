#!/bin/bash
set -e

cd "$(dirname "$0")"

IMAGE="paimon_assist"
NAME="paimon_assist"

# 启动
echo "=== Starting ==="
docker run -d -it --name paimon_assist --privileged --device /dev/snd:/dev/snd -v /vol1/paimon_ai/paimon_assist:/workdir \
    -e PULSE_RUNTIME_PATH=/workdir/pulse -p 6018:8160 --restart unless-stopped paimon-assist

echo ""
echo "Done. Web: http://localhost:8160"
echo "  Logs:  docker logs -f $NAME"
echo "  Shell: docker exec -it $NAME bash"
echo "  Stop:  docker stop $NAME"
