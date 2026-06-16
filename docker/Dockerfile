FROM ubuntu:22.04

ENV UID=1002
ENV DEBIAN_FRONTEND=noninteractive

# 替换为阿里云镜像加速
RUN sed -i 's/archive.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    sed -i 's/security.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list

# 系统依赖
RUN apt-get update && apt-get install -y \
    sudo \
    git \
    vim \
    curl \
    python3 \
    python3-pip \
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

# Python 依赖（使用清华源加速）
RUN pip3 install --no-cache-dir \
    torch \
    onnxruntime \
    pyaudio \
    numpy \
    soundfile \
    scipy \
    requests \
    python-dotenv \
    fastapi \
    uvicorn \
    python-multipart \
    pypinyin \
    unidecode \
    phonemizer \
    datasets \
    silero-vad \
    funasr \
    modelscope \
    addict \
    -i https://pypi.tuna.tsinghua.edu.cn/simple/

# livekit-wakeword 不在清华镜像，单独从默认 PyPI 安装
RUN pip3 install --no-cache-dir "livekit-wakeword[listener]"

# 中文 locale
RUN locale-gen zh_CN.UTF-8 && update-locale LANG=zh_CN.UTF-8
ENV LANG=zh_CN.UTF-8
ENV LANGUAGE=zh_CN:zh
ENV LC_ALL=zh_CN.UTF-8

RUN git config --global --add safe.directory "*"

WORKDIR /workdir

# 入口脚本
COPY docker/run.sh /workdir/run.sh
RUN chmod +x /workdir/run.sh

USER appuser
CMD ["/workdir/run.sh"]
