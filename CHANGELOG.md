# Changelog

Tutte le modifiche degne di nota sono documentate qui, in accordo con
[Keep a Changelog](https://keepachangelog.com/it-IT/1.1.0/).

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
