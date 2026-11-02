#!/usr/bin/env python3
"""
PausaREC - Cattura l'audio in uscita dalla scheda audio (loopback)
e lo salva in un file MP3. Come una volta, senza nastro: nessun DJ
che parla sopra la tua canzone.

Uso:
    python pausarec.py                     # registra dal device predefinito
    python pausarec.py -o output.mp3       # nome file personalizzato
    python pausarec.py --list              # elenca le sorgenti audio disponibili
    python pausarec.py --device 2          # registra da un device specifico
    python pausarec.py --duration 60       # si ferma da solo dopo 60 secondi
    python pausarec.py --bitrate 320       # bitrate MP3 (kbit/s)

Ferma la registrazione con Ctrl+C.
"""

import argparse
import datetime
import sys

import numpy as np
import soundcard as sc
import lameenc

BANNER = r"""
   ____                    _____  ____  ____
  / __ \__ _  ___ _______ / ___/ / __ \/ __/
 / /_/ // ' \/ _ `/ __/ -_) /    / /_/ /\ \
 \____/_/_/_/\_,_/_/  \__/_/     \____/___/
     cattura l'audio che esce dalla tua scheda
"""


def list_loopbacks() -> None:
    """Elenca le sorgenti audio in loopback disponibili (una per ogni uscita)."""
    loopbacks = sc.all_microphones(include_loopback=True)
    default_mic = sc.default_microphone()
    default_speaker = sc.default_speaker()
    print("Sorgenti audio (loopback) disponibili:\n")
    for i, mic in enumerate(loopbacks):
        kind = "[LOOPBACK]" if mic.isloopback else "[MICROFONO]"
        default = " (predefinita)" if mic.id in (default_mic.id, default_speaker.id) else ""
        print(f"  {i}: {kind} {mic.name}{default}")


def pick_loopback(index: int | None):
    """Restituisce il device loopback scelto (o quello predefinito)."""
    loopbacks = [m for m in sc.all_microphones(include_loopback=True) if m.isloopback]
    if not loopbacks:
        sys.exit("Nessuna sorgente loopback trovata su questo sistema.")
    if index is None:
        default_speaker = sc.default_speaker()
        for mic in loopbacks:
            if mic.id == default_speaker.id:
                return mic
        return loopbacks[0]
    if index < 0 or index >= len(loopbacks):
        sys.exit(
            f"Indice device non valido: {index}. "
            f"Usa --list per vedere i device disponibili (0-{len(loopbacks) - 1})."
        )
    return loopbacks[index]


def encode_to_mp3(frames: np.ndarray, encoder: lameenc.Encoder) -> bytes:
    """Converte i frame float32 [-1, 1] in PCM int16 e li codifica in MP3."""
    pcm = np.clip(frames, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    return encoder.encode(pcm.tobytes())


def record(output_file: str, device_index: int | None,
           samplerate: int, bitrate: int, channels: int,
           duration: float | None) -> None:
    device = pick_loopback(device_index)
    print(f"Side           : Lato A")
    print(f"Sorgente audio : {device.name}")
    print(f"File di output : {output_file}")
    print(f"Formato        : MP3 @ {bitrate} kbit/s, {samplerate} Hz, {channels} canali")

    encoder = lameenc.Encoder()
    encoder.set_bit_rate(bitrate)
    encoder.set_in_sample_rate(samplerate)
    encoder.set_channels(channels)
    encoder.set_quality(2)  # 2 = alta qualità, 7 = veloce

    mp3_data = bytearray()
    bytes_recorded = 0
    start = datetime.datetime.now()

    print("\n◉ REC avviata... premi Ctrl+C per mettere in PAUSA e salvare.\n")

    try:
        with device.recorder(samplerate=samplerate, channels=channels) as rec:
            while True:
                # Campiona a blocchi da ~100 ms per feedback in tempo reale
                frames = rec.record(numframes=samplerate // 10)
                mp3_data += encode_to_mp3(frames, encoder)
                bytes_recorded += frames.shape[0]
                elapsed = (datetime.datetime.now() - start).total_seconds()
                if duration is not None and elapsed >= duration:
                    break
                mb = len(mp3_data) / (1024 * 1024)
                mins, secs = divmod(int(elapsed), 60)
                print(f"\r  ● REC  ⏱ {mins:02d}:{secs:02d}  |  {mb:6.2f} MB",
                      end="", flush=True)
    except KeyboardInterrupt:
        pass

    # Finalizza il flusso MP3
    mp3_data += encoder.flush()

    duration = bytes_recorded / samplerate
    with open(output_file, "wb") as f:
        f.write(bytes(mp3_data))

    mins, secs = divmod(int(duration), 60)
    print(f"\n\n■ STOP — nastro riavvolto, file salvato:")
    print(f"  Durata : {mins:02d}:{secs:02d}")
    print(f"  File   : {output_file} ({len(mp3_data) / (1024 * 1024):.2f} MB)")


def main() -> None:
    # Il terminale Windows di default usa una codepage non Unicode:
    # forzo UTF-8 (con fallback) per i simboli REC/STOP del banner.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
    print(BANNER)
    parser = argparse.ArgumentParser(
        prog="pausarec",
        description="PausaREC — cattura l'audio in uscita dalla scheda audio "
                    "e salva un MP3. Come una volta, senza nastro.")
    parser.add_argument("-o", "--output", metavar="FILE",
                        help="file MP3 di destinazione (predefinito: pausarec_<data>.mp3)")
    parser.add_argument("--device", type=int, metavar="N",
                        help="indice del device loopback (vedi --list)")
    parser.add_argument("--bitrate", type=int, default=192, metavar="Kbps",
                        help="bitrate MP3, es. 128, 192, 320 (predefinito: 192)")
    parser.add_argument("--samplerate", type=int, default=48000, metavar="Hz",
                        help="frequenza di campionamento (predefinito: 48000)")
    parser.add_argument("--channels", type=int, default=2, choices=[1, 2],
                        help="1 = mono, 2 = stereo (predefinito: 2)")
    parser.add_argument("--duration", type=float, metavar="SEC",
                        help="ferma automaticamente la registrazione dopo SEC secondi")
    parser.add_argument("--list", action="store_true",
                        help="elenca le sorgenti audio disponibili ed esce")
    args = parser.parse_args()

    if args.list:
        list_loopbacks()
        return

    output = args.output or "pausarec_" + \
        datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".mp3"

    try:
        record(output, args.device, args.samplerate, args.bitrate,
               args.channels, args.duration)
    except Exception as e:
        sys.exit(f"Errore: {e}")


if __name__ == "__main__":
    main()
