#!/usr/bin/env bash
# cd src/websocket-container/
docker buildx build --platform linux/amd64,linux/arm64 -t robachmann/artifactsmmo-websocket-container:1.4.0 -f src/websocket-container/Dockerfile .
