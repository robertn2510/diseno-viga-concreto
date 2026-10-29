#!/usr/bin/env bash
# Inicia la interfaz web local del sistema de diseño E.060
cd "$(dirname "$0")"
python3 servidor.py "$@"
