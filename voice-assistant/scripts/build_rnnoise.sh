#!/bin/bash
# Build librnnoise (Xiph, v0.1.1 - self-contained, weights baked in) into lib/
# Needed for mic noise suppression (src/noise_suppressor.py).
# ~1 min on a Pi 5. Requires: gcc, wget, make.
set -e
cd "$(dirname "$0")/.."
rm -rf /tmp/rnnoise-0.1.1
wget -q -O rnnoise-0.1.1.tar.gz https://github.com/xiph/rnnoise/archive/refs/tags/v0.1.1.tar.gz
tar xzf rnnoise-0.1.1.tar.gz && rm rnnoise-0.1.1.tar.gz
cd rnnoise-0.1.1
mkdir -p ../lib
# minimal config.h (only celt_lpc.c / denoise.c / kiss_fft.c include it)
printf '#ifndef CONFIG_H\n#define CONFIG_H\n#define PACKAGE_VERSION "0.1.1"\n#endif\n' > config.h
gcc -O2 -fPIC -Iinclude -Isrc -shared -o ../lib/librnnoise.so \
    src/denoise.c src/rnn.c src/rnn_data.c src/pitch.c src/kiss_fft.c src/celt_lpc.c -lm
echo "built: $(ls -lh ../lib/librnnoise.so)"