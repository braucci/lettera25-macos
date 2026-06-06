"""
app.py — Interfaccia Cocoa nativa per Olivetti Lettera 25 su macOS.

Costruita con PyObjC e AppKit (no toolkit cross-platform). Si appoggia
al modulo `core` per la logica di dominio: la presentazione e' separata
dal solutore, come si separa il post-processore da un solutore CFD.

Pattern adottati
----------------

  • AppDelegate classico: un'unica classe `AppDelegate(NSObject)` che
    risponde a `applicationDidFinishLaunching_:` costruendo finestra
    e controlli, e ai target/action dei pulsanti.

  • Finestra fissa (card): minSize == maxSize, niente
    NSWindowStyleMaskResizable. Posizionamento dei controlli a
    coordinate assolute - legittimo perche' la finestra non si ridimensiona.

  • Selettori vs helper:
      - i metodi terminanti con `_` sono selettori Cocoa veri,
        NON decorati;
      - tutti gli altri helper sono decorati con `@objc.python_method`
        per evitare BadPrototypeError del bridge;
      - le funzioni utility senza self sono fuori dalla classe.

  • Flusso PIL -> NSImage in memoria, senza file temporanei:
        PIL.Image -> bytes PNG -> NSData -> NSImage -> NSImageView

  • Pulsante "Copia immagine" obbligatorio (linee guida): copia il PNG
    nella pasteboard di sistema, cosi' l'utente puo' incollare
    direttamente in Pages/Mail/Slack senza salvare.
"""

import io
import os
import subprocess
import sys

import objc
from Cocoa import (
    NSApplication,
    NSApp,
    NSObject,
    NSWindow,
    NSView,
    NSTextField,
    NSTextView,
    NSScrollView,
    NSButton,
    NSPopUpButton,
    NSStepper,
    NSSlider,
    NSImageView,
    NSImage,
    NSData,
    NSPasteboard,
    NSPasteboardTypePNG,
    NSAlert,
    NSSavePanel,
    NSColor,
    NSFont,
    NSFontAttributeName,
    NSMakeRect,
    NSMakeSize,
    NSMakePoint,
    NSBackingStoreBuffered,
    NSWindowStyleMaskTitled,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskMiniaturizable,
    NSBezelStyleRounded,
    NSButtonTypeSwitch,
    NSImageScaleProportionallyUpOrDown,
    NSImageAlignCenter,
    NSImageFrameGrayBezel,
    NSModalResponseOK,
    NSAlertFirstButtonReturn,
    NSAlertStyleWarning,
)

from PIL import ImageFont

import core


# =============================================================
#   Funzioni di utilita' (livello modulo, niente self)
# =============================================================
#
# Sono pure: non manipolano stato della UI. Vivono fuori dalla
# classe AppDelegate proprio per evitare confusioni col bridge
# PyObjC (vedi linee guida sui selettori).


def find_best_font():
    """
    Restituisce (font_path, font_family) cercando il miglior monospazio
    serif disponibile sul Mac, in ordine di preferenza.

    Su macOS usiamo `mdfind` come fallback se il font non e' in una
    directory standard, ma in primis lavoriamo per pattern di nome.
    """
    candidates = [
        ("Courier Prime",     ["CourierPrime-Regular.ttf"]),
        ("Courier New",       ["Courier New.ttf"]),
        ("Courier",           ["Courier.dfont", "Courier.ttc"]),
        ("Menlo",             ["Menlo-Regular.ttf"]),
        ("Monaco",            ["Monaco.ttf"]),
        ("SF Mono",           ["SFNSMono.ttf", "SF-Mono-Regular.otf"]),
    ]

    search_dirs = [
        os.path.expanduser("~/Library/Fonts"),
        "/Library/Fonts",
        "/System/Library/Fonts",
        "/System/Library/Fonts/Supplemental",
    ]

    for family, filenames in candidates:
        for d in search_dirs:
            for fn in filenames:
                p = os.path.join(d, fn)
                if os.path.exists(p):
                    return p, family

    # Ultimo tentativo: cerca con find
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for entry in os.listdir(d):
            low = entry.lower()
            if low.endswith((".ttf", ".otf", ".ttc")) and "mono" in low:
                return os.path.join(d, entry), entry

    raise RuntimeError(
        "Nessun font monospazio trovato sul sistema. "
        "Installare almeno Courier Prime o Menlo."
    )


