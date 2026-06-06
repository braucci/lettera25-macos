# Changelog

Tutte le modifiche degne di nota sono documentate qui, in accordo con
[Keep a Changelog](https://keepachangelog.com/it-IT/1.1.0/).

## [1.3.0] — 2026-06-06

### Added

- **Imperfezioni analogiche regolabili** con due slider nell'interfaccia:
  - *Imperfezioni* (brokenness): erosione casuale dei glifi da nastro
    secco, jitter extra di battuta, flecks e peli di nastro sul foglio.
  - *Nastro rosso*: simulazione del nastro bicolore nero/rosso. Un glifo
    può uscire tutto rosso, rosso-sopra/nero-sotto (slug a cavallo della
    frontiera fra le bande) o con una sbavatura rossa tenue (nastro
    "pizzicato").
- **`core.py`**: nuovi parametri `brokenness` e `red_ribbon` in
  `render_sentence`/`render_sentence_tight` (default `None` ⇒ usa il
  profilo, che vale 0 ⇒ comportamento invariato); helper `_tint`,
  `_split_red_black`, `_red_smudge`, `_scatter_dirt` e costante `RIBBON_RED`.

### Notes

- Le invarianti di determinismo restano valide: con intensità 0 non viene
  consumato alcun numero casuale aggiuntivo, quindi seed fisso ⇒ pixel
  identici e il profilo "poesia" resta deterministico anche senza seed.

## [1.2.0] — 2026-06-06

### Added

- **Selettore Font ora funzionante** con più famiglie typewriter. Due font
  sono impacchettati nel bundle (autoportante, indipendente dal sistema):
  **Courier Prime** (SIL OFL 1.1) e **Special Elite** (Apache 2.0). Si
  aggiungono i font typewriter/monospazio di macOS se presenti (Courier,
  Courier New, American Typewriter, Menlo, Monaco).
- **Auto-discovery dei font**: qualunque `.ttf/.otf/.ttc` collocato in
  `assets/fonts/` compare automaticamente nel menu, senza modifiche al codice.
- `assets/fonts/` con i file dei font e i rispettivi testi di licenza, inclusi
  nel bundle via `DATA_FILES`.

### Changed

- `app.py`: rimosso il vecchio `find_best_font()` come unica sorgente (resta
  come rete di sicurezza); introdotto `build_font_list()` e il getter
  `_getFontPath()`; il rendering usa il font selezionato anziché uno fisso.

## [1.1.0] — 2026-06-06

### Added

- **Selettore di sfondo del foglio** nella riga dei parametri: `Profilo`
  (default, usa il `paper_color` calibrato del profilo), `Bianco`
  (255,255,255) e `Avorio` (248,240,222). La scelta sovrascrive solo il
  colore della carta; la fisica dell'inchiostro (profilo) resta invariata.
- **`core.py`**: nuove costanti `PAPER_BIANCO` e `PAPER_AVORIO` e parametro
  opzionale `paper_color` in `render_sentence` e `render_sentence_tight`
  (default `None` ⇒ comportamento precedente preservato).

## [1.0.1] — 2026-06-04

### Fixed

- **`build.sh`**: cercava il bundle prodotto da py2app come
  `Lettera25.app` (senza spazio), mentre py2app lo produce come
  `Lettera 25.app` (con spazio, derivato da `CFBundleName`). Lo script
  ora cerca il nome corretto e differenzia chiaramente il nome del
  bundle (con spazio) dal nome dell'eseguibile interno (senza spazio,
  da `CFBundleExecutable`).
- Lo script aggiunge ora un `ls` diagnostico di `dist/` quando il
  bundle non viene trovato, per facilitare la diagnosi.

### Changed

- README ristrutturato per pubblicazione GitHub: badge, sezioni "Cosa
  fa" e "Compilazione passo passo" con verifiche di controllo a ogni
  passo, sezione troubleshooting esplicita.

## [1.0.0] — 2026-06-04

### Added

- Prima release pubblica del porting macOS.
- Tre profili di rendering: **Lettera 25** (calibrato su macchina
  reale), **Poesia** (stampa digitale pulita), **Vintage** (macchina
  usurata).
- Modello fisico a sette fenomeni: gioco del carrello, usura del
  perno, variabilità pressione, disomogeneità del nastro, diffusione
  nei contro-grafemi, bleed sub-pixel, ghosting da rimbalzo.
- Interfaccia Cocoa nativa via PyObjC con AppDelegate, finestra fissa
  (card), supporto Dark Mode.
- Pacchettizzazione `.app` standalone via py2app.
- Icona squircle Big Sur+ con 10 risoluzioni canoniche Apple.
- Cinque sanity check del solutore con invarianti del dominio,
  eseguibili con `python core.py`.

### Fixed dal primo prototipo

- **Determinismo del seed**: il contatore globale `_glyph_counter` del
  motore di rendering non veniva azzerato a ogni chiamata, rompendo
  la riproducibilità. Bug scoperto dai sanity check stessi.

---

[1.0.1]: https://github.com/braucci/lettera25-macos/releases/tag/v1.0.1
[1.0.0]: https://github.com/braucci/lettera25-macos/releases/tag/v1.0.0
