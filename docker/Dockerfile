FROM ubuntu:24.04

ENV UID=1002
ENV DEBIAN_FRONTEND=noninteractive

# 替换为阿里云镜像加速
RUN sed -i 's/archive.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    sed -i 's/security.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list

# 系统依赖 + Python 虚拟环境
# 添加 NodeSource（npm/Node.js 22.x，用于 Claude Code CLI）
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash -

RUN apt-get update && apt-get install -y \
    sudo \
    git \
    vim \
    curl \
    python3 \
    python3-pip \
    python3-venv \
    nodejs \
    alsa-utils \
    pulseaudio \
    pulseaudio-utils \
    ffmpeg \
    sox \
    libasound2-dev \
    portaudio19-dev \
    locales \
    locales-all \
    && rm -rf /var/lib/apt/lists/*

# 创建用户并加入 audio/pulse 组
RUN useradd -m -u $UID appuser && \
    usermod -a -G audio,pulse,pulse-access appuser && \
    usermod -a -G sudo appuser

# PulseAudio 配置
RUN mkdir -p /var/run/pulse && \
    chown appuser:appuser /var/run/pulse && \
    chmod 755 /var/run/pulse && \
    echo "load-module module-native-protocol-unix auth-anonymous=1 socket=/var/run/pulse/native" > /etc/pulse/default.pa && \
    echo "load-module module-always-sink" >> /etc/pulse/default.pa && \
    echo "load-module module-suspend-on-idle" >> /etc/pulse/default.pa

# Python 包安装在虚拟环境中（挂载项目目录后运行 pip install -r requirements.txt）
# 不在此处 pip install，由 run.sh 或用户手动管理

# 中文 locale
RUN locale-gen zh_CN.UTF-8 && update-locale LANG=zh_CN.UTF-8
ENV LANG=zh_CN.UTF-8
ENV LANGUAGE=zh_CN:zh
ENV LC_ALL=zh_CN.UTF-8

# Claude Code CLI（web_search 工具使用）
RUN npm install -g @anthropic-ai/claude-code

RUN git config --global --add safe.directory "*"

WORKDIR /workdir

USER appuser
CMD ["bash", "docker/run.sh"]
