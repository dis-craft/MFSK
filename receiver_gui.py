#!/usr/bin/env python3

import argparse
import sys

from PyQt5 import Qt
from gnuradio import audio, filter, gr

from embedded_python_block import blk as tone_decoder


class ChipStrip(Qt.QScrollArea):
    def __init__(self):
        super().__init__()

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOff)
        self.setFrameShape(Qt.QFrame.NoFrame)

        self.container = Qt.QWidget()
        self.row = Qt.QHBoxLayout(self.container)
        self.row.setContentsMargins(12, 12, 12, 12)
        self.row.setSpacing(10)
        self.row.addStretch(1)
        self.setWidget(self.container)

        self.chips = []

    def clear(self):
        while self.chips:
            chip = self.chips.pop()
            self.row.removeWidget(chip)
            chip.deleteLater()

    def set_text(self, text):
        self.clear()
        for character in text:
            self.add_character(character)

    def add_character(self, character):
        chip = Qt.QLabel('SP' if character == ' ' else character)
        chip.setProperty('chip', True)
        chip.setAlignment(Qt.Qt.AlignCenter)
        chip.setMinimumWidth(36)
        chip.setMinimumHeight(34)
        self.row.insertWidget(self.row.count() - 1, chip)
        self.chips.append(chip)


class StatusPanel(Qt.QWidget):
    def __init__(self):
        super().__init__()

        self.word_value = Qt.QLabel('-')
        self.time_value = Qt.QLabel('-')
        self.char_value = Qt.QLabel('-')
        self.freq_value = Qt.QLabel('-')
        self.bin_value = Qt.QLabel('-')
        self.power_value = Qt.QLabel('-')
        self.word_strip = ChipStrip()
        self.log_view = Qt.QPlainTextEdit()

        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(300)

        self.word_value.setObjectName('wordValue')
        self.time_value.setObjectName('metricValue')
        self.char_value.setObjectName('metricValue')
        self.freq_value.setObjectName('metricValue')
        self.bin_value.setObjectName('metricValue')
        self.power_value.setObjectName('metricValue')

        title = Qt.QLabel('Acoustic Modem Receiver')
        title.setObjectName('title')

        subtitle = Qt.QLabel('Live decoded text, tone metrics, and symbol log')
        subtitle.setObjectName('subtitle')

        self.word_caption = Qt.QLabel('Decoded text')
        self.word_caption.setObjectName('sectionLabel')

        self.metrics_caption = Qt.QLabel('Symbol details')
        self.metrics_caption.setObjectName('sectionLabel')

        self.log_caption = Qt.QLabel('Live log')
        self.log_caption.setObjectName('sectionLabel')

        grid = Qt.QGridLayout()
        grid.addWidget(Qt.QLabel('Time'), 0, 0)
        grid.addWidget(self.time_value, 0, 1)
        grid.addWidget(Qt.QLabel('Character'), 1, 0)
        grid.addWidget(self.char_value, 1, 1)
        grid.addWidget(Qt.QLabel('Frequency'), 2, 0)
        grid.addWidget(self.freq_value, 2, 1)
        grid.addWidget(Qt.QLabel('FFT Bin'), 3, 0)
        grid.addWidget(self.bin_value, 3, 1)
        grid.addWidget(Qt.QLabel('Peak Power'), 4, 0)
        grid.addWidget(self.power_value, 4, 1)

        metrics_card = Qt.QFrame()
        metrics_card.setObjectName('metricsCard')
        metrics_layout = Qt.QVBoxLayout(metrics_card)
        metrics_layout.setContentsMargins(18, 18, 18, 18)
        metrics_layout.addLayout(grid)

        word_card = Qt.QFrame()
        word_card.setObjectName('wordCard')
        word_layout = Qt.QVBoxLayout(word_card)
        word_layout.setContentsMargins(18, 18, 18, 18)
        word_layout.addWidget(self.word_caption)
        word_layout.addWidget(self.word_strip)
        word_layout.addWidget(Qt.QLabel('Current word'))
        word_layout.addWidget(self.word_value)

        log_card = Qt.QFrame()
        log_card.setObjectName('logCard')
        log_layout = Qt.QVBoxLayout(log_card)
        log_layout.setContentsMargins(18, 18, 18, 18)
        log_layout.addWidget(self.log_caption)
        log_layout.addWidget(self.log_view)

        layout = Qt.QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(word_card)
        layout.addWidget(self.metrics_caption)
        layout.addWidget(metrics_card)
        layout.addWidget(log_card, 1)

        self.setStyleSheet(
            'QWidget { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #07101d, stop:1 #0d1730); color: #edf2ff; font-size: 14px; }'
            'QLabel#title { font-size: 24px; font-weight: 700; letter-spacing: 0.5px; }'
            'QLabel#subtitle { color: #9db0d3; font-size: 13px; margin-bottom: 6px; }'
            'QLabel#sectionLabel { color: #8adbb5; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.4px; margin-bottom: 6px; }'
            'QFrame#wordCard, QFrame#metricsCard, QFrame#logCard { background: rgba(6, 10, 20, 0.78); border: 1px solid rgba(138, 219, 181, 0.12); border-radius: 18px; }'
            'QLabel#wordValue { font-size: 24px; font-weight: 700; color: #ffffff; padding: 2px 0 4px; }'
            'QLabel#metricValue { font-size: 15px; font-weight: 600; color: #f0f4ff; }'
            'QLabel[chip="true"] { background: rgba(138, 219, 181, 0.12); border: 1px solid rgba(138, 219, 181, 0.22); border-radius: 12px; padding: 6px 10px; color: #f5f9ff; font-weight: 700; }'
            'QPlainTextEdit { background: #08101f; border: 1px solid #24304d; border-radius: 12px; padding: 8px; font-family: "IBM Plex Mono", monospace; }'
        )

    def update_status(self, status_text):
        fields = {}
        for chunk in status_text.split('|'):
            if '=' not in chunk:
                continue
            key, value = chunk.split('=', 1)
            fields[key.strip()] = value.strip()

        word_text = fields.get('word', '-')
        self.word_value.setText(word_text)
        self.word_strip.set_text(word_text if word_text != '-' else '')
        self.time_value.setText(fields.get('time', '-'))
        self.char_value.setText(fields.get('char', '-'))
        self.freq_value.setText(fields.get('freq', '-'))
        self.bin_value.setText(fields.get('bin', '-'))
        self.power_value.setText(fields.get('power', '-'))
        self.log_view.appendPlainText(status_text)


