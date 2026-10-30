# FAW als statische Website

Statische Kopie von https://www.faw.at/ mit allen 14 öffentlich verlinkten Seiten. HTML, CSS, JavaScript, Bilder und Schriften liegen vollständig lokal. Kein WordPress, PHP, Datenbank, Build-Schritt oder JavaScript-Paketmanager erforderlich.

## Lokal öffnen

`index.html` per Doppelklick im Browser öffnen. Die Unterseiten, Navigation, Slider und Suche funktionieren auch direkt über `file://`. Den gesamten Ordner zusammenhalten; einzelne HTML-Dateien benötigen die mitgelieferten Assets.

Alternativ mit einem beliebigen statischen Webserver, zum Beispiel:

```sh
python3 -m http.server 8000
```

Dann http://localhost:8000/ öffnen. Python ist nur für diesen optionalen Testserver nötig.

## GitHub Pages

Die öffentliche Website wird unter https://davidnemecek.github.io/www-fwa/ bereitgestellt.

GitHub Pages veröffentlicht den Branch `main` aus `/(root)`. Änderungen an der Website nach `main` pushen; GitHub baut und aktualisiert die Veröffentlichung automatisch. Die enthaltene `.nojekyll` schaltet Jekyll aus. Alle internen Links und Ressourcen funktionieren auch unter diesem Projekt-Unterverzeichnis.

Die Ordner `wp-content` und `wp-includes` enthalten ausschließlich statische Originaldateien. Ihre bisherigen Namen bleiben erhalten, damit das ursprüngliche Design und dessen Skripte funktionieren. Es gibt keine PHP-Dateien und keine WordPress-Installation.

## Verhalten

- Der Original-Slider läuft mit den ursprünglichen Animationen; nachzuladende Folien sind fest eingebettet und benötigen keine REST-API.
- Die Suche durchsucht die lokalen Seiten. Darstellung, Auszüge, Reihenfolge und Seitennavigation verwenden die archivierten Originalvorlagen.
- Externe Links und E-Mail-Links bleiben erhalten. Nur beim bewussten Öffnen dieser Links wird die jeweilige externe Seite beziehungsweise das E-Mail-Programm benötigt.
- Inhalte entsprechen dem heruntergeladenen Stand. Spätere Änderungen am Original werden nicht automatisch übernommen.

## Export und Prüfung

Nur für eine erneute Erstellung oder Entwicklung:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r tools/requirements.txt
python3 tools/mirror.py
python3 -m playwright install chromium
python3 tools/check_static.py
```

`mirror.py` lädt öffentliche Seiten und zugehörige Dateien einzeln mit mindestens 1,05 Sekunden Abstand und nutzt einen persistenten Cache unter `.snapshot/` (nicht versioniert). Bei einem ausgelasteten Server bricht der Export ab. Ein erneuter Lauf mit vorhandenem Cache fragt bereits gespeicherte Dateien nicht erneut ab und überschreibt die generierten HTML-/Asset-Dateien.

`check_static.py` vergleicht Desktop und Mobil gegen die unveränderten Originaldateien im Cache, ohne dafür die Live-Seite erneut aufzurufen. Der zeitabhängige Slider wird bei diesem Bildvergleich ausgeblendet und separat funktional geprüft. Ergebnisse und Vergleichsbilder landen standardmäßig unter `/tmp/faw-comparison/`. Bei Bedarf lässt sich mit `FAW_CHROMIUM=/pfad/zu/chrome` ein Browser vorgeben.
