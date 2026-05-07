#!/bin/bash
set -e

# Generate .streamlit/secrets.toml from .env so st.secrets doesn't crash
mkdir -p /app/.streamlit
python3 - <<'EOF'
import pathlib
env = pathlib.Path('/app/.env')
out = pathlib.Path('/app/.streamlit/secrets.toml')
lines = []
for line in env.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    k, _, v = line.partition('=')
    v = v.strip().strip("'\"").replace('\\', '\\\\')
    lines.append(f'{k.strip()} = "{v}"')
out.write_text('\n'.join(lines) + '\n')
EOF

exec streamlit run app.py --server.port=8501 --server.address=0.0.0.0
