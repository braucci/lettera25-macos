"""
typewriter.py — Motore di rendering tipografico.

Profili disponibili:

  • "poesia"    — composizione pulita su foglio, senza imperfezioni.
                  Adatto a citazioni stampate digitalmente.

  • "lettera25" — calibrato su una vera Olivetti Lettera 25 in buone
                  condizioni meccaniche. Niente jitter verticale, ma
                  forte irregolarità dell'inchiostratura intra-glifo,
                  ghosting da rimbalzo del martelletto, riempimento
                  parziale dei contro-grafemi.

  • "vintage"   — macchina usurata, nastro consumato, baseline ballerino.
                  Estetica "anni '70, lettere dattiloscritte".

Fenomeni fisici modellati nel profilo "lettera25":

  (a) Inchiostratura non uniforme intra-glifo:
      moltiplicazione del canale alpha per un campo di rumore di
      valore-noise a bassa frequenza (sostituto leggero del Perlin).

  (b) Riempimento dei contro-grafemi (o, e, a, g, p…):
      dilatazione morfologica leggera del glifo prima del bleed.

  (c) Ghosting (rimbalzo del martelletto):
      doppia impressione con offset sub-pixel e alpha ridotta.

  (d) Bleed capillare:
      sfocatura gaussiana sub-pixel (diffusione dell'inchiostro
      sulle fibre della carta — soluzione dell'equazione del calore).

  (e) Variazione per-glifo della pressione globale:
      ogni carattere ha la sua propria "spinta" complessiva.
"""

import math
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops


# =============================================================
#   SOSTITUZIONI TIPOGRAFICHE
# =============================================================

TYPOGRAPHIC_SUBSTITUTIONS = [
    ("'", "\u2019"),
    ('"', "\u201D"),
    (" - ", " \u2013 "),
    ("--", "\u2014"),
    ("...", "\u2026"),
]


def apply_typography(text):
    out = text
    for src, dst in TYPOGRAPHIC_SUBSTITUTIONS:
        out = out.replace(src, dst)
    return out


# =============================================================
#   PROFILI
# =============================================================

PROFILES = {
    "poesia": {
        "sigma_y":          0.0,
        "sigma_x":          0.0,
        "rotation_max":     0.0,
        "ink_min":          1.00,
        "ink_max":          1.00,
        "bleed_radius":     0.0,
        "line_spacing":     1.9,
        "paper_color":      (252, 251, 247),
        "ink_color":        (24, 24, 24),
        "intra_glyph_noise": 0.0,
        "dilate":           0.0,
        "ghost_alpha":      0.0,
        "ghost_offset":     (0, 0),
    },

    "lettera25": {
        # Calibrato sulla foto reale della Olivetti Lettera 25
        "sigma_y":          0.25,
        "sigma_x":          0.20,
        "rotation_max":     0.4,
        "ink_min":          0.90,    # glifi mediamente molto carichi
        "ink_max":          1.00,
        "bleed_radius":     0.8,     # diffusione un po' più decisa
        "line_spacing":     1.55,
        "paper_color":      (248, 238, 232),
        "ink_color":        (24, 22, 32),      # nero più carico
        "intra_glyph_noise": 0.30,
        "dilate":           1.00,    # ★ riempimento contro-grafemi MAX
        "ghost_alpha":      0.55,    # ★ ghost ben visibile
        "ghost_offset":     (2, 1),  # offset leggermente maggiore
    },

    "vintage": {
        "sigma_y":          1.2,
        "sigma_x":          0.6,
        "rotation_max":     1.5,
        "ink_min":          0.55,
        "ink_max":          1.00,
        "bleed_radius":     0.5,
        "line_spacing":     1.6,
        "paper_color":      (248, 240, 220),
        "ink_color":        (28, 28, 32),
        "intra_glyph_noise": 0.35,
        "dilate":           0.3,
        "ghost_alpha":      0.15,
        "ghost_offset":     (1, 1),
    },
}


# =============================================================
#   GENERATORE DI MASCHERA DI RUMORE (valore-noise leggero)
# =============================================================

