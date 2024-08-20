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
RUN apt-get -y install python3-yaml python3-pyudev python3-psutil python3-httpx udev

#endregion

#region Install Rust

    # Install rustup
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | bash -s -- --default-toolchain stable -y
RUN apt-get -y install cargo

#endregion

#region Install Node.js

SHELL ["/bin/bash", "--login", "-c"]

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
COPY ./src/run.py run.py
COPY ./src/pipelines.py pipelines.py

    # Change attributes
RUN chmod +x run.sh

#endregion

#region Clear image

    # Remove packages
RUN apt-get -y remove gcc cmake git cmake-data cppcheck googletest
RUN apt-get -y remove fonts-urw-base35 opencv-data fonts-droid-fallback 
RUN apt-get -y remove perl-modules-5.38 qttranslations5-l10n poppler-data    
RUN apt-get -y remove mesa-vulkan-drivers pocketsphinx-en-us libopencv-contrib-dev

    # Remove APT lists
RUN rm -rf /var/lib/apt/lists/*

    # Remove cache and dependencies
RUN rm -rf ./root/.cargo
RUN rm -rf ./root/.rustup
RUN rm -rf ./gst-plugins-rs/target/release/deps

    # Remove .rlib and strip .so in gst-plugins
RUN find /gst-plugins-rs/target/release -type f -name "*.rlib" -delete
RUN find /gst-plugins-rs/target/release -type f -name "*.so" | xargs strip 

    # Clean gst-plugins
WORKDIR /gst-plugins-rs
RUN ls /gst-plugins-rs | grep -xv "target" | xargs rm -rf 
RUN rm -rf /gst-plugins-rs/target/release/.fingerprint

    # Clear /usr/share
RUN rm -rf /usr/share/pocketsphinx
RUN rm -rf /usr/share/icons
RUN rm -rf /usr/share/qt5
RUN rm -rf /usr/share/poppler
RUN rm -rf /usr/share/fonts-droid-fallback
RUN rm -rf /usr/share/perl
RUN rm -rf /usr/share/cmake-3.28
RUN rm -rf /usr/share/fonts
RUN rm -rf /usr/share/doc
RUN rm -rf /usr/share/proj
RUN rm -rf /usr/share/vim
RUN rm -rf /usr/lib/rustlib

# Clear apt
    RUN apt-get -y autoremove
    RUN apt-get -y autoclean
    RUN apt-get -y clean

#endregion

#region Production stage

FROM scratch
COPY --from=build / /
WORKDIR /
CMD ["./run.sh"]

#endregion