# -------------------------------------------------------------
#   Registro dei font: impacchettati nel bundle + di sistema
# -------------------------------------------------------------
#
# Filosofia: il bundle e' autoportante. I font typewriter distintivi
# (Courier Prime, Special Elite) viaggiano DENTRO l'app, in
# assets/fonts/, e non dipendono da cosa l'utente ha installato — come
# un velivolo porta a bordo i propri strumenti invece di assumere che
# siano gia' in pista. In piu' si offrono i font typewriter/monospazio
# che corredano macOS, se presenti.
#
# AUTO-DISCOVERY: qualunque .ttf/.otf/.ttc aggiunto in assets/fonts/
# compare automaticamente nel menu, senza toccare il codice.

BUNDLED_FONT_EXTS = (".ttf", ".otf", ".ttc")

# (etichetta, nomi-file candidati) per i font che corredano macOS.
SYSTEM_FONT_CANDIDATES = [
    ("Courier",             ["Courier.ttc", "Courier.dfont"]),
    ("Courier New",         ["Courier New.ttf"]),
    ("American Typewriter", ["AmericanTypewriter.ttc"]),
    ("Menlo",               ["Menlo.ttc", "Menlo-Regular.ttf"]),
    ("Monaco",              ["Monaco.ttf"]),
]

SYSTEM_FONT_DIRS = [
    os.path.expanduser("~/Library/Fonts"),
    "/Library/Fonts",
    "/System/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
]


