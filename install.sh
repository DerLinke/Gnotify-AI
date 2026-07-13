#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

# GlitchHeader & Branding
SCRIPTNAME="Gnotify-AI Installer"
VERSION="1.0.0"

C_RED="\e[38;2;255;0;0m"
C_PINK="\e[38;2;161;0;94m"
C_BLUE="\e[38;2;0;0;255m"
NC="\e[0m"
BOLD="\e[1m"

show_banner() {
    echo -e "      ${C_PINK}██${NC}   ${C_BLUE}█████${NC}"
    echo -e "   ${C_RED}██${NC}             ${C_BLUE}██${NC}"
    echo -e "${C_RED}██${NC}          ${C_BLUE}██${NC} ${BOLD}${SCRIPTNAME} v${VERSION}${NC}"
    echo -e "   ${C_RED}██${NC}             ${C_BLUE}██${NC}"
    echo -e "      ${C_PINK}██${NC}   ${C_BLUE}█████${NC}\n"
}

show_footer() {
    echo -e "\n${C_BLUE}----------------------------------------------------${NC}"
    echo -e "  ${BOLD}${SCRIPTNAME} v${VERSION}${NC}"
    echo -e "  \e[2mWeb:\e[0m ${C_BLUE}\e[4mhttps://derlinke.github.io/\e[0m"
    echo -e "  ${C_RED}██${C_PINK}██${C_BLUE}██${NC}"
    echo -e "${C_BLUE}====================================================${NC}\n"
}

show_banner

# 1. Prerequisites checken
echo -e "${C_BLUE}1. Überprüfe Voraussetzungen...${NC}"
FAILED=0

check_prereq() {
    local cmd=$1
    local name=$2
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "   ${C_RED}ERROR:${NC} Voraussetzung '$name' ($cmd) ist nicht installiert." >&2
        FAILED=1
    else
        echo -e "   ${C_BLUE}Check bestanden:${NC} $name ($cmd) ist verfügbar."
    fi
}

check_prereq "python3" "Python 3"
check_prereq "pip3" "pip 3"
check_prereq "systemctl" "systemd"
check_prereq "paplay" "paplay"

if ! python3 -c "import venv" >/dev/null 2>&1; then
    echo -e "   ${C_RED}ERROR:${NC} Python 3 'venv' Modul ist nicht installiert." >&2
    FAILED=1
else
    echo -e "   ${C_BLUE}Check bestanden:${NC} Python 3 venv Modul ist verfügbar."
fi

if [ $FAILED -ne 0 ]; then
    echo -e "   ${C_RED}Installation abgebrochen aufgrund fehlender Voraussetzungen.${NC}" >&2
    exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo -e "   Projekt-Verzeichnis: $PROJECT_ROOT"

# 2. Verzeichnisse anlegen
echo -e "${C_BLUE}2. Erstelle Standard-Verzeichnisse...${NC}"
mkdir -p "$HOME/.config/Gnotify-AI"
mkdir -p "$HOME/.cache/Gnotify-AI/tts"
echo -e "   Verzeichnisse bereitgestellt:"
echo -e "   - ~/.config/Gnotify-AI"
echo -e "   - ~/.cache/Gnotify-AI/tts"

# 3. Virtual Environment erstellen mit System-Paketen
echo -e "${C_BLUE}3. Erstelle Python Virtual Environment...${NC}"
python3 -m venv --system-site-packages "$PROJECT_ROOT/venv"
echo -e "   Virtual Environment erstellt unter: $PROJECT_ROOT/venv"

# 4. Abhängigkeiten installieren
echo -e "${C_BLUE}4. Installiere Python-Abhängigkeiten...${NC}"
"$PROJECT_ROOT/venv/bin/pip" install --upgrade pip
"$PROJECT_ROOT/venv/bin/pip" install -r "$PROJECT_ROOT/requirements.txt"

# 5. Systemd User Service konfigurieren
echo -e "${C_BLUE}5. Konfiguriere Systemd-User-Service...${NC}"
mkdir -p "$HOME/.config/systemd/user"
SERVICE_FILE="$HOME/.config/systemd/user/gnotify-ai.service"

cat << EOF > "$SERVICE_FILE"
[Unit]
Description=Gnotify AI Daemon Service
After=dbus.service

[Service]
Type=simple
ExecStart=$PROJECT_ROOT/venv/bin/python3 $PROJECT_ROOT/gnotify_ai_daemon.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF
echo -e "   Service-Datei geschrieben nach: $SERVICE_FILE"

# 6. Service aktivieren und starten
echo -e "${C_BLUE}6. Aktiviere und starte den Systemd-User-Service...${NC}"
systemctl --user daemon-reload
systemctl --user enable gnotify-ai.service
systemctl --user restart gnotify-ai.service

# 7. Desktop-Starter erstellen (Startmenü)
echo -e "${C_BLUE}7. Erstelle Desktop-Starter im Startmenü...${NC}"
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"
DESKTOP_FILE="$DESKTOP_DIR/gnotify-ai.desktop"

# Logo herunterladen falls nicht vorhanden
if [ ! -f "$PROJECT_ROOT/logo.svg" ]; then
    wget -q https://derlinke.github.io/logo.svg -O "$PROJECT_ROOT/logo.svg" || true
fi

cat << EOF > "$DESKTOP_FILE"
[Desktop Entry]
Name=Gnotify AI Control Center
Comment=Manage Gnotify AI Daemon rules, settings, and logs
Exec=$PROJECT_ROOT/venv/bin/python3 $PROJECT_ROOT/gnotify_ai_gui.py
Icon=$PROJECT_ROOT/logo.svg
Terminal=false
Type=Application
Categories=Settings;Utility;
StartupNotify=true
EOF
chmod +x "$DESKTOP_FILE"
echo -e "   Desktop-Starter erstellt unter: $DESKTOP_FILE"

# 8. Status überprüfen
echo -e "${C_BLUE}8. Überprüfe Service-Status...${NC}"
sleep 1
if systemctl --user is-active gnotify-ai.service >/dev/null 2>&1; then
    echo -e "\n${C_PINK}Installation erfolgreich abgeschlossen! Der Service läuft im Hintergrund.${NC}"
    systemctl --user status gnotify-ai.service
    show_footer
    exit 0
else
    echo -e "\n${C_RED}ERROR: gnotify-ai.service konnte nicht gestartet werden.${NC}" >&2
    systemctl --user status gnotify-ai.service >&2
    show_footer
    exit 1
fi
