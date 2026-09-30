#!/usr/bin/env bash
set -euo pipefail
exec gst-launch-1.0 v4l2src device=/dev/v4l/by-id/usb-Image+_Galyimage_Live_camera_HU123456798765432-video-index0 ! image/jpeg,width=1920,height=1080,framerate=30/1 ! jpegdec ! videoconvert ! ximagesink sync=false
