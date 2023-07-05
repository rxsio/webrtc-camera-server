#!/bin/bash

source /usr/local/nvm/nvm.sh

export GST_PLUGIN_PATH=/gst-plugins-rs/target/release:$GST_PLUGIN_PATH
(trap 'kill 0' SIGINT EXIT; 
    (cd /gst-plugins-rs/ && WEBRTCSINK_SIGNALLING_SERVER_LOG=warn ./target/release/gst-webrtc-signalling-server; kill 0) &
    (cd /gst-plugins-rs/net/webrtc/gstwebrtc-api && npm start; kill 0) &
    (python3 pipelines.py; kill 0) &
    wait
)
