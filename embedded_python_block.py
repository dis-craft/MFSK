import numpy as np
import pmt
from gnuradio import gr


class blk(gr.sync_block):
    def __init__(self, sample_rate=48000.0, fft_size=1920, base_freq=17000.0, step_freq=30.0, min_peak_power=25.0):
        gr.sync_block.__init__(
            self,
            name='Tone Decoder',
            in_sig=[np.float32],
            out_sig=[],
        )

        self.sample_rate = float(sample_rate)
        self.fft_size = int(fft_size)
        self.base_freq = float(base_freq)
        self.step_freq = float(step_freq)
        self.min_peak_power = float(min_peak_power)
        self.ascii_min = 32
        self.ascii_max = 126
        self.band_min_freq = self.base_freq
        self.band_max_freq = self.base_freq + (self.ascii_max - self.ascii_min) * self.step_freq
        self.band_min_bin = max(0, int(np.floor(self.band_min_freq * self.fft_size / self.sample_rate)))
        self.band_max_bin = min(
            self.fft_size // 2,
            int(np.ceil(self.band_max_freq * self.fft_size / self.sample_rate)),
        )
        self._buffer = np.array([], dtype=np.float32)
        self.decoded_text = ''
        self.current_status = ''
        self.symbol_index = 0

        self.message_port_register_out(pmt.intern('status'))

    def _decode_frequency(self, freq_hz):
        idx = int(round((freq_hz - self.base_freq) / self.step_freq))
        code = self.ascii_min + idx

        if code < self.ascii_min or code > self.ascii_max:
            return None

        nearest = self.base_freq + idx * self.step_freq
        if abs(freq_hz - nearest) > (self.step_freq / 2.0):
            return None

        return chr(code)

    def work(self, input_items, output_items):
        samples = input_items[0]
        if samples.size == 0:
            return 0

        self._buffer = np.concatenate((self._buffer, samples))
        emitted = 0

        while self._buffer.size >= self.fft_size:
            window = self._buffer[: self.fft_size]
            spectrum = np.fft.rfft(window * np.hanning(self.fft_size))
            magnitudes = np.abs(spectrum)
            symbol_time = self.symbol_index * (self.fft_size / self.sample_rate)
            band_magnitudes = magnitudes[self.band_min_bin : self.band_max_bin + 1]
            character = None
            peak_bin = -1
            peak_freq = 0.0
            peak_power = 0.0

            if band_magnitudes.size > 0:
                band_peak_offset = int(np.argmax(band_magnitudes))
                peak_bin = self.band_min_bin + band_peak_offset
                peak_freq = peak_bin * self.sample_rate / self.fft_size
                peak_power = float(band_magnitudes[band_peak_offset])

            if peak_power >= self.min_peak_power:
                character = self._decode_frequency(peak_freq)

            if character is not None:
                self.decoded_text += character
                self.current_status = (
                    f"time={symbol_time:.3f}s | word={self.decoded_text} | char={character} | "
                    f"freq={peak_freq:.1f} Hz | bin={peak_bin} | power={peak_power:.4f}"
                )
            else:
                self.current_status = (
                    f"time={symbol_time:.3f}s | word={self.decoded_text} | char=? | "
                    f"freq={peak_freq:.1f} Hz | bin={peak_bin} | power={peak_power:.4f}"
                )

            print(self.current_status, flush=True)
            self.message_port_pub(pmt.intern('status'), pmt.to_pmt(self.current_status))

            self._buffer = self._buffer[self.fft_size :]
            self.symbol_index += 1
            emitted += 1

        return len(samples)