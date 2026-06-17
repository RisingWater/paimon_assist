#!/bin/bash
set -e

cd "$(dirname "$0")"

# 构建（复用缓存，只更新变更）
echo "=== Building Docker image ==="
docker compose -f docker/docker-compose.yml build

# 如果容器已在运行，重启；否则启动
if docker compose -f docker/docker-compose.yml ps | grep -q "Up"; then
    echo "=== Restarting container ==="
    docker compose -f docker/docker-compose.yml restart
else
    echo "=== Starting container ==="
    docker compose -f docker/docker-compose.yml up -d
fi

echo ""
echo "Done. Web: http://localhost:8160"
echo "  Logs:  docker compose -f docker/docker-compose.yml logs -f"
echo "  Shell: docker exec -it paimon_assist bash"
echo "  Stop:  docker compose -f docker/docker-compose.yml down"
