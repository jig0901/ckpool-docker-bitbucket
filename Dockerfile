FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Build deps + runtime libs (incl. jemalloc for runtime stability)
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential clang git pkg-config autoconf automake libtool \
    libcurl4-openssl-dev libssl-dev libjansson-dev libgmp-dev \
    libevent-dev zlib1g-dev libsqlite3-dev ca-certificates \
    libjemalloc2 bash \
 && rm -rf /var/lib/apt/lists/*

# Clone your fork/branch
RUN git clone --single-branch --branch Report https://jbelani@bitbucket.org/jbelani/ckpool.git /ckpool
WORKDIR /ckpool

# Patch C++17 fallthrough attributes to C-safe comments
# (prevents: stratifier.c:****: error: expected expression)
RUN sed -i 's/\[\[fallthrough\]\];/\/\* fallthrough *\//g' src/stratifier.c

# Configure & build with clang in C mode, C11/gnu11 features enabled
# Also soften any fallthrough warnings
RUN ./autogen.sh \
 && ./configure CC=clang CFLAGS="-O2 -std=gnu11 -Wno-implicit-fallthrough" \
 && make -j"$(nproc)"

# Runtime config/scripts
COPY ckpool.conf /ckpool/ckpool.conf
COPY entrypoint.sh /entrypoint.sh
COPY start.sh /start.sh
RUN chmod +x /entrypoint.sh /start.sh

# Use jemalloc at runtime to avoid glibc smallbin crash
ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2
ENV MALLOC_CONF=background_thread:true,dirty_decay_ms:5000,muzzy_decay_ms:5000

ENTRYPOINT ["/entrypoint.sh"]
