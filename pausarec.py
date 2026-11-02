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
    python pausarec.py --silence 5         # nuovo MP3 dopo 5 s di silenzio:
                                           # traccia 1, traccia 2, ... in una cartella

Ferma la registrazione con Ctrl+C.
"""

import argparse
import datetime
import os
import sys

import numpy as np
import soundcard as sc
import lameenc

BANNER = r"""
     ____                       ____  _____ ____ 
    |  _ \ __ _ _   _ ___  __ _|  _ \| ____/ ___|
    | |_) / _` | | | / __|/ _` | |_) |  _|| |    
    |  __/ (_| | |_| \__ \ (_| |  _ <| |__| |___ 
    |_|   \__,_|\__,_|___/\__,_|_| \_\_____\____|
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


def make_encoder(samplerate: int, bitrate: int, channels: int) -> lameenc.Encoder:
    """Crea un encoder lameenc configurato per i parametri dati."""
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(bitrate)
    encoder.set_in_sample_rate(samplerate)
    encoder.set_channels(channels)
    encoder.set_quality(2)  # 2 = alta qualità, 7 = veloce
    return encoder


def is_silent(frames: np.ndarray, threshold: float) -> bool:
    """True se il blocco audio è sotto la soglia di rumore (RMS, 0.0-1.0)."""
    return float(np.sqrt(np.mean(np.square(frames)))) < threshold


def save_track(mp3_data: bytes, folder: str, track: int) -> str:
    """Salva una traccia MP3 nella cartella e restituisce il percorso."""
    path = os.path.join(folder, f"traccia {track}.mp3")
    with open(path, "wb") as f:
        f.write(mp3_data)
    return path


def record_tracks(output_dir: str, device_index: int | None,
                  samplerate: int, bitrate: int, channels: int,
                  duration: float | None, silence: float,
                  threshold: float) -> None:
    """Registra dividendo le tracce sui silenzi.

    Quando rileva `silence` secondi consecutivi di silenzio (RMS sotto
    `threshold`), chiude la traccia corrente, la salva nella cartella
    `output_dir` come "traccia N.mp3" e ne apre una nuova al prossimo
    audio rilevato. Un solo device aperto per tutta la sessione, quindi
    nessun sample va perso tra una traccia e l'altra.
    """
    device = pick_loopback(device_index)
    os.makedirs(output_dir, exist_ok=True)

    print(f"Sorgente audio : {device.name}")
    print(f"Cartella       : {output_dir}")
    print(f"Silenzio       : nuova traccia dopo {silence:g} s "
          f"(soglia RMS {threshold:g})")
    print(f"Formato        : MP3 @ {bitrate} kbit/s, {samplerate} Hz, {channels} canali")

    tail_frames_keep = int(min(silence, 1.0) * samplerate)  # coda breve a fine traccia

    encoder = make_encoder(samplerate, bitrate, channels)
    track = 1
    track_open = False    # la traccia corrente contiene almeno un frammento di audio
    mp3_data = bytearray()
    pending_silence: list[np.ndarray] = []  # silenzio sospeso (gap interno da tenere)
    silence_frames = 0    # frame consecutivi di silenzio al momento corrente
    track_frames = 0      # frame audio (silenzio interno incluso) nella traccia
    total_frames = 0
    start = datetime.datetime.now()

    print(f"\n◉ REC avviata... in attesa del primo audio (traccia 1)."
          f" Ctrl+C per fermare e salvare l'ultima traccia.\n")

    try:
        with device.recorder(samplerate=samplerate, channels=channels) as rec:
            while True:
                # Campiona a blocchi da ~100 ms per feedback in tempo reale
                frames = rec.record(numframes=samplerate // 10)
                n = frames.shape[0]
                total_frames += n
                silent = is_silent(frames, threshold)

                if silent:
                    if track_open:
                        # Il silenzio va sospeso: se dopo arriva ancora
                        # audio è una pausa interna da tenere, altrimenti
                        # segna la fine della traccia e viene scartato.
                        pending_silence.append(frames.copy())
                        silence_frames += n
                        if silence_frames / samplerate >= silence:
                            # Traccia finita: tiene solo una coda corta
                            # di silenzio prima di chiudere il file.
                            tail_n = tail_frames_keep
                            for buf in pending_silence:
                                if tail_n <= 0:
                                    break
                                take = buf[:tail_n]
                                mp3_data += encode_to_mp3(take, encoder)
                                track_frames += take.shape[0]
                                tail_n -= take.shape[0]
                            mp3_data += encoder.flush()
                            path = save_track(bytes(mp3_data), output_dir, track)
                            tmins, tsecs = divmod(int(track_frames / samplerate), 60)
                            mb = len(mp3_data) / (1024 * 1024)
                            print(f"\r  ✔ Traccia {track} salvata "
                                  f"({tmins:02d}:{tsecs:02d}, {mb:.2f} MB) "
                                  f"-> {path}")
                            track += 1
                            encoder = make_encoder(samplerate, bitrate, channels)
                            mp3_data = bytearray()
                            pending_silence = []
                            track_open = False
                            track_frames = 0
                            silence_frames = 0
                            print(f"  ... attesa audio per traccia {track}")
                    # Silenzio prima del primo audio: scartato, nessuna
                    # traccia vuota viene creata.
                else:
                    silence_frames = 0
                    if not track_open:
                        track_open = True
                        print(f"\r  ▶ tracce: audio rilevato, traccia {track} "
                              f"in registrazione")
                    else:
                        # Pausa interna finita: rimette nel flusso il
                        # silenzio sospeso prima del nuovo audio.
                        for buf in pending_silence:
                            mp3_data += encode_to_mp3(buf, encoder)
                            track_frames += buf.shape[0]
                        pending_silence = []
                    mp3_data += encode_to_mp3(frames, encoder)
                    track_frames += n

                elapsed_total = (datetime.datetime.now() - start).total_seconds()
                if duration is not None and elapsed_total >= duration:
                    break

                mins, secs = divmod(int(elapsed_total), 60)
                sil = silence_frames / samplerate
                status = (f"\r  ● REC  ⏱ {mins:02d}:{secs:02d}  "
                          f"|  traccia {track:3d}  |  "
                          f"silenzio {sil:4.1f}/{silence:g} s")
                print(status, end="", flush=True)
    except KeyboardInterrupt:
        pass

    # Chiude e salva l'ultima traccia, se contiene audio
    if track_open:
        for buf in pending_silence:
            mp3_data += encode_to_mp3(buf, encoder)
            track_frames += buf.shape[0]
        mp3_data += encoder.flush()
        path = save_track(bytes(mp3_data), output_dir, track)
    else:
        # Nessuna traccia registrata: segnala solo il totale
        path = None

    mins, secs = divmod(int(total_frames / samplerate), 60)
    saved = track if track_open else track - 1
    print(f"\n\n■ STOP — nastro riavvolto, {saved} tracce salvate in \"{output_dir}\":")
    print(f"  Durata totale : {mins:02d}:{secs:02d}")
    if path:
        print(f"  Ultima traccia: {path}")


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
    parser.add_argument("--silence", type=float, metavar="SEC",
                        help="modalità a tracce: dopo SEC secondi di silenzio "
                             "chiude l'MP3 corrente e ne inizia uno nuovo "
                             "(traccia 1, traccia 2, ...) salvati in una cartella")
    parser.add_argument("--threshold", type=float, default=0.005, metavar="AMP",
                        help="soglia RMS di silenzio, 0.0-1.0 (predefinita: 0.005)")
    parser.add_argument("-d", "--output-dir", metavar="CARTELLA",
                        help="cartella delle tracce per --silence "
                             "(predefinita: pausarec_<data>)")
    parser.add_argument("--list", action="store_true",
                        help="elenca le sorgenti audio disponibili ed esce")
    args = parser.parse_args()

    if args.list:
        list_loopbacks()
        return

    if args.silence is not None:
        if args.silence <= 0 or args.threshold < 0:
            sys.exit("--silence e --threshold devono essere maggiori di 0.")
        output_dir = args.output_dir or "pausarec_" + \
            datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if args.output:
            print("Nota: -o/--output è ignorato in modalità --silence; "
                  "le tracce sono salvate come \"traccia N.mp3\".")
        try:
            record_tracks(output_dir, args.device, args.samplerate, args.bitrate,
                          args.channels, args.duration, args.silence,
                          args.threshold)
        except Exception as e:
            sys.exit(f"Errore: {e}")
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
