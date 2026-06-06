"""
setup.py — Configurazione py2app per Olivetti Lettera 25.

Uso:
    python setup.py py2app           # build standalone
    python setup.py py2app -A        # build alias (sviluppo, NON per distribuzione)

Il bundle prodotto in dist/Lettera25.app e' standalone:
puo' essere copiato in /Applications senza dipendenze esterne
(eccezion fatta per il sistema operativo e i font installati).
"""

from setuptools import setup

APP = ["app.py"]

DATA_FILES = []

OPTIONS = {
    # Icona compilata: riferimento al .icns multi-risoluzione
    "iconfile": "assets/icon.icns",

    # Pacchetti che devono finire dentro il bundle
    "packages": ["PIL", "objc", "Cocoa"],

    # Moduli aggiuntivi (logica di dominio)
    "includes": ["core"],

    # Esclusioni: tutto cio' che non ci serve riduce dimensione bundle
    "excludes": [
        "tkinter",
        "test",
        "unittest",
        "pydoc",
        "doctest",
    ],

    # Info.plist incorporato nel bundle
    "plist": {
        "CFBundleName":          "Lettera 25",
        "CFBundleDisplayName":   "Olivetti Lettera 25",
        "CFBundleIdentifier":    "net.raucci.lettera25",
        "CFBundleVersion":       "1.1.0",
        "CFBundleShortVersionString": "1.1.0",
        "CFBundleExecutable":    "Lettera25",
        "LSMinimumSystemVersion": "11.0",

        # ★ CRITICO: senza questo il bundle ignora il Dark Mode
        # (stub py2app fu compilato su una vecchia versione macOS)
        "NSRequiresAquaSystemAppearance": False,

        # Politica di attivazione: app GUI completa
        "LSUIElement": False,

        # Tipi di file accettati (l'app salva PNG)
        "CFBundleDocumentTypes": [],

        "NSHumanReadableCopyright":
            "Copyright (c) 2026 Biagio Raucci. Distribuito sotto licenza MIT.",
    },
}

setup(
    name="Lettera25",
    version="1.1.0",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
