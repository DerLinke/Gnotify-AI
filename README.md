# Gnotify-AI 🤖🔊

**Ein intelligenter lokaler Benachrichtigungs-Daemon mit KI-Sprachausgabe (TTS), entwickelt für die DerLinke Software Zentrale.**

Gnotify-AI klinkt sich nahtlos in deinen D-Bus ein, fängt eintreffende Desktop-Benachrichtigungen ab und liest sie dir mit natürlicher KI-Stimme vor. Anstatt dich mit nervigen Ping-Sounds aus der Konzentration zu reißen, sagt dir dein System genau, was gerade passiert – intelligent gefiltert und konfigurierbar.

---

## ✨ Features

* **KI-Sprachausgabe (TTS):** Nutzt leistungsstarke Text-to-Speech Modelle (wie Kokoro) via LocalAI, um Benachrichtigungen in natürlicher Sprache (Deutsch/Englisch) vorzulesen.
* **Intelligente Textfilter:** 
  * URLs und lange Links werden zu "Link" gekürzt.
  * Komplexe Terminal-Befehle werden zusammengefasst ("Ein Terminal-Befehl").
  * Lange Dateipfade werden zu "Verzeichnis" abstrahiert.
  * Extrem lange Texte werden intelligent abgeschnitten.
* **Regelbasiertes System:** Erstelle eigene Regeln basierend auf App-Namen (z.B. *Slack*, *Antigravity*). Lege pro App fest, ob die Nachricht vorgelesen, stummgeschaltet oder ein spezifischer Sound abgespielt werden soll.
* **Spam-Schutz:** Integriertes Rate-Limiting und Deduplizierungs-Fenster verhindern, dass du bei vielen Nachrichten auf einmal zugespammt wirst.
* **GUI Control Center:** Eine grafische Benutzeroberfläche zur Verwaltung des Daemons, Live-Log-Ansicht und Regel-Erstellung.
* **Desktop-Integration:** Vollständig als `systemd` User-Service integriert, startet automatisch im Hintergrund und ist über das Startmenü erreichbar.

---

## 📋 Voraussetzungen

Damit Gnotify-AI funktioniert, benötigst du ein lokales oder entferntes KI-Backend.

1. **LocalAI Server**
   * Ein laufender [LocalAI](https://localai.io) Server, der eine OpenAI-kompatible `/v1/audio/speech` Schnittstelle bereitstellt.
2. **Kokoro TTS Modelle**
   * Die Kokoro-Modelle müssen in LocalAI konfiguriert sein.
   * Empfehlung für Englisch: Standard `kokoro` Modell.
   * Empfehlung für Deutsch: Das `kokoro-de` Modell (mit der Stimme `de_martin`).
3. **System-Pakete (Linux)**
   * `python3` (inkl. `python3-venv`)
   * `libnotify-bin` (für Test-Benachrichtigungen)
   * `paplay` (PulseAudio / PipeWire für die Audio-Wiedergabe)

---

## 🚀 Installation

1. **Repository klonen:**
   ```bash
   git clone git@github.com:DerLinke/Gnotify-AI.git
   cd Gnotify-AI
   ```

2. **Installations-Skript ausführen:**
   ```bash
   chmod +x install.sh
   ./install.sh
   ```
   *Das Skript erstellt automatisch die virtuelle Python-Umgebung, installiert alle Abhängigkeiten, richtet den Systemd-Daemon ein und fügt einen Starter zu deinem Anwendungsmenü hinzu.*

---

## ⚙️ Nutzung & Konfiguration

* **Control Center starten:** 
  Öffne dein Startmenü und suche nach **"Gnotify AI Control Center"**.
* **API konfigurieren:** 
  Trage im Tab *General Settings* die URL zu deinem LocalAI-Server ein (z.B. `https://ai.dan.jetzt/v1`).
* **Stimme wählen:** 
  Wähle deine bevorzugte Stimme. Wenn du eine deutsche Stimme (beginnend mit `de_`, z.B. `de_martin`) wählst, routet der Daemon die Anfrage automatisch an das deutsche Modell (`kokoro-de`), sofern auf dem Server vorhanden.
* **Live Test:**
  Wechsle in den *Test Suite*-Tab und sende eine Test-Benachrichtigung, um zu prüfen, ob die Sprachausgabe funktioniert.

---
*Gnotify-AI – Made with ❤️ by DerLinke Software Zentrale.*
