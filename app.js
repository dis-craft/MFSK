const SAMPLE_RATE = 48000;
const TONE_MS = 40;
const GAP_MS = 8;
const FADE_MS = 4;
const BASE_FREQ = 17000;
const STEP_FREQ = 30;
const ASCII_MIN = 32;
const ASCII_MAX = 126;

const messageInput = document.getElementById('messageInput');
const playButton = document.getElementById('playButton');
const stopButton = document.getElementById('stopButton');
const downloadButton = document.getElementById('downloadButton');
const statusPill = document.getElementById('statusPill');
const sequencePreview = document.getElementById('sequencePreview');
const frequencyPreview = document.getElementById('frequencyPreview');

let audioContext = null;
let activeTimeouts = [];

function isPrintableAscii(code) {
  return code >= ASCII_MIN && code <= ASCII_MAX;
}

function sanitizeText(value) {
  return [...value]
    .map((character) => {
      const code = character.charCodeAt(0);
      return isPrintableAscii(code) ? character : ' ';
    })
    .join('');
}

function charToFrequency(character) {
  const code = character.charCodeAt(0);
  return BASE_FREQ + (code - ASCII_MIN) * STEP_FREQ;
}

function frequencyToChar(frequency) {
  const index = Math.round((frequency - BASE_FREQ) / STEP_FREQ);
  const code = ASCII_MIN + index;
  if (code < ASCII_MIN || code > ASCII_MAX) {
    return null;
  }

  return String.fromCharCode(code);
}

function updateStatus(text, tone = 'idle') {
  statusPill.textContent = text;
  statusPill.dataset.state = tone;
}

function renderPreview() {
  const sanitized = sanitizeText(messageInput.value);
  const characters = [...sanitized].filter((character) => character !== '\n');

  sequencePreview.replaceChildren();
  if (!characters.length) {
    const empty = document.createElement('span');
    empty.textContent = 'Empty';
    empty.className = 'is-active';
    sequencePreview.append(empty);
  } else {
    characters.forEach((character) => {
      const chip = document.createElement('span');
      chip.textContent = character === ' ' ? 'SP' : character;
      sequencePreview.append(chip);
    });
  }

  const details = characters.length
    ? characters
        .map((character) => {
          const frequency = charToFrequency(character);
          const label = character === ' ' ? 'space' : character;
          return `${label} -> ${frequency.toFixed(0)} Hz`;
        })
        .join(' | ')
    : 'Type text to see the tone mapping.';

  frequencyPreview.textContent = details;
}

function createEnvelope(length, fadeLength) {
  const envelope = new Float32Array(length);
  for (let index = 0; index < length; index += 1) {
    const fadeIn = Math.min(1, index / Math.max(1, fadeLength));
    const fadeOut = Math.min(1, (length - 1 - index) / Math.max(1, fadeLength));
    envelope[index] = Math.min(fadeIn, fadeOut, 1);
  }
  return envelope;
}

function appendTone(buffer, offset, frequency, symbolSamples, gapSamples, fadeSamples) {
  const toneSamples = symbolSamples;
  const gapStart = offset + toneSamples;
  const envelope = createEnvelope(toneSamples, fadeSamples);

  for (let index = 0; index < toneSamples; index += 1) {
    const phase = (2 * Math.PI * frequency * index) / SAMPLE_RATE;
    buffer[offset + index] = Math.sin(phase) * 0.85 * envelope[index];
  }

  for (let index = 0; index < gapSamples; index += 1) {
    buffer[gapStart + index] = 0;
  }

  return gapStart + gapSamples;
}

function buildSamples(text) {
  const sanitized = sanitizeText(text);
  const characters = [...sanitized];
  const toneSamples = Math.round((TONE_MS / 1000) * SAMPLE_RATE);
  const gapSamples = Math.round((GAP_MS / 1000) * SAMPLE_RATE);
  const fadeSamples = Math.round((FADE_MS / 1000) * SAMPLE_RATE);
  const leadInSamples = Math.round(0.08 * SAMPLE_RATE);
  const tailSamples = Math.round(0.12 * SAMPLE_RATE);
  const totalSamples = leadInSamples + characters.length * (toneSamples + gapSamples) + tailSamples;

  const buffer = new Float32Array(totalSamples);
  let offset = leadInSamples;

  characters.forEach((character) => {
    offset = appendTone(buffer, offset, charToFrequency(character), toneSamples, gapSamples, fadeSamples);
  });

  return buffer;
}

function floatTo16BitPcm(floatBuffer) {
  const output = new Int16Array(floatBuffer.length);
  for (let index = 0; index < floatBuffer.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, floatBuffer[index]));
    output[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
  }
  return output;
}

function encodeWav(samples) {
  const pcm = floatTo16BitPcm(samples);
  const buffer = new ArrayBuffer(44 + pcm.length * 2);
  const view = new DataView(buffer);
  const writeString = (offset, value) => {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(offset + index, value.charCodeAt(index));
    }
  };

  writeString(0, 'RIFF');
  view.setUint32(4, 36 + pcm.length * 2, true);
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, SAMPLE_RATE, true);
  view.setUint32(28, SAMPLE_RATE * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, 'data');
  view.setUint32(40, pcm.length * 2, true);

  let offset = 44;
  for (let index = 0; index < pcm.length; index += 1) {
    view.setInt16(offset, pcm[index], true);
    offset += 2;
  }

  return new Blob([buffer], { type: 'audio/wav' });
}

async function playText() {
  stopPlayback();
  const text = sanitizeText(messageInput.value);
  const samples = buildSamples(text);
  const audioBuffer = audioContext ?? new (window.AudioContext || window.webkitAudioContext)({ sampleRate: SAMPLE_RATE });
  audioContext = audioBuffer;

  if (audioBuffer.state === 'suspended') {
    await audioBuffer.resume();
  }

  const buffer = audioBuffer.createBuffer(1, samples.length, SAMPLE_RATE);
  buffer.copyToChannel(samples, 0);

  const source = audioBuffer.createBufferSource();
  source.buffer = buffer;
  source.connect(audioBuffer.destination);
  source.onended = () => updateStatus('Done', 'idle');

  source.start();
  updateStatus('Playing', 'active');

  const active = setTimeout(() => {
    updateStatus('Done', 'idle');
  }, (samples.length / SAMPLE_RATE) * 1000 + 50);
  activeTimeouts.push(active);
}

function stopPlayback() {
  activeTimeouts.forEach((timeoutId) => clearTimeout(timeoutId));
  activeTimeouts = [];

  if (audioContext && audioContext.state !== 'closed') {
    audioContext.close().catch(() => {});
  }

  audioContext = null;
  updateStatus('Idle', 'idle');
}

function downloadWav() {
  const text = sanitizeText(messageInput.value);
  const blob = encodeWav(buildSamples(text));
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'acoustic-modem.wav';
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

messageInput.addEventListener('input', renderPreview);
playButton.addEventListener('click', playText);
stopButton.addEventListener('click', stopPlayback);
downloadButton.addEventListener('click', downloadWav);

renderPreview();
updateStatus('Idle', 'idle');

window.addEventListener('beforeunload', stopPlayback);

window.acousticModem = {
  charToFrequency,
  frequencyToChar,
  sanitizeText,
};