def _make_noise_mask(size, strength, seed_hint=0):
    """
    Genera una maschera in scala di grigio (modalità 'L', 0..255) con
    rumore a bassa frequenza per modulare l'opacità intra-glifo.

    Algoritmo: campioniamo punti casuali su una griglia piccola
    (≈ 4×6 punti), li disegniamo come cerchi sfumati, scaliamo
    all'upscala. Risulta in un campo continuo simile al Perlin ma
    senza dipendenze esterne.

    Parametri
    ---------
    size      : (w, h) della maschera finale
    strength  : 0..1 — 0 = maschera uniforme (no rumore),
                       1 = forti zone chiare/scure
    seed_hint : varia per glifo, così ogni carattere ha rumore diverso
    """
    w, h = size
    if strength <= 0 or w < 2 or h < 2:
        return Image.new("L", size, 255)

    # Griglia di campionamento a bassa risoluzione
    gw, gh = max(3, w // 8), max(3, h // 8)
    small = Image.new("L", (gw, gh), 128)
    px = small.load()

    rng = random.Random(seed_hint)
    for j in range(gh):
        for i in range(gw):
            # Valore base con piccola varianza
            v = int(255 * (1.0 - strength) + 255 * strength * rng.random())
            px[i, j] = max(0, min(255, v))

    # Upscaling bilineare → campo continuo
    mask = small.resize(size, Image.BILINEAR)
    # Smoothing aggiuntivo per ammorbidire i confini
    mask = mask.filter(ImageFilter.GaussianBlur(radius=max(w, h) / 20.0))
    return mask


# =============================================================
#   DILATAZIONE MORFOLOGICA LEGGERA
# =============================================================

def _dilate_alpha(img, amount):
    """
    Dilata leggermente l'alpha del glifo per simulare il riempimento
    dei contro-grafemi causato dalla diffusione dell'inchiostro.

    amount ∈ [0, 1] — 0 = nessuna dilatazione, 1 = +2px circa.

    Approccio: MaxFilter (kernel 3) seguito da blur, miscelato con
    l'originale in proporzione 'amount'.
    """
    if amount <= 0:
        return img
    r, g, b, a = img.split()
    a_dilated = a.filter(ImageFilter.MaxFilter(3))
    # Blend originale ↔ dilatato
    a_new = Image.blend(a, a_dilated, amount)
    return Image.merge("RGBA", (r, g, b, a_new))


# =============================================================
#   RENDERING DEL SINGOLO GLIFO
# =============================================================

_glyph_counter = [0]   # contatore globale per seed_hint del noise


def _render_glyph(char, font, profile, pad):
    """
    Renderizza un singolo glifo applicando, nell'ordine:
      1) disegno base
      2) dilatazione morfologica (riempimento contro-grafemi)
      3) variazione di pressione globale per glifo
      4) modulazione intra-glifo con noise mask
      5) bleed gaussiano
      6) rotazione (sub-grado)

    Il canvas ha dimensioni costanti per garantire l'allineamento
    della baseline tra glifi diversi.
    """
    ascent, descent = font.getmetrics()
    full_h = ascent + descent
    advance_x = font.getlength(char)

    canvas_w = int(advance_x + 2 * pad)
    canvas_h = int(full_h + 2 * pad)

    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((pad, pad), char, font=font, fill=profile["ink_color"])

    # 2) Dilatazione (riempimento contro-grafemi)
    if profile["dilate"] > 0:
        img = _dilate_alpha(img, profile["dilate"])

    # 3) Variazione globale di pressione (per glifo)
    if profile["ink_min"] < 1.0:
        global_strength = random.uniform(profile["ink_min"], profile["ink_max"])
        if global_strength < 1.0:
            r, g, b, a = img.split()
            a = a.point(lambda v: int(v * global_strength))
            img = Image.merge("RGBA", (r, g, b, a))

    # 4) Modulazione INTRA-glifo (irregolarità dell'inchiostratura)
    if profile["intra_glyph_noise"] > 0:
        _glyph_counter[0] += 1
        noise_mask = _make_noise_mask(
            img.size,
            strength=profile["intra_glyph_noise"],
            seed_hint=_glyph_counter[0] * 9973,  # primo, per de-correlare
        )
        r, g, b, a = img.split()
        a = ImageChops.multiply(a, noise_mask)
        img = Image.merge("RGBA", (r, g, b, a))

    # 5) Bleed
    if profile["bleed_radius"] > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=profile["bleed_radius"]))

    # 6) Rotazione sub-grado
    if profile["rotation_max"] > 0:
        angle = random.uniform(-profile["rotation_max"], profile["rotation_max"])
        img = img.rotate(angle, resample=Image.BICUBIC, expand=False)

    return img, advance_x


# =============================================================
#   WORD WRAP
# =============================================================

def _wrap_text(text, font, max_width):
    paragraphs = text.split("\n")
    lines = []
    for para in paragraphs:
        if not para:
            lines.append("")
            continue
        words = para.split(" ")
        current = ""
        for w in words:
            test = w if not current else current + " " + w
            if font.getlength(test) <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = w
        if current:
            lines.append(current)
    return lines


# =============================================================
#   RENDERING DEL BLOCCO DI TESTO
# =============================================================

