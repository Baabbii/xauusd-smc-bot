"""
Loader minimal pentru fișier .env -- nu necesită nicio librărie externă.

Citește un fișier .env (format cheie=valoare, o pereche pe linie) și
încarcă valorile în os.environ, DOAR dacă nu sunt deja setate (variabilele
de mediu reale au prioritate față de .env).

Motivul pentru care există acest fișier separat: pe Windows, variabilele
setate cu `setx` nu sunt întotdeauna vizibile pentru task-urile pornite
din Task Scheduler. Un fișier .env citit direct de script e mai fiabil.
"""

import os


def load_env(path: str = ".env") -> None:
    if not os.path.exists(path):
        return

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
