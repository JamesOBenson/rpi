"""
Speaker-lock filter.

After the wake word is confirmed, the kid who said "buddy" becomes the
reference speaker. Every 1s fragment of the question window is embedded
with a CAM++ speaker-embedding model; fragments that don't match the
reference are zeroed out, so the STT engine only hears the kid who
addressed the assistant (not the TV, not the other kids).

Calibrated 2026-10-05 with real captures from this Pi's mic (user voice
vs a background TV voice, same room):
  same-speaker chunks : 0.80-0.99 cosine vs reference
  cross-speaker chunks: 0.10-0.75 (gap between the two clusters)
  => threshold 0.75 sits in the measured gap.

Safety: if the filter keeps less than `min_keep` of the window, the
reference is probably contaminated (wake word said mid-overlap) or the
target speaker stopped talking - in that case the ORIGINAL audio is
returned, so the worst case is exactly today's unfiltered behavior.
"""

import numpy as np


class SpeakerFilter:
    SR = 16000

    def __init__(self, model_path, threshold=0.75, min_keep=0.25,
                 chunk_sec=1.0, hop_sec=0.5, num_threads=4):
        import sherpa_onnx
        self.threshold = threshold
        self.min_keep = min_keep
        self.chunk_sec = chunk_sec
        self.hop_sec = hop_sec
        self.extractor = sherpa_onnx.SpeakerEmbeddingExtractor(
            sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=model_path, num_threads=num_threads))

    def _embed(self, audio):
        """L2-normalized 512-d embedding, or None if the audio is too short."""
        if audio is None or len(audio) < self.SR // 4:  # < 0.25s
            return None
        st = self.extractor.create_stream()
        st.accept_waveform(self.SR,
                           np.ascontiguousarray(audio, dtype=np.float32))
        e = np.asarray(self.extractor.compute(st), dtype=np.float32)
        n = np.linalg.norm(e)
        return e / n if n > 1e-6 else None

    @staticmethod
    def _rms(a):
        return float(np.sqrt(np.mean(np.square(a, dtype=np.float32))))

    def reference(self, wake_audio):
        """Embedding of the loudest 1s slice of the wake-word utterance.

        The kid deliberately said "buddy" close to the mic, so their voice
        is the loudest source at that moment even with background present.
        Only ONE embedding is computed (RMS slice-picking is free).
        """
        if wake_audio is None:
            return None
        a = np.ascontiguousarray(wake_audio, dtype=np.float32)
        cn = int(self.chunk_sec * self.SR)
        if len(a) < cn:
            return self._embed(a)
        best, best_rms = None, -1.0
        hop = self.SR // 10  # 0.1s
        for i in range(0, len(a) - cn + 1, hop):
            r = self._rms(a[i:i + cn])
            if r > best_rms:
                best, best_rms = a[i:i + cn], r
        return self._embed(best)

    def filter(self, audio, ref):
        """Zero out 0.5s regions whose covering 1s chunk doesn't match ref.

        Returns (audio_out, info). audio_out is the original array when
        the filter should not be applied (no ref, or too little kept).
        """
        if ref is None or audio is None or len(audio) < self.SR:
            return audio, "off"
        cn = int(self.chunk_sec * self.SR)
        hn = int(self.hop_sec * self.SR)
        n = len(audio)
        sims = []
        for start in range(0, n - cn + 1, hn):
            c = audio[start:start + cn]
            if self._rms(c) < 0.01:  # silent chunk: no speaker in it
                sims.append(0.0)
            else:
                e = self._embed(c)
                sims.append(float(ref @ e) if e is not None else 0.0)
        # Region j = [j*hn, (j+1)*hn) is covered by chunks j-1 and j;
        # keep it if EITHER chunk matches (1s chunk, 0.5s hop).
        keep = np.zeros(n, dtype=bool)
        for j in range(n // hn):
            s = sims[j] if j < len(sims) else 0.0
            if j > 0:
                s = max(s, sims[j - 1])
            if s >= self.threshold:
                keep[j * hn:(j + 1) * hn] = True
        ratio = float(keep.mean())
        if ratio < self.min_keep:
            return audio, f"fallback (kept {ratio:.0%})"
        out = np.where(keep, audio, 0.0).astype(np.float32)
        return out, f"kept {ratio:.0%}"