# Stato delle immagini in docs/

Questo file documenta lo stato delle immagini referenziate dal README.
Cancellalo quando avrai sostituito tutti i placeholder.

## ✓ Già presenti

| File | Cos'è |
|------|-------|
| `icon.png` | Icona dell'app a 256×256 (renderizzata da `assets/icon.svg`) |
| `sample_app.png` | Output dell'app — testo *Colapesce, Dimartino* |
| `sample_poesia.png` | Output dell'app — Emily Dickinson, profilo poesia |
| `screenshot_ui.png` | Mockup dell'interfaccia (SVG → PNG 2x retina) |
| `screenshot_ui.svg` | Sorgente vettoriale del mockup |

## ⚠ Da aggiungere

| File | Cosa serve |
|------|-----------|
| `sample_real.jpg` | **Foto della tua battitura reale** sulla Olivetti Lettera 25 |

Usa preferibilmente la foto del testo *Colapesce/Dimartino* battuta sulla
Olivetti reale: corrisponde esattamente a `sample_app.png` e permette il
confronto diretto nel README.

Specifiche tecniche consigliate:
- Lato lungo: 1200–1600 px
- Peso: sotto i 500 KB (JPEG qualità 85)
- Inquadratura: il testo dovrebbe occupare il 70-80% del frame

## 🔄 Da sostituire (consigliato)

| File | Perché sostituirlo |
|------|-------------------|
| `screenshot_ui.png` | È un mockup SVG. Una volta avviata l'app sul Mac, sostituiscilo con uno screenshot reale: `screencapture -w docs/screenshot_ui.png` poi clicca sulla finestra dell'app |

## Comandi utili

Rigenerare l'icona PNG dal sorgente SVG (richiede `librsvg` o Inkscape):

```bash
# Con librsvg (brew install librsvg)
rsvg-convert -w 256 -h 256 assets/icon.svg -o docs/icon.png

# Con sips (nativo macOS, partendo dal .icns)
sips -z 256 256 assets/icon.icns --out docs/icon.png
```

Rigenerare lo screenshot UI dal sorgente SVG:

```bash
rsvg-convert -w 1120 -h 1560 docs/screenshot_ui.svg -o docs/screenshot_ui.png
```