def _render_text_block(text, font, profile, max_width):
    """
    Renderizza il blocco di testo su immagine RGBA trasparente.

    Per ogni glifo, oltre alla stampa principale, esegue (se attivo)
    un'impressione fantasma (ghost) sfalsata di 'ghost_offset' px
    con opacità 'ghost_alpha', che simula il rimbalzo elastico del
    martelletto.
    """
    ascent, descent = font.getmetrics()
    full_h = ascent + descent
    line_height = int(full_h * profile["line_spacing"])

    pad = max(10,
              int(profile["sigma_y"] * 4),
              int(profile["sigma_x"] * 4),
              int(profile["bleed_radius"] * 4))

    lines = _wrap_text(text, font, max_width)
    if not lines:
        lines = [""]

    block_w = max_width
    block_h = len(lines) * line_height + pad
    block = Image.new("RGBA", (block_w, block_h), (0, 0, 0, 0))

    ghost_dx, ghost_dy = profile["ghost_offset"]
    ghost_alpha = profile["ghost_alpha"]

    for row, line in enumerate(lines):
        line_top_y = row * line_height
        cursor_x = 0

        for ch in line:
            if ch == " ":
                cursor_x += font.getlength(" ")
                continue

            glyph_img, advance_x = _render_glyph(ch, font, profile, pad)

            base_x = int(cursor_x - pad)
            base_y = int(line_top_y - pad)

            if profile["sigma_x"] > 0 or profile["sigma_y"] > 0:
                dx = random.gauss(0, profile["sigma_x"])
                dy = random.gauss(0, profile["sigma_y"])
                base_x += int(round(dx))
                base_y += int(round(dy))

            # Ghost (rimbalzo) — disegnato PRIMA, sotto la stampa principale
            if ghost_alpha > 0:
                r, g, b, a = glyph_img.split()
                a_ghost = a.point(lambda v: int(v * ghost_alpha))
                ghost_img = Image.merge("RGBA", (r, g, b, a_ghost))
                block.paste(
                    ghost_img,
                    (base_x + ghost_dx, base_y + ghost_dy),
                    ghost_img,
                )

            # Stampa principale
            block.paste(glyph_img, (base_x, base_y), glyph_img)

            cursor_x += advance_x

    return block, line_height, len(lines)


# =============================================================
#   COMPOSIZIONE SU FOGLIO (formato fisso)
# =============================================================

def render_sentence(text,
                    font_path,
                    font_size=28,
                    profile_name="lettera25",
                    paper_size=(1200, 1500),
                    text_width_ratio=0.78,
                    vertical_anchor=0.42,
                    apply_typo=True,
                    seed=None):
    if seed is not None:
        random.seed(seed)
    _glyph_counter[0] = 0  # reset per garantire determinismo per chiamata

    if profile_name not in PROFILES:
        raise ValueError(f"Profilo sconosciuto: {profile_name}")
    profile = PROFILES[profile_name]

    if apply_typo:
        text = apply_typography(text)

    font = ImageFont.truetype(font_path, font_size)

    paper_w, paper_h = paper_size
    text_max_width = int(paper_w * text_width_ratio)

    block, _, _ = _render_text_block(text, font, profile, text_max_width)

    paper = Image.new("RGB", paper_size, profile["paper_color"])
    paste_x = (paper_w - block.width) // 2
    block_center_y = int(paper_h * vertical_anchor)
    paste_y = block_center_y - block.height // 2
    paper.paste(block, (paste_x, paste_y), block)
    return paper


def render_sentence_tight(text,
                          font_path,
                          font_size=48,
                          profile_name="lettera25",
                          max_width=900,
                          margin=80,
                          apply_typo=True,
                          seed=None):
    if seed is not None:
        random.seed(seed)
    _glyph_counter[0] = 0  # reset per garantire determinismo per chiamata

    if profile_name not in PROFILES:
        raise ValueError(f"Profilo sconosciuto: {profile_name}")
    profile = PROFILES[profile_name]

    if apply_typo:
        text = apply_typography(text)

    font = ImageFont.truetype(font_path, font_size)
    block, _, _ = _render_text_block(text, font, profile, max_width)

    paper_w = block.width + 2 * margin
    paper_h = block.height + 2 * margin
    paper = Image.new("RGB", (paper_w, paper_h), profile["paper_color"])
    paper.paste(block, (margin, margin), block)
    return paper


# =============================================================
#   SANITY CHECK — invarianti del dominio
# =============================================================
#
# Eseguibili con:  python core.py
#
# Servono sia da test di non-regressione che da documentazione
# eseguibile: dimostrano cinque proprietà fondamentali del motore.
# Analogo alle "manufactured solutions" usate per validare i solutori
# numerici, in cui si verifica che il codice riproduca un caso noto.

