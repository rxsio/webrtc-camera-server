#region Build stage

    # Build on ros image
FROM ros:jazzy-ros-core as build

    # Change default shell used by Docker to bash
SHELL ["/bin/bash", "-c"]

#endregion

#region Install common dependencies

    # Update repository
RUN apt-get update

    # Usefull utilities
RUN apt-get -y install git curl

    # GStreamer dependencies
RUN apt-get -y install libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev libgstreamer-plugins-bad1.0-dev \
                        gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
                        gstreamer1.0-plugins-ugly gstreamer1.0-libav gstreamer1.0-tools gstreamer1.0-x \
                        gstreamer1.0-alsa gstreamer1.0-gl gstreamer1.0-gtk3 gstreamer1.0-qt5 gstreamer1.0-pulseaudio \
                        python3-gst-1.0

    # GStreamer plugins dependencies
RUN apt-get -y install build-essential libssl-dev libx264-dev libvpx-dev libopus-dev

    # WebRTC dependencies
RUN apt-get -y install libnice-dev gstreamer1.0-nice

    # Python dependencies
RUN apt-get -y install python3-yaml python3-pyudev python3-psutil udev

#endregion

#region Install Rust

    # Install rustup
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | bash -s -- --default-toolchain stable -y
RUN apt-get -y install cargo

#endregion

#region Install Node.js

SHELL ["/bin/bash", "--login", "-c"]

    # Install NVM
RUN mkdir /usr/local/nvm
ENV NVM_DIR /usr/local/nvm
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash

    # Install Node 18
RUN source $NVM_DIR/nvm.sh \
    && nvm install 18 \
    && nvm alias default 18 \
    && nvm use default

#endregion

#region Clone repository

RUN git clone https://gitlab.freedesktop.org/gstreamer/gst-plugins-rs.git
RUN cd gst-plugins-rs

#endregion

#region Build frontend

#endregion

#region Build plugins

# RUN cargo cbuild -p webrtc

    # Build WebRTC plugin
WORKDIR /gst-plugins-rs/net/webrtc
RUN cargo build --release

    # Build Signalling server
WORKDIR /gst-plugins-rs/net/webrtc/signalling
RUN cargo build --release

    # Build RTP
WORKDIR /gst-plugins-rs/net/rtp
RUN cargo build --release

#endregion

#region Copy scripts

    # Copy
WORKDIR /
COPY ./src/run.sh run.sh
COPY ./src/pipelines.py pipelines.py

    # Change attributes
RUN chmod +x run.sh

#endregion

#region Clear image

    # Remove APT lists
RUN rm -rf /var/lib/apt/lists/*

    # Remove Rust
RUN apt-get -y remove cargo

    # Remove cache and dependencies
RUN rm -rf ./root/.cargo
RUN rm -rf ./root/.rustup
RUN rm -rf ./gst-plugins-rs/target/release/deps

    # Remove .rlib and strip .so in gst-plugins
RUN find /gst-plugins-rs/target/release -type f -name "*.rlib" -delete
RUN find /gst-plugins-rs/target/release -type f -name "*.so" | xargs strip 

    # Remove .rlib in rustlib
RUN find /usr/lib/rustlib -type f -name "*.rlib" -delete

#endregion

#region Production stage

FROM scratch
COPY --from=build / /
WORKDIR /
CMD ["./run.sh"]

#endregion
