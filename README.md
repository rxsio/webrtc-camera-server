# webrtc-camera-server

This is the server used for streaming video from webcams to the control interface

## Building

To build the container, run

```bash
docker build --pull -t gstreamer-cameras .
```

## Running

To start the server, run

```bash
docker run --rm --privileged -it -v /run/udev:/run/udev:ro -v /dev:/dev -v ./config/config.yaml:/config.yaml --net=host --entrypoint bash gstreamer-cameras
```

And the inside of the container run

```bash
./run.sh
```
