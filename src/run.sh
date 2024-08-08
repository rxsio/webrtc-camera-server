#!/bin/bash

#region Prepare

    # Activate NVM
# source /usr/local/nvm/nvm.sh

    # Export GST_PLUGIN_PATH
export GST_PLUGIN_PATH=/gst-plugins-rs/target/release:$GST_PLUGIN_PATH

#endregion

#region Main loop

    # 1. Run signalling server
    # 2. Run example video
    # 3. Run python script for detecting cameras
(trap 'kill 0' SIGINT EXIT; 
    (
        WEBRTCSINK_SIGNALLING_SERVER_LOG=debug ./gst-plugins-rs/target/release/gst-webrtc-signalling-server --cert /certificates/firo.p12 --cert-password skar ; kill 0
    ) &
    (
        gst-launch-1.0 webrtcsink name=ws meta="meta,name=gst-stream" signaller::uri="wss://localhost:8443" signaller::cafile="/certificates/RootCA.pem" videotestsrc ! ws. audiotestsrc ! ws. ; kill 0
    ) &
    (
        python3 pipelines.py ; kill 0
    ) &
    wait
)

#endregion
