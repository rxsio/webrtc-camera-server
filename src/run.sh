#!/bin/bash

#region Prepare

    # Activate NVM
source /usr/local/nvm/nvm.sh

    # Export GST_PLUGIN_PATH
export GST_PLUGIN_PATH=/gst-plugins-rs/target/release:$GST_PLUGIN_PATH

#endregion

#region Main loop

    # 1. Run signalling server
    # 2. Run example web page
    # 3. Run example video
    # 4. Run python script for detecting cameras
(trap 'kill 0' SIGINT EXIT; 
    (
        WEBRTCSINK_SIGNALLING_SERVER_LOG=debug ./gst-plugins-rs/target/release/gst-webrtc-signalling-server ; kill 0
    ) &
    (
        cd gst-plugins-rs/net/webrtc/gstwebrtc-api && webpack serve --host 0.0.0.0 ; kill 0
    ) &
    (
        gst-launch-1.0 webrtcsink name=ws meta="meta,name=gst-stream" videotestsrc ! ws. audiotestsrc ! ws. ; kill 0
    ) &
    (
        python3 pipelines.py ; kill 0
    ) &
    wait
)

#endregion