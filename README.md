# reveries

Kleine, sarkastische Eigenheiten („Quirks“) für deterministische Antworten – benannt nach
den *Reveries* aus Westworld: winzige Gesten, die eine Maschine menschlicher wirken lassen.

```
wo ist indiana jones 4   →  Wovon redest du? Es gibt nur drei Indiana-Jones-Filme.
                            Aber wenn du dir den Tag versauen willst: Kiste 4.
```

Gebaut für die [Lagersuche](https://github.com/gman-k8s/nestegg-locator) in Home Assistant,
aber als Bibliothek in jedem Projekt nutzbar.

## Prinzipien

- **Token-sparsam:** Ob ein Quirk passt, entscheidet String-Matching. Kein Treffer → die
  Originalantwort kommt unverändert zurück (0 Tokens).
- **Vorlagen zuerst:** Quirks bringen feste Antworten mit Platzhaltern (`{kiste}`) mit.
- **LLM optional:** Eine `llm`-Callable wird nur bei einem Treffer gerufen und bekommt nur
  diesen einen Quirk.
- **Fakten sind heilig:** Jede Antwort – Vorlage oder LLM – muss alle geschützten Fakten
  enthalten, sonst gilt die Originalantwort. Fehler und Timeouts ebenso.
- **Robust:** Kaputte Quirk-Dateien werden übersprungen und auf stderr gemeldet.

Einzige Abhängigkeit: PyYAML (im Home-Assistant-Core-Container vorhanden).

## Verwendung

```python
from reveries import load, load_persona, apply

QUIRKS = load("/config/reveries/quirks")
text = apply(
    plain="Indiana Jones und das Königreich des Kristallschädels liegt in Kiste 4.",
    facts={"kiste": 4, "titel": "Indiana Jones und das Königreich des Kristallschädels"},
    project="nestegg",                 # für scope; None = kein Filter
    texts=[user_text, item_title],     # Matching gegen Frage UND DB-Titel
    quirks=QUIRKS,
    llm=None,                          # optional: Callable str -> str
    llm_share=0.4,                     # Anteil der Treffer, die das LLM formuliert
    rng=None,                          # random.Random für reproduzierbare Tests
    persona=load_persona("/config/reveries/persona.md"),
)
```

`explain(...)` nimmt dieselben Argumente und liefert zusätzlich, welcher Quirk gegriffen hat
und warum (`.text`, `.source`, `.quirk`, `.reason`, `.matches`).

### Ablauf

1. Quirks mit passendem `scope` und Treffer in einem der `texts` sammeln.
2. Den besten wählen: höchste `priority`, dann längster getroffener Begriff, dann `id`.
3. Mit `chance` würfeln – verfehlt → Originalantwort.
4. Mit `llm_share` entscheiden, ob das LLM formuliert (nur wenn `llm` übergeben wurde;
   ohne passende Vorlage immer). Fällt die LLM-Antwort durch den Fakten-Check, wird eine
   Vorlage genommen, sonst die Originalantwort.

### LLM-Adapter

Nur Standardbibliothek (`urllib`), Timeout 20 s; zusätzlich bricht `apply` nach
`llm_timeout=25` s hart ab (HA beendet `shell_command` nach 60 s).

```python
from reveries.llm import openai_compatible, gemini

llm = openai_compatible("http://192.168.1.50:8000/v1", "qwen2.5-7b-instruct")  # vLLM
llm = gemini("gemini-2.5-flash", api_key="…")
```

Der Prompt enthält nur `persona.md`, die Haltung des einen Quirks, die Fakten
(„exakt übernehmen“) und die Originalantwort. `python -m reveries test … --prompt` zeigt ihn.

## Quirks schreiben

Eine Markdown-Datei pro Quirk irgendwo unter `quirks/` (Unterordner nach Belieben,
Dateien mit `_` am Anfang und `README.md` werden ignoriert):

```markdown
---
id: indy-trilogie               # Pflicht, eindeutig
match: ["indiana jones 4", "kristallschädel", "rad des schicksals"]   # Pflicht
scope: [nestegg]                # Projektnamen oder ["*"]; Default ["*"]
chance: 0.8                     # Default 1.0
priority: 0                     # höher gewinnt; Default 0
guard: [kiste]                  # Pflicht-Fakten in der Antwort; Default: alle Fakten
---
Haltung: Es gibt nur drei Indiana-Jones-Filme. Teil 4 und 5 existieren nicht.
Genervt-sarkastisch, gibt am Ende aber trotzdem die richtige Info.

## Vorlagen
- Wovon redest du? Es gibt nur drei Indiana-Jones-Filme. Aber wenn du dir den Tag versauen willst: Kiste {kiste}.
- Kristallschädel? Nie gehört. Falls doch: Kiste {kiste}. Ich hab nichts gesagt.

## Notizen
Alles unter anderen Überschriften ist Kommentar und wird ignoriert.
```

**Matching:** Begriffe und Texte werden gleich normalisiert – Kleinschreibung, NFKC,
`ä`→`ae`/`ß`→`ss` (beide Schreibweisen treffen), Akzente und Satzzeichen weg, römische
Zahlen II–XX als Ziffern („Highlander II“ = „highlander 2“). Es zählen nur ganze Wörter:
„indiana jones 4“ trifft nicht „indiana jones 40“. Endet ein Begriff auf ein Wort mit
mindestens 4 Buchstaben, sind deutsche Endungen erlaubt (`-s -es -n -en -e -er`), damit
„kristallschädel“ auch „des Kristallschädels“ trifft.

**`guard`:** Ohne `guard` müssen *alle* übergebenen Fakten in der Antwort stehen – auch
`titel`. Soll der Quirk den Titel verleugnen dürfen (wie bei Indy), `guard: [kiste]` setzen.
Vorlagen mit fehlenden Platzhaltern oder ohne geschützte Fakten werden übersprungen.

### Prüfen

```sh
python -m reveries lint                 # alle Quirks unter ./quirks; Exit 1 bei Fehlern
python -m reveries test "wo ist indiana jones IV" \
    --titel "Indiana Jones und das Königreich des Kristallschädels" \
    --fakt kiste=4 --project nestegg --seed 1 --prompt
```

`test` zeigt alle Treffer, die Entscheidung und die Antwort. Mit `--llm-url`/`--llm-model`
(OpenAI-kompatibel, Key optional in `REVERIES_API_KEY`) oder `--gemini MODELL`
(Key in `GEMINI_API_KEY`) wird das LLM tatsächlich gefragt.

## Home Assistant

### Installation

In der App **Terminal & SSH**:

```sh
git clone https://github.com/gman-k8s/reveries.git /config/reveries
python3 -m reveries lint /config/reveries/quirks    # aus /config/reveries heraus
```

Keine pip-Installation nötig: Das Suchskript hängt `/config/reveries` an `sys.path`.
Alternativ geht `pip install git+https://github.com/gman-k8s/reveries` (nicht im HA-Container).

### Einbinden in lager_suche.py

[nestegg-locator](https://github.com/gman-k8s/nestegg-locator) hat die Anbindung eingebaut
(`with_reveries` in `lager_suche.py`): Liegt reveries unter `/config/reveries`, ist sie aktiv,
`--sachlich` schaltet sie pro Aufruf ab. Für andere Projekte zeigt
[`examples/lager_suche_integration.py`](examples/lager_suche_integration.py) das Muster:

- `import reveries` in `try/except` – fehlt reveries, bleibt die Antwort sachlich.
- Nur bei eindeutigen Treffern (nicht fuzzy, alle in derselben Kiste) würzen.
- Fakten: `kiste` (Nummer aus „Kiste 4“), `ort` (z. B. „Keller“), `titel`.
- Gematcht wird gegen die Telegram-Frage und die Namen aller Treffer.
- Optionales LLM über `REVERIES_LLM_URL` / `REVERIES_LLM_MODEL`.

Ausprobieren ohne HA:

```sh
NESTEGG_DIR=../nestegg-locator python3 examples/lager_suche_integration.py \
    --data ../nestegg-locator/tests/fixtures/inventar_beispiel.csv wo ist die hard
```

### Updates per Telegram

Neue Quirks: Datei anlegen, `python -m reveries lint`, pushen. Auf HA reicht `git pull` –
das Suchskript liest die Quirks bei jeder Anfrage frisch. Als `shell_command`:

```yaml
  reveries_update: "git -C /config/reveries pull --ff-only"
```

Im „Smart Router“ eine Regel für `!reveries` ergänzen, die `shell_command.reveries_update`
mit `response_variable` aufruft und `stdout` (bzw. `stderr` bei Fehler) zurückschickt.

## Entwicklung

```sh
./setup-venv.sh          # .venv mit PyYAML + pytest
.venv/bin/pytest
.venv/bin/python -m reveries lint
```

Der Integrationstest läuft gegen `../nestegg-locator`, falls es daneben ausgecheckt ist,
und wird sonst übersprungen.
