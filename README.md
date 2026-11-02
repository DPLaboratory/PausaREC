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
cd C:\Develop\@Prj-Lab\AI-test\AudioRip
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
```

---

## Come funziona

1. Uso la libreria **soundcard** per aprire un recorder sul dispositivo di **uscita** (loopback WASAPI): cattura l'audio che sta già suonando, come lo senti tu.
2. Legge blocchi di ~100 ms di audio in formato `float32` (`-1.0` … `1.0`) e li converte in **PCM int16**.
3. Ogni blocco viene codificato in **MP3 al volo** (in memoria) con **lameenc**.
4. Alla fine (con `Ctrl+C` o dopo `--duration` secondi) il flusso MP3 viene finalizzato e scritto su disco.

---

## Risoluzione dei problemi

**"Nessuna sorgente loopback trovata"**
→ Su Windows dovrebbero esserci almeno i loopback degli Speaker. Verifica con `--list`.

**"Indice device non valido"**
→ Usa `python pausarec.py --list` per vedere gli indici validi.

**Il file MP3 è vuoto / non suona**
→ Su Windows 10/11 vai in **Impostazioni → Privacy e sicurezza → Microfono** e attiva la voce *"Consenti alle app desktop di accedere al microfono"* (il loopback è trattato come registrazione).

**Non sto registrando la sorgente giusta**
→ Potresti avere più di un'uscita audio (es. "FxSound Audio Enhancer" *e* "Realtek"). Registra esattamente sul device su cui stai riproducendo: usa `--device N` con l'indice giusto di `--list`.

**Errore all'avvio**
→ Controlla che le dipendenze siano installate (`pip install -r requirements.txt`).

---

## Struttura del progetto

```
AudioRip/
├── pausarec.py        # script principale
├── requirements.txt   # dipendenze Python
└── README.md          # questo file
```

---

## Licenza

Uso libero — senza restrizioni. Le librerie usate sono open source (soundcard — BSD, lameenc — LGPL bundling di LAME, numpy — BSD).
