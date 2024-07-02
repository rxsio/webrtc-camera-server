FROM ubuntu:23.04

# Change default shell used by Docker to bash
SHELL ["/bin/bash", "-c"]

# Install common dependencies and prepare the environment.
RUN apt-get update \
  && apt-get -y install \
        # useful utils
        vim git curl \ 
        # required for the python script
        python3-yaml python3-pyudev python3-psutil udev \
        # required for building gst-plugins-rs
        build-essential libssl-dev libx264-dev libvpx-dev libopus-dev  \
        # required for webrtc-sink to work properly
        libnice-dev gstreamer1.0-nice \
        # gstreamer
        libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev libgstreamer-plugins-good1.0-dev libgstreamer-plugins-bad1.0-dev \
        gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav \
        gstreamer1.0-tools python3-gst-1.0 \
        # hardware acceleration for amd (currently nonfunctional)
        # mesa-va-drivers gstreamer1.0-vaapi va-driver-all \
  && rm -rf /var/lib/apt/lists/* 

SHELL ["/bin/bash", "--login", "-c"]

# install nvm
RUN mkdir /usr/local/nvm
ENV NVM_DIR /usr/local/nvm
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash \
    && source $NVM_DIR/nvm.sh \
    && nvm install 18 \
    && nvm alias default 18 \
    && nvm use default

# install rustup
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | bash -s -- --default-toolchain stable -y

# clone gst-plugins-rs and select a specific commit, to ensure stable builds
RUN git clone https://gitlab.freedesktop.org/gstreamer/gst-plugins-rs.git \
    #&& cd gst-plugins-rs && git checkout 1dd13c481216ba093468ffe482a9c4f7f35bba41 \
    #&& cd gst-plugins-rs && git checkout 3c1f05cdc334cb3e26952e5a0c48be71835555e2 \
    # && cd gst-plugins-rs && git checkout e83238b6813742acba004ad590b1843739d3b920 \
    && cd gst-plugins-rs && rm -r .git

# install frontend dependencies
WORKDIR /gst-plugins-rs/net/webrtc/gstwebrtc-api
RUN source $NVM_DIR/nvm.sh \
    && npm install

# build plugins and signalling server
WORKDIR /gst-plugins-rs/net/webrtc
RUN cargo build --release
WORKDIR /gst-plugins-rs/net/webrtc/signalling
RUN cargo build --release
WORKDIR /gst-plugins-rs/net/rtp
RUN cargo build --release

# copy test scripts
WORKDIR /
COPY ./src/run.sh run.sh
COPY ./src/pipelines.py pipelines.py
RUN chmod +x run.sh

CMD ["./run.sh"]
