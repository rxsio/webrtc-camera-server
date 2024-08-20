#!/bin/bash

#region Prepare

    # Export GST_PLUGIN_PATH
export GST_PLUGIN_PATH=/gst-plugins-rs/target/release:$GST_PLUGIN_PATH

#endregion

#region Main loop

    # 1. Run signalling server
    # 2. Run python script for detecting cameras
(trap 'kill 0' SIGINT EXIT; 
    (
        python3 run.py ; kill 0
    ) &
    (
        python3 pipelines.py ; kill 0
    ) &
    wait
)

#endregion