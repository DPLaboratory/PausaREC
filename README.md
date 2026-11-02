# PausaREC 📼

**Cattura l'audio in uscita dalla scheda audio e salvalo in MP3. Come una volta, senza nastro.**

Ricordi quando aspettavi che il DJ finisse di parlare per premere REC e registrare la canzone dalla radio sulla cassetta? PausaREC fa la stessa cosa con il suono del tuo PC: qualsiasi cosa stai ascoltando — Spotify, YouTube, browser, videogiochi, chiamate — viene catturata dall'**uscita** della scheda audio e salvata in un file **MP3** pulito, senza microfoni, senza ricavi di cavi, senza DJ che parla sopra la tua canzone.

Funziona su Windows tramite il **loopback WASAPI**: intercetta l'audio direttamente dal bus del sistema.

---

## Requisiti

- **Python 3.10 o superiore** (testato con Python 3.12)
- **Windows 10/11**
- Le seguenti librerie Python (installate con pip):
  - [soundcard](https://pypi.org/project/soundcard/) — cattura audio in loopback
  - [lameenc](https://pypi.org/project/lameenc/) — codifica MP3 (LAME)
  - [numpy](https://pypi.org/project/numpy/) — gestione dei campioni audio

---

## Installazione

```bash
cd C:\Develop\@Prj-Lab\PausaREC
pip install -r requirements.txt
```

oppure manualmente:

```bash
pip install soundcard lameenc numpy
```

---

## Utilizzo

### Registrazione rapida

```bash
python pausarec.py
```

- Avvia subito la registrazione dall'**uscita audio predefinita**.
- La registrazione continua finché non premi **`Ctrl+C`**: a quel punto l'app finalizza il file MP3 e lo salva ("nastro riavvolto").
- Se non viene specificato un nome, il file viene salvato come `pausarec_AAAAMMGG_HHMMSS.mp3` (con data e ora correnti).

### Modalità a tracce: split automatico sul silenzio

```bash
python pausarec.py --silence 5
```

Questa è la vera magia del nastro: quando rileva **5 secondi consecutivi di silenzio** (colonna sonora ferma), chiude l'MP3 corrente e ne apre uno nuovo. I file vengono salvati in una cartella come `traccia 1.mp3`, `traccia 2.mp3`, `traccia 3.mp3`, ...

Perfetto per registrare la radio, una playlist o una cassetta digitale e permettere di trovare le canzoni.

```bash
# Trasmissioni radio: dopo 10 s di silenzio → nuovo MP3
python pausarec.py --silence 10 -d "Radio Europa FM" --duration 3600

# Regola la soglia di silenzio (rumore di fondo alto → alza la soglia)
python pausarec.py --silence 5 --threshold 0.01
```

Comportamento del silenzio:

- **Prima del primo audio** → scartato: non vengono mai create tracce vuote
- **Pausa breve (sotto `--silence` secondi) dentro una traccia** → tenuta: resta una pausa naturale del brano
- **Chiusura traccia** → viene tenuta solo una coda di ~1 s, il resto del silenzio è scartato
- Il device audio viene aperto **una sola volta** per tutta la sessione: nessun frammento audio va perso tra una traccia e l'altra
- Se la cartella contiene già tracce da una sessione precedente, la numerazione **riparte dal numero successivo** (`traccia 7.mp3`, `traccia 8.mp3`, ...): i file esistenti non vengono mai sovrascritti

Durante la registrazione la riga di stato mostra la traccia corrente e il silenzio accumulato:

```
● REC  ⏱ 03:41  |  traccia   4  |  silenzio  2.3/5 s
  ✔ Traccia 4 salvata (03:35, 4.92 MB) -> Radio Europa FM\traccia 4.mp3
```

Combinabile con `--duration` (si ferma da solo dopo N secondi, salvando anche l'ultima traccia parziale).

### Elencare le sorgenti audio disponibili

```bash
python pausarec.py --list
```

Esempio di output su un sistema tipico:

```
Sorgenti audio (loopback) disponibili:

  0: [LOOPBACK] Altoparlanti (FxSound Audio Enhancer) (predefinita)
  1: [LOOPBACK] Speakers (Realtek(R) Audio)
  2: [MICROFONO] Microphone Array (Realtek(R) Audio) (predefinita)
```

### Opzioni disponibili

| Opzione | Descrizione | Predefinito |
|---|---|---|
| `-o, --output FILE` | Nome del file MP3 di destinazione | `pausarec_<data>.mp3` |
| `--device N` | Indice della sorgente audio da usare (vedi `--list`) | sorgente predefinita |
| `--bitrate KBPS` | Bitrate MP3: `128`, `192`, `320`, ecc. | `192` |
| `--samplerate HZ` | Frequenza di campionamento | `48000` |
| `--channels N` | `1` = mono, `2` = stereo | `2` |
| `--duration SEC` | Ferma automaticamente la registrazione dopo N secondi | (nessun limite) |
| `--silence SEC` | Modalità a tracce: dopo N secondi di silenzio chiude l'MP3 corrente e ne apre uno nuovo (`traccia 1.mp3`, `traccia 2.mp3`, ...), tutti salvati in una cartella | (disattivata) |
| `--threshold AMP` | Soglia RMS di silenzio in modalità `--silence`, da `0.0` a `1.0` (0.005 ≈ -46 dB) | `0.005` |
| `-d, --output-dir CARTELLA` | Cartella delle tracce in modalità `--silence` | `pausarec_<data>` |
| `--list` | Elenca le sorgenti audio disponibili ed esce | — |
| `-h, --help` | Aiuto con tutte le opzioni | — |

### Esempi

```bash
# Il tuo "mixtape" di oggi
python pausarec.py -o mixtape_lunedi.mp3

# Registra dal device Realtek (indice 1 dell'elenco)
python pausarec.py --device 1

# Registra 60 secondi con bitrate alto e si ferma da sola
python pausarec.py --duration 60 --bitrate 320

# Registra in 44,1 kHz (ideale per musica)
python pausarec.py --samplerate 44100

# Tracce automatiche: un nuovo MP3 dopo 5 s di silenzio, nella cartella "Mixtape"
python pausarec.py --silence 5 -d Mixtape
```

---

## Come funziona

1. Uso la libreria **soundcard** per aprire un recorder sul dispositivo di **uscita** (loopback WASAPI): cattura l'audio che sta già suonando, come lo senti tu.
2. Legge blocchi di ~100 ms di audio in formato `float32` (`-1.0` … `1.0`) e li converte in **PCM int16**.
3. Ogni blocco viene codificato in **MP3 al volo** (in memoria) con **lameenc**.
4. Alla fine (con `Ctrl+C` o dopo `--duration` secondi) il flusso MP3 viene finalizzato e scritto su disco.

Con `--silence SEC` si aggiunge la **modalità a tracce**: per ogni blocco viene calcolato l'RMS (media quadratica) dei campioni. Se resta sotto la soglia `--threshold` per SEC secondi consecutivi, la traccia corrente viene chiusa con `flush()` di lameenc, salvata come `traccia N.mp3` e ne parte una nuova con un encoder fresco — mentre il recorder loopback resta aperto e non perde un solo campione.

---

## Risoluzione dei problemi

**"Nessuna sorgente loopback trovata"**
→ Su Windows dovrebbero esserci almeno i loopback degli Speaker. Verifica con `--list`.

**"Indice device non valido"**
→ Usa `python pausarec.py --list` per vedere gli indici validi.

**Il file MP3 è vuoto / non suona**
→ Su Windows 10/11 vai in **Impostazioni → Privacy e sicurezza → Microfono** e attiva la voce *"Consenti alle app desktop di accedere al microfono"* (il loopback è trattato come registrazione).

**"SoundcardRuntimeWarning: data discontinuity in recording"**
→ È un avviso della libreria **soundcard**, non un errore: il loopback WASAPI segnala un salto nei timestamp di capture che di solito si verifica all'avvio dello stream e durante il silenzio (quando nessuna app suona, Windows sospende momentaneamente l'engine di capture). La registrazione prosegue normalmente e i file salvati sono regolari; lo script silenzia da solo questo avviso per non inquinare l'output.

**Non sto registrando la sorgente giusta**
→ Potresti avere più di un'uscita audio (es. "FxSound Audio Enhancer" *e* "Realtek"). Registra esattamente sul device su cui stai riproducendo: usa `--device N` con l'indice giusto di `--list`.

**Errore all'avvio**
→ Controlla che le dipendenze siano installate (`pip install -r requirements.txt`).

---

## Struttura del progetto

```
PausaREC/
├── pausarec.py        # script principale
├── requirements.txt   # dipendenze Python
├── Readme.md          # questo file
└── pausarec_<data>/   # cartelle tracce create dalla modalità --silence
```

---

## Licenza

Uso libero — senza restrizioni. Le librerie usate sono open source (soundcard — BSD, lameenc — LGPL bundling di LAME, numpy — BSD).
