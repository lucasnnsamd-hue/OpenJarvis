"""jarvis-show: espera duas palmas e então abre o Jarvis por voz.

Variáveis de ambiente:
  JARVIS_CLAP_THRESH  sensibilidade (0.01-1.0, padrão 0.30). MENOR = mais sensível.
  JARVIS_MIC          microfone: número do dispositivo ou parte do nome; vários separados por vírgula (ex.: 10,11). Padrão: o do sistema.
  JARVIS_SHOW_LIST=1  só lista os microfones e sai.
"""
from __future__ import annotations

import contextlib
import os
import queue
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

import numpy as np
import sounddevice as sd

ROOT = Path(__file__).resolve().parent
JINGLE = ROOT / "voz" / "assets" / "jingle.mp3"
URL = "http://localhost:8000"

THRESH = float(os.environ.get("JARVIS_CLAP_THRESH", "0.30"))
SAMPLE_RATE = 16000
BLOCK = 512  # ~32 ms
MIN_GAP, MAX_GAP = 0.12, 1.0  # intervalo válido entre as duas palmas (s)
DEAD_TIME = 0.10  # ignora o eco logo após uma palma (s)


def pick_mics() -> list:
    raw = os.environ.get("JARVIS_MIC", "").strip()
    if not raw:
        return [None]
    devices = []
    for mic in (p.strip() for p in raw.split(",") if p.strip()):
        if mic.isdigit():
            devices.append(int(mic))
            continue
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0 and mic.lower() in d["name"].lower():
                devices.append(i)
                break
        else:
            sys.exit(f"Microfone '{mic}' não encontrado. Rode com JARVIS_SHOW_LIST=1 para ver a lista.")
    return devices


def list_mics():
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            print(f"  [{i}] {d['name']}")


def wait_for_double_clap(devices) -> None:
    last = 0.0  # instante da primeira palma pendente
    last_peak = 0.0
    peaks: queue.Queue = queue.Queue()

    def callback(indata, frames, time_info, status):
        peaks.put(float(np.max(np.abs(indata))))

    with contextlib.ExitStack() as stack:
        for device in devices:
            rate = int(sd.query_devices(device, "input")["default_samplerate"])
            stack.enter_context(sd.InputStream(
                samplerate=rate, channels=1, blocksize=int(rate * 0.032),  # ~32 ms
                dtype="float32", device=device, callback=callback))
        while True:
            peak = peaks.get()
            now = time.monotonic()
            if peak < THRESH or now - last_peak < DEAD_TIME:
                continue
            last_peak = now
            if last and MIN_GAP <= now - last <= MAX_GAP:
                return
            last = now


def play_jingle() -> None:
    if not JINGLE.exists():
        return
    try:
        import soundfile as sf

        audio, sr = sf.read(str(JINGLE), dtype="float32")
        sd.play(audio, sr)
        sd.wait()
    except Exception as exc:  # som é opcional: nunca impede o Jarvis de abrir
        print(f"(não consegui tocar o jingle: {exc})")


def server_up() -> bool:
    try:
        urllib.request.urlopen(URL, timeout=1)
        return True
    except Exception:
        return False


def ensure_server() -> None:
    if server_up():
        return
    subprocess.Popen(
        ["uv", "run", "jarvis", "start"], cwd=ROOT,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    for _ in range(60):
        if server_up():
            return
        time.sleep(1)
    print("(a interface web demorou para subir; abrindo mesmo assim)")


def main() -> None:
    if os.environ.get("JARVIS_SHOW_LIST") == "1":
        list_mics()
        return
    devices = pick_mics()
    print(f"Escutando... bata duas palmas para chamar o Jarvis. (sensibilidade={THRESH}, Ctrl+C sai)")
    try:
        wait_for_double_clap(devices)
    except KeyboardInterrupt:
        return
    print("Duas palmas detectadas!")
    play_jingle()
    ensure_server()
    webbrowser.open(URL)
    sys.exit(subprocess.call(["uv", "run", "jarvis", "chat", "--voice", "--skip-runtime-panel"], cwd=ROOT))


if __name__ == "__main__":
    main()
