#!/bin/zsh
set -euo pipefail
DIR="${0:A:h}"
cd "$DIR"
if [[ ! -x .venv/bin/python ]]; then
  echo 'Es fehlt die vorhandene virtuelle Python-Umgebung. Zunächst zsh install.command ausführen.' >&2
  exit 1
fi
.venv/bin/python -m pip install -e '.[elastic,semantic]'
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/authority-matcher" <<EOF
#!/bin/sh
exec "$DIR/.venv/bin/authority-matcher" "\$@"
EOF
chmod +x "$HOME/.local/bin/authority-matcher"
echo 'Update installiert. Vorhandene FIM-SQLite-Daten sind unverändert.'
echo 'Nächste Schritte: authority-matcher --no-semantic (schneller Ersttest), dann authority-matcher.'
