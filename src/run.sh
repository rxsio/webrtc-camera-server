#!/bin/bash

#region Main loop

    # 1. Run signalling server
    # 2. Run pipelines
(trap 'kill 0' SIGINT EXIT; 
    (
        python3 signaller.py ; kill 0
    ) &
    (
        python3 pipelines.py ; kill 0
    ) &
    wait
)

#endregion