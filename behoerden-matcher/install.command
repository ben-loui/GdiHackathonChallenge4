#!/bin/zsh
# macOS: once-only installer. No sudo, no modification of existing project files.
set -euo pipefail
SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"
printf '\n Behörden-Matcher: Installation (lokaler Benutzer)\n\n'
for tool in python3 node npm docker; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Fehlende Voraussetzung: $tool"
    echo "Bitte installieren und erneut ./install.command ausführen."
    if [[ "$tool" == docker ]]; then echo 'Docker Desktop: https://www.docker.com/products/docker-desktop/'; fi
    exit 1
  fi
done
python3 - <<'PY'
import sys
if sys.version_info < (3, 10):
    sys.exit('Python >=3.10 wird benötigt')
PY
node - <<'JS'
if (Number(process.versions.node.split('.')[0]) < 20) process.exit(1);
JS
python3 -m venv .venv
"$SCRIPT_DIR/.venv/bin/python" -m pip install -U pip
"$SCRIPT_DIR/.venv/bin/python" -m pip install -e '.[elastic,semantic]'
mkdir -p "$HOME/.local/bin"
npm install --prefix "$SCRIPT_DIR/.fim-cli" @maschinenlesbar.org/fim-portal-cli
cat > "$HOME/.local/bin/fim-portal" <<EOF
#!/bin/sh
exec "$SCRIPT_DIR/.fim-cli/node_modules/.bin/fim-portal" "\$@"
EOF
chmod +x "$HOME/.local/bin/fim-portal"
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/authority-matcher" <<EOF
#!/bin/sh
exec "$SCRIPT_DIR/.venv/bin/authority-matcher" "\$@"
EOF
chmod +x "$HOME/.local/bin/authority-matcher"
for profile in "$HOME/.zprofile" "$HOME/.zshrc"; do
  if [[ -f "$profile" ]] && grep -Fq 'export PATH="$HOME/.local/bin:$PATH"' "$profile"; then
    continue
  fi
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$profile"
done
printf '\nInstalliert. In einem NEUEN Terminal: authority-matcher\n'
printf 'Nächster Schritt: JZuFi importieren (README), dann authority-matcher starten.\n'