if __name__ == "__main__":
    import sys
    import subprocess

    # Risolvi un font monospazio qualunque tramite fontconfig.
    # In assenza di Courier Prime, usiamo il primo monospazio del sistema.
    try:
        out = subprocess.run(
            ["fc-match", "-f", "%{file}", "monospace"],
            capture_output=True, text=True, check=True,
        )
        FONT_PATH = out.stdout.strip()
    except Exception as exc:
        print(f"Impossibile risolvere un font di test: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Font di test: {FONT_PATH}")
    print()

    # -----------------------------------------------------------
    # Invariante 1 — Determinismo con seed
    # -----------------------------------------------------------
    # Due chiamate con lo stesso seed devono produrre pixel identici.
    # E' l'analogo della riproducibilita' di una simulazione CFD:
    # stesse condizioni iniziali ⇒ stesso risultato.
    img_a = render_sentence_tight(
        "Test deterministico.",
        font_path=FONT_PATH,
        font_size=24,
        profile_name="lettera25",
        seed=42,
    )
    img_b = render_sentence_tight(
        "Test deterministico.",
        font_path=FONT_PATH,
        font_size=24,
        profile_name="lettera25",
        seed=42,
    )
    assert img_a.tobytes() == img_b.tobytes(), \
        "Invariante 1 fallita: stesso seed deve produrre pixel identici."
    print("[1/5] OK  Determinismo con seed fisso.")

    # -----------------------------------------------------------
    # Invariante 2 — Dimensioni del foglio rispettate
    # -----------------------------------------------------------
    # Analogo della conservazione della massa: l'output rispetta il
    # vincolo dimensionale che gli abbiamo imposto.
    PAPER = (1200, 1500)
    img_p = render_sentence(
        "Riga di prova.",
        font_path=FONT_PATH,
        font_size=24,
        profile_name="poesia",
        paper_size=PAPER,
        seed=0,
    )
    assert img_p.size == PAPER, \
        f"Invariante 2 fallita: atteso {PAPER}, ottenuto {img_p.size}."
    print(f"[2/5] OK  Dimensioni foglio = {PAPER}.")

    # -----------------------------------------------------------
    # Invariante 3 — Profilo "poesia" e' deterministico anche senza seed
    # -----------------------------------------------------------
    # Avendo sigma_x = sigma_y = 0 e intra_glyph_noise = 0, l'output
    # non dipende dal generatore casuale. Due chiamate consecutive
    # senza seed devono comunque coincidere.
    img_c = render_sentence_tight(
        "Poesia senza rumore.",
        font_path=FONT_PATH,
        font_size=24,
        profile_name="poesia",
        seed=None,
    )
    img_d = render_sentence_tight(
        "Poesia senza rumore.",
        font_path=FONT_PATH,
        font_size=24,
        profile_name="poesia",
        seed=None,
    )
    assert img_c.tobytes() == img_d.tobytes(), \
        "Invariante 3 fallita: il profilo 'poesia' deve essere deterministico."
    print("[3/5] OK  Profilo 'poesia' deterministico anche senza seed.")

    # -----------------------------------------------------------
    # Invariante 4 — Sostituzioni tipografiche italiane
    # -----------------------------------------------------------
    # apply_typography e' una trasformazione conservativa della stringa
    # che applica le sostituzioni tipografiche italiane.
    cases = [
        ("po'",        "po\u2019"),       # apostrofo dritto -> curvo
        ('"frase"',    "\u201Dfrase\u201D"),  # virgolette
        ("uno - due",  "uno \u2013 due"),  # trattino tra spazi -> medio
        ("...",        "\u2026"),         # ellissi
        ("--",         "\u2014"),         # em-dash
    ]
    for src, expected in cases:
        got = apply_typography(src)
        assert got == expected, (
            f"Invariante 4 fallita: apply_typography({src!r}) = {got!r}, "
            f"atteso {expected!r}."
        )
    print(f"[4/5] OK  Sostituzioni tipografiche italiane ({len(cases)} casi).")

    # -----------------------------------------------------------
    # Invariante 5 — Profilo invalido solleva ValueError
    # -----------------------------------------------------------
    # Controllo dei parametri d'input: il solutore deve rifiutare
    # configurazioni sconosciute, non produrre risultati silenziosi.
    try:
        render_sentence_tight(
            "x",
            font_path=FONT_PATH,
            font_size=24,
            profile_name="profilo_che_non_esiste",
        )
    except ValueError:
        print("[5/5] OK  Profilo invalido -> ValueError.")
    else:
        raise AssertionError(
            "Invariante 5 fallita: profilo invalido non ha sollevato eccezione."
        )

    print()
    print("Tutti i sanity check sono passati.")
