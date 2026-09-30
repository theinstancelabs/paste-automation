#!/usr/bin/env bash
set -euo pipefail
exec gst-launch-1.0 v4l2src device=/dev/v4l/by-id/usb-EMEET_EMEET_SmartCam_C960_A260311000111730-video-index0 ! image/jpeg,width=640,height=480,framerate=30/1 ! jpegdec ! videoconvert ! ximagesink sync=false
