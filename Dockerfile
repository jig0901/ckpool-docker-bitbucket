FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y git build-essential libcurl4-openssl-dev libjansson-dev uthash-dev automake libtool autoconf pkg-config && \
    apt-get clean

# Clone original ckpool from Bitbucket
RUN git clone --single-branch --branch ProbabilityOdds https://jbelani@bitbucket.org/jbelani/ckpool.git /ckpool
WORKDIR /ckpool

# Patch global_ckp declaration
RUN ./autogen.sh && ./configure CFLAGS="-O2" && make

COPY ckpool.conf /ckpool/ckpool.conf
COPY entrypoint.sh /entrypoint.sh
COPY start.sh /start.sh

RUN chmod +x /entrypoint.sh /start.sh

ENTRYPOINT ["/entrypoint.sh"]
