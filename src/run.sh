#!/bin/bash

export GST_PLUGIN_PATH=/gst-plugins-rs/target/release:$GST_PLUGIN_PATH
(trap 'kill 0' SIGINT EXIT; 
    (cd /gst-plugins-rs/ && WEBRTCSINK_SIGNALLING_SERVER_LOG=warn ./target/release/gst-webrtc-signalling-server; 0) &
    (cd /gst-plugins-rs/net/webrtc/gstwebrtc-api && npm start; 0) &
    (python3 pipelines.py; kill 0) &
    wait
)