class receiver_top_block(gr.top_block, Qt.QWidget):
    def __init__(self, device_name='pulse', sample_rate=48000):
        gr.top_block.__init__(self, 'Acoustic Modem Receiver')
        Qt.QWidget.__init__(self)

        self.sample_rate = int(sample_rate)
        self.fft_size = 1920
        self.base_freq = 17000.0
        self.step_freq = 30.0

        self.status_panel = StatusPanel()

        self.audio_source = audio.source(self.sample_rate, device_name, True)
        self.dc_blocker = filter.dc_blocker_ff(32, True)
        self.tone_decoder = tone_decoder(
            sample_rate=self.sample_rate,
            fft_size=self.fft_size,
            base_freq=self.base_freq,
            step_freq=self.step_freq,
            min_peak_power=25.0,
        )

        self.connect(self.audio_source, self.dc_blocker, self.tone_decoder)

        layout = Qt.QVBoxLayout(self)
        layout.addWidget(self.status_panel)

        self.setWindowTitle('Acoustic Modem Receiver')
        self.resize(1080, 780)

        self.status_timer = Qt.QTimer(self)
        self.status_timer.timeout.connect(self._refresh_status)
        self.status_timer.start(100)

        self.last_status = ''

    def _refresh_status(self):
        status_text = self.tone_decoder.current_status
        if status_text and status_text != self.last_status:
            self.last_status = status_text
            self.status_panel.update_status(status_text)


def main():
    parser = argparse.ArgumentParser(description='Acoustic modem receiver GUI')
    parser.add_argument('--device', default='pulse', help='GNU Radio audio input device name')
    parser.add_argument('--sample-rate', type=int, default=48000, help='Audio sample rate')
    args = parser.parse_args()

    app = Qt.QApplication(sys.argv)
    top_block = receiver_top_block(device_name=args.device, sample_rate=args.sample_rate)
    top_block.start()
    top_block.show()

    app.aboutToQuit.connect(top_block.stop)
    app.aboutToQuit.connect(top_block.wait)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()