def _bundled_fonts_dir():
    """
    Individua la cartella assets/fonts/ sia in sviluppo (accanto ad
    app.py) sia dentro il bundle .app (Contents/Resources/assets/fonts).
    Restituisce il primo percorso esistente, o None.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    exe = (os.path.dirname(os.path.abspath(sys.argv[0]))
           if sys.argv and sys.argv[0] else here)
    candidates = [
        os.path.join(here, "assets", "fonts"),                     # dev
        os.path.join(exe, "..", "Resources", "assets", "fonts"),   # bundle
        os.path.join(here, "..", "Resources", "assets", "fonts"),
    ]
    for d in candidates:
        d = os.path.normpath(d)
        if os.path.isdir(d):
            return d
    return None


def _font_label(path, fallback):
    """Nome di famiglia del font (via Pillow); fallback al nome-file."""
    try:
        family, _ = ImageFont.truetype(path, 16).getname()
        return family or fallback
    except Exception:
        return fallback


def build_font_list():
    """
    Lista ordinata (etichetta, percorso) dei font disponibili:
    prima quelli impacchettati (auto-discovery), poi quelli di sistema.
    De-duplica per etichetta. Garantisce almeno una voce.
    """
    fonts = []
    seen = set()

    fdir = _bundled_fonts_dir()
    if fdir:
        for fn in sorted(os.listdir(fdir)):
            if fn.lower().endswith(BUNDLED_FONT_EXTS):
                p = os.path.join(fdir, fn)
                label = _font_label(p, os.path.splitext(fn)[0])
                if label not in seen:
                    fonts.append((label, p))
                    seen.add(label)

    for label, filenames in SYSTEM_FONT_CANDIDATES:
        if label in seen:
            continue
        for d in SYSTEM_FONT_DIRS:
            hit = next((os.path.join(d, fn) for fn in filenames
                        if os.path.exists(os.path.join(d, fn))), None)
            if hit:
                fonts.append((label, hit))
                seen.add(label)
                break

    if not fonts:                       # rete di sicurezza
        p, fam = find_best_font()
        fonts.append((fam, p))
    return fonts


def pil_to_nsimage(pil_img):
    """
    Converte un'immagine Pillow in NSImage senza scrivere su disco.

    Flusso: PIL.Image -> PNG bytes -> NSData -> NSImage.
    """
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG", optimize=False)
    png_bytes = buf.getvalue()
    data = NSData.dataWithBytes_length_(png_bytes, len(png_bytes))
    return NSImage.alloc().initWithData_(data), png_bytes


def pil_to_pasteboard(pil_img):
    """
    Copia un'immagine PIL nella pasteboard di sistema come PNG.
    """
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG", optimize=True)
    png_bytes = buf.getvalue()
    data = NSData.dataWithBytes_length_(png_bytes, len(png_bytes))

    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setData_forType_(data, NSPasteboardTypePNG)


# =============================================================
#   Costanti di layout (finestra fissa)
# =============================================================

WIN_W = 560
WIN_H = 780

# Margini globali
M = 16

# Profili e formati (ordine = indici della popup)
PROFILE_LABELS = ["Lettera 25", "Poesia", "Vintage"]
PROFILE_KEYS   = ["lettera25",  "poesia", "vintage"]

PAPER_PRESETS = [
    ("Portrait 4:5 (1200x1500)",  (1200, 1500)),
    ("Portrait A4 (1240x1754)",   (1240, 1754)),
    ("Quadrato (1200x1200)",      (1200, 1200)),
    ("Landscape (1500x1200)",     (1500, 1200)),
    ("Adattivo (autofit)",        None),
]

# Sfondo del foglio (ordine = indici della popup).
# Indice 0 = None -> usa il `paper_color` calibrato del profilo (default,
# comportamento invariato). Gli altri due sovrascrivono il foglio.
BG_LABELS = ["Profilo", "Bianco", "Avorio"]
BG_COLORS = [None, core.PAPER_BIANCO, core.PAPER_AVORIO]


# =============================================================
#   AppDelegate
# =============================================================

class AppDelegate(NSObject):

    # ---------- stato (annotato per chiarezza) ----------
    # window:       NSWindow
    # textView:     NSTextView      input testo
    # profilePop:   NSPopUpButton   selettore profilo
    # fontPop:      NSPopUpButton   selettore font (Courier Prime ecc.)
    # paperPop:     NSPopUpButton   selettore formato foglio
    # sizeField:    NSTextField     dim. font
    # widthField:   NSTextField     larghezza testo
    # vanchorField: NSTextField     posizione verticale
    # seedField:    NSTextField     seed
    # seedCheck:    NSButton        checkbox "usa seed"
    # imageView:    NSImageView     anteprima
    # generateBtn:  NSButton
    # saveBtn:      NSButton
    # copyBtn:      NSButton
    # currentImage: PIL.Image|None  ultima immagine generata
    # currentBytes: bytes|None      ultimo PNG generato
    # fontPath:     str             percorso del font selezionato
    # fontFamily:   str             famiglia del font

    # =================================================
    #   Ciclo di vita Cocoa
    # =================================================

    def applicationDidFinishLaunching_(self, notification):
        # Costruisci il registro dei font (bundled + di sistema)
        try:
            self.fonts = build_font_list()
        except Exception as exc:
            self._fatalAlert(f"Errore di inizializzazione: {exc}")
            NSApp.terminate_(self)
            return

        self.currentImage = None
        self.currentBytes = None

        self._buildWindow()
        self._buildControls()
        self.window.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)

    def applicationShouldTerminateAfterLastWindowClosed_(self, sender):
        return True

    # =================================================
    #   Selettori target/action (terminano con `_`)
    # =================================================

    def generateClicked_(self, sender):
        self._renderPreview()

    def saveClicked_(self, sender):
        self._saveToFile()

    def copyClicked_(self, sender):
        if self.currentImage is None:
            self._infoAlert("Genera prima un'immagine.")
            return
        try:
            pil_to_pasteboard(self.currentImage)
            self._infoAlert("Immagine copiata negli appunti.")
        except Exception as exc:
            self._infoAlert(f"Errore copia: {exc}")

    def sliderChanged_(self, sender):
        self.brkValue.setStringValue_(str(int(self.brkSlider.floatValue())))
        self.redValue.setStringValue_(str(int(self.redSlider.floatValue())))

    # =================================================
    #   Helper Python (decoratore obbligatorio)
    # =================================================

    @objc.python_method
    def _buildWindow(self):
        style = (
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskMiniaturizable
            # NSWindowStyleMaskResizable volutamente assente: card fissa
        )
        rect = NSMakeRect(0, 0, WIN_W, WIN_H)
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, style, NSBackingStoreBuffered, False
        )
        self.window.setTitle_("Olivetti Lettera 25")
        # Card vera: min == max
        size = NSMakeSize(WIN_W, WIN_H)
        self.window.setMinSize_(size)
        self.window.setMaxSize_(size)
        self.window.center()

    @objc.python_method
    def _buildControls(self):
        content = self.window.contentView()
        y = WIN_H  # parto dall'alto e scendo

        # ---- 1. Label "Testo da imprimere" ----
        y -= 30
        content.addSubview_(
            self._label("Testo da imprimere:", M, y, WIN_W - 2*M, 20, bold=True)
        )

        # ---- 2. TextView in ScrollView ----
        y -= 130
        scroll = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(M, y, WIN_W - 2*M, 120)
        )
        scroll.setHasVerticalScroller_(True)
        scroll.setBorderType_(2)  # NSBezelBorder
        scroll.setAutohidesScrollers_(True)

        self.textView = NSTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, WIN_W - 2*M, 120)
        )
        self.textView.setFont_(NSFont.systemFontOfSize_(13))
        self.textView.setRichText_(False)
        self.textView.setString_(
            "L'acqua \u00e8 insegnata dalla sete.\n"
            "La terra, dagli oceani traversati.\n"
            "La gioia, dal dolore.\n"
            "La pace, dai racconti di battaglia.\n"
            "L'amore da un'impronta di memoria.\n"
            "Gli uccelli, dalla neve.\n"
            "\n"
            "- Emily Dickinson"
        )
        scroll.setDocumentView_(self.textView)
        content.addSubview_(scroll)

        # ---- 3. Riga: Profilo / Font / Formato ----
        y -= 36
        col_w = (WIN_W - 2*M - 16) // 3
        x = M

        content.addSubview_(self._label("Profilo:", x, y + 14, col_w, 16))
        self.profilePop = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(x, y - 6, col_w, 26), False
        )
        for label in PROFILE_LABELS:
            self.profilePop.addItemWithTitle_(label)
        self.profilePop.selectItemAtIndex_(0)
        content.addSubview_(self.profilePop)

        x += col_w + 8
        content.addSubview_(self._label("Font:", x, y + 14, col_w, 16))
        self.fontPop = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(x, y - 6, col_w, 26), False
        )
        for label, _ in self.fonts:
            self.fontPop.addItemWithTitle_(label)
        self.fontPop.selectItemAtIndex_(0)
        content.addSubview_(self.fontPop)

        x += col_w + 8
        content.addSubview_(self._label("Formato:", x, y + 14, col_w, 16))
        self.paperPop = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(x, y - 6, col_w, 26), False
        )
        for label, _ in PAPER_PRESETS:
            self.paperPop.addItemWithTitle_(label)
        self.paperPop.selectItemAtIndex_(0)
        content.addSubview_(self.paperPop)

        # ---- 4. Riga parametri numerici ----
        y -= 50
        small_w = 60
        x = M

        content.addSubview_(self._label("Dim. font:", x, y + 6, 70, 16))
        self.sizeField = self._numField(x + 72, y, small_w, "28")
        content.addSubview_(self.sizeField)

        x = M + 150
        content.addSubview_(self._label("Largh. %:", x, y + 6, 65, 16))
        self.widthField = self._numField(x + 67, y, small_w, "78")
        content.addSubview_(self.widthField)

        x = M + 300
        content.addSubview_(self._label("V-anchor:", x, y + 6, 65, 16))
        self.vanchorField = self._numField(x + 67, y, small_w, "0.42")
        content.addSubview_(self.vanchorField)

        # ---- 4b. Riga imperfezioni (nastro reale) ----
        y -= 40
        content.addSubview_(self._label("Imperfezioni:", M, y + 4, 86, 16))
        self.brkSlider = NSSlider.alloc().initWithFrame_(
            NSMakeRect(M + 88, y, 130, 22)
        )
        self.brkSlider.setMinValue_(0.0)
        self.brkSlider.setMaxValue_(100.0)
        self.brkSlider.setFloatValue_(0.0)
        self.brkSlider.setContinuous_(True)
        self.brkSlider.setTarget_(self)
        self.brkSlider.setAction_(objc.selector(self.sliderChanged_, signature=b"v@:@"))
        content.addSubview_(self.brkSlider)
        self.brkValue = self._label("0", M + 222, y + 4, 30, 16)
        content.addSubview_(self.brkValue)

        x = M + 268
        content.addSubview_(self._label("Nastro rosso:", x, y + 4, 86, 16))
        self.redSlider = NSSlider.alloc().initWithFrame_(
            NSMakeRect(x + 90, y, 118, 22)
        )
        self.redSlider.setMinValue_(0.0)
        self.redSlider.setMaxValue_(100.0)
        self.redSlider.setFloatValue_(0.0)
        self.redSlider.setContinuous_(True)
        self.redSlider.setTarget_(self)
        self.redSlider.setAction_(objc.selector(self.sliderChanged_, signature=b"v@:@"))
        content.addSubview_(self.redSlider)
        self.redValue = self._label("0", x + 212, y + 4, 30, 16)
        content.addSubview_(self.redValue)

        # ---- 5. Riga seed ----
        y -= 32
        content.addSubview_(self._label("Seed:", M, y + 6, 40, 16))
        self.seedField = self._numField(M + 42, y, small_w, "0")
        content.addSubview_(self.seedField)

        self.seedCheck = NSButton.alloc().initWithFrame_(
            NSMakeRect(M + 110, y + 2, 90, 22)
        )
        self.seedCheck.setButtonType_(NSButtonTypeSwitch)
        self.seedCheck.setTitle_("usa seed")
        self.seedCheck.setState_(0)
        content.addSubview_(self.seedCheck)

        # Selettore sfondo del foglio (Profilo / Bianco / Avorio)
        content.addSubview_(self._label("Sfondo:", M + 208, y + 6, 52, 16))
        self.bgPop = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(M + 262, y - 2, 98, 26), False
        )
        for label in BG_LABELS:
            self.bgPop.addItemWithTitle_(label)
        self.bgPop.selectItemAtIndex_(0)   # 0 = Profilo (default invariato)
        content.addSubview_(self.bgPop)

        # Pulsante Genera a destra
        gen_w = 160
        self.generateBtn = NSButton.alloc().initWithFrame_(
            NSMakeRect(WIN_W - M - gen_w, y - 2, gen_w, 30)
        )
        self.generateBtn.setTitle_("Genera immagine")
        self.generateBtn.setBezelStyle_(NSBezelStyleRounded)
        self.generateBtn.setKeyEquivalent_("\r")  # Invio
        self.generateBtn.setTarget_(self)
        self.generateBtn.setAction_(objc.selector(self.generateClicked_, signature=b"v@:@"))
        content.addSubview_(self.generateBtn)

        # ---- 6. Label "Anteprima" ----
        y -= 32
        content.addSubview_(
            self._label("Anteprima:", M, y, WIN_W - 2*M, 20, bold=True)
        )

        # ---- 7. NSImageView per anteprima ----
        preview_h = 340
        y -= preview_h + 8
        self.imageView = NSImageView.alloc().initWithFrame_(
            NSMakeRect(M, y, WIN_W - 2*M, preview_h)
        )
        self.imageView.setImageScaling_(NSImageScaleProportionallyUpOrDown)
        self.imageView.setImageAlignment_(NSImageAlignCenter)
        self.imageView.setImageFrameStyle_(NSImageFrameGrayBezel)
        self.imageView.setEditable_(False)
        content.addSubview_(self.imageView)

        # ---- 8. Pulsanti Salva / Copia in basso ----
        y -= 44
        btn_w = 140
        # Salva
        self.saveBtn = NSButton.alloc().initWithFrame_(
            NSMakeRect(M, y, btn_w, 30)
        )
        self.saveBtn.setTitle_("Salva su file\u2026")
        self.saveBtn.setBezelStyle_(NSBezelStyleRounded)
        self.saveBtn.setTarget_(self)
        self.saveBtn.setAction_(objc.selector(self.saveClicked_, signature=b"v@:@"))
        content.addSubview_(self.saveBtn)

        # Copia (obbligatorio dalle linee guida)
        self.copyBtn = NSButton.alloc().initWithFrame_(
            NSMakeRect(M + btn_w + 10, y, btn_w, 30)
        )
        self.copyBtn.setTitle_("Copia immagine")
        self.copyBtn.setBezelStyle_(NSBezelStyleRounded)
        self.copyBtn.setTarget_(self)
        self.copyBtn.setAction_(objc.selector(self.copyClicked_, signature=b"v@:@"))
        content.addSubview_(self.copyBtn)

    @objc.python_method
    def _label(self, text, x, y, w, h, bold=False):
        lbl = NSTextField.alloc().initWithFrame_(NSMakeRect(x, y, w, h))
        lbl.setStringValue_(text)
        lbl.setBezeled_(False)
        lbl.setDrawsBackground_(False)
        lbl.setEditable_(False)
        lbl.setSelectable_(False)
        if bold:
            lbl.setFont_(NSFont.boldSystemFontOfSize_(13))
        else:
            lbl.setFont_(NSFont.systemFontOfSize_(12))
        return lbl

    @objc.python_method
    def _numField(self, x, y, w, default):
        f = NSTextField.alloc().initWithFrame_(NSMakeRect(x, y, w, 22))
        f.setStringValue_(default)
        f.setAlignment_(2)  # NSTextAlignmentRight
        return f

    @objc.python_method
    def _getText(self):
        return self.textView.string().strip()

    @objc.python_method
    def _getProfile(self):
        return PROFILE_KEYS[self.profilePop.indexOfSelectedItem()]

    @objc.python_method
    def _getPaper(self):
        return PAPER_PRESETS[self.paperPop.indexOfSelectedItem()][1]

    @objc.python_method
    def _getBackground(self):
        return BG_COLORS[self.bgPop.indexOfSelectedItem()]

    @objc.python_method
    def _getFontPath(self):
        idx = self.fontPop.indexOfSelectedItem()
        if 0 <= idx < len(self.fonts):
            return self.fonts[idx][1]
        return self.fonts[0][1]

    @objc.python_method
    def _readFloat(self, field, default):
        try:
            return float(field.stringValue().replace(",", "."))
        except (ValueError, TypeError):
            return default

    @objc.python_method
    def _readInt(self, field, default):
        try:
            return int(float(field.stringValue().replace(",", ".")))
        except (ValueError, TypeError):
            return default

    @objc.python_method
    def _renderPreview(self):
        text = self._getText()
        if not text:
            self._infoAlert("Inserisci almeno una frase.")
            return

        profile = self._getProfile()
        paper = self._getPaper()
        background = self._getBackground()
        font_path = self._getFontPath()
        brokenness = self.brkSlider.floatValue() / 100.0
        red_ribbon = self.redSlider.floatValue() / 100.0
        font_size = max(8, self._readInt(self.sizeField, 28))
        width_ratio = max(0.2, min(0.95,
                                   self._readFloat(self.widthField, 78) / 100.0))
        v_anchor = max(0.05, min(0.95,
                                 self._readFloat(self.vanchorField, 0.42)))
        seed = (self._readInt(self.seedField, 0)
                if self.seedCheck.state() else None)

        try:
            if paper is None:
                # Adattivo
                max_w = int(font_size * 22)
                img = core.render_sentence_tight(
                    text,
                    font_path=font_path,
                    font_size=font_size,
                    profile_name=profile,
                    max_width=max_w,
                    paper_color=background,
                    brokenness=brokenness,
                    red_ribbon=red_ribbon,
                    seed=seed,
                )
            else:
                img = core.render_sentence(
                    text,
                    font_path=font_path,
                    font_size=font_size,
                    profile_name=profile,
                    paper_size=paper,
                    text_width_ratio=width_ratio,
                    vertical_anchor=v_anchor,
                    paper_color=background,
                    brokenness=brokenness,
                    red_ribbon=red_ribbon,
                    seed=seed,
                )
        except Exception as exc:
            self._infoAlert(f"Errore di rendering: {exc}")
            return

        self.currentImage = img
        nsimg, png_bytes = pil_to_nsimage(img)
        self.currentBytes = png_bytes
        self.imageView.setImage_(nsimg)

    @objc.python_method
    def _saveToFile(self):
        if self.currentImage is None:
            self._infoAlert("Genera prima un'immagine.")
            return

        panel = NSSavePanel.savePanel()
        panel.setTitle_("Salva immagine")
        panel.setNameFieldStringValue_("lettera25.png")
        panel.setAllowedFileTypes_(["png"])
        result = panel.runModal()
        if result != NSModalResponseOK:
            return

        url = panel.URL()
        if url is None:
            return
        path = url.path()
        try:
            self.currentImage.save(path, "PNG")
            self._infoAlert(f"Salvato in:\n{path}")
        except Exception as exc:
            self._infoAlert(f"Errore nel salvataggio: {exc}")

    @objc.python_method
    def _infoAlert(self, message):
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Lettera 25")
        alert.setInformativeText_(message)
        alert.addButtonWithTitle_("OK")
        alert.runModal()

    @objc.python_method
    def _fatalAlert(self, message):
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Errore irrecuperabile")
        alert.setInformativeText_(message)
        alert.setAlertStyle_(NSAlertStyleWarning)
        alert.addButtonWithTitle_("Esci")
        alert.runModal()


# =============================================================
#   Entry point
# =============================================================

def main():
    app = NSApplication.sharedApplication()
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    # Activation policy "regular" perche' e' un'app GUI completa
    app.setActivationPolicy_(0)  # NSApplicationActivationPolicyRegular
    app.run()


if __name__ == "__main__":
    main()
