#!/bin/bash
# Reinstall Microsoft SQL Server 2022 on Ubuntu 24.04 after a VM replacement.
# The VM replacement wipes /opt/mssql (outside the home directory), so this
# repeats the full install. Run with sudo:
#   sudo bash ~/workspace/dashzone-milestone-3/sql/reinstall-sqlserver.sh
# The SA password is read from .sa_password.txt if it exists, otherwise a
# strong one is generated and saved there (chmod 600). This script never
# prints the SA password.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

# Home directory of the user who invoked sudo (hatch).
USER_HOME="/home/${SUDO_USER:-hatch}"
SA_FILE="$USER_HOME/workspace/dashzone-milestone-3/sql/.sa_password.txt"

# --- SA password: reuse the saved one, or generate and save a new one. ---
if [ -f "$SA_FILE" ]; then
    SA_PASS="$(cat "$SA_FILE")"
else
    SA_PASS="$(tr -dc 'A-Za-z0-9!@#$%^&*()' < /dev/urandom | head -c 24)"
    mkdir -p "$(dirname "$SA_FILE")"
    printf '%s' "$SA_PASS" > "$SA_FILE"
    chmod 600 "$SA_FILE"
fi

# --- Microsoft apt repos. ---
# The 24.04 mssql-server-2022 config is 404, so use the 22.04 server config
# plus the 24.04 prod list for the driver/tools. The prod key must be at
# /usr/share/keyrings/microsoft-prod.gpg (the prod list references it).
if [ ! -f /usr/share/keyrings/microsoft-prod.gpg ]; then
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg
fi
cp /usr/share/keyrings/microsoft-prod.gpg /etc/apt/trusted.gpg.d/microsoft.gpg
curl -fsSL https://packages.microsoft.com/config/ubuntu/22.04/mssql-server-2022.list \
    -o /etc/apt/sources.list.d/mssql-server-2022.list
curl -fsSL https://packages.microsoft.com/config/ubuntu/24.04/prod.list \
    -o /etc/apt/sources.list.d/microsoft-prod.list
apt-get update

# --- Wait for any other apt/dpkg process (e.g. the boot os-intent replay). ---
for _ in $(seq 1 60); do
    if ! pgrep -x apt-get >/dev/null 2>&1 && ! pgrep -x dpkg >/dev/null 2>&1; then
        break
    fi
    sleep 10
done

# --- Install SQL Server, tools and the ODBC driver. ---
ACCEPT_EULA=Y apt-get install -y mssql-server mssql-tools18 msodbcsql18

# --- libldap fix: the 22.04 sqlservr needs OpenLDAP 2.5, Ubuntu 24.04 ships 2.6. ---
if ! ldconfig -p | grep -q 'liblber-2.5.so.0'; then
    cd /tmp
    curl -fsSL -o libldap-2.5-0_2.5.20+dfsg-0ubuntu0.22.04.1_amd64.deb \
        http://archive.ubuntu.com/ubuntu/pool/main/o/openldap/libldap-2.5-0_2.5.20+dfsg-0ubuntu0.22.04.1_amd64.deb
    dpkg -i libldap-2.5-0_2.5.20+dfsg-0ubuntu0.22.04.1_amd64.deb
fi

# --- Fake cgroup memory.max. ---
# sqlservr stats /sys/fs/cgroup/memory.max, but this VM has no memory
# controller (the file does not exist) and /sys/fs/cgroup is root-only, so
# the stat fails with EACCES. Provide a fake memory.max (total RAM in bytes)
# in a directory that is bind-mounted over /sys/fs/cgroup inside a private
# mount namespace. The bind mount exists only inside that namespace.
mkdir -p /tmp/fakecgroup
TOTAL_BYTES=$(( $(grep MemTotal /proc/meminfo | awk '{print $2}') * 1024 ))
printf '%s' "$TOTAL_BYTES" > /tmp/fakecgroup/memory.max
chmod 755 /tmp/fakecgroup
chmod 644 /tmp/fakecgroup/memory.max

# --- Setup (locale C hangs the interactive setup; use -n and MSSQL_LCID=1033). ---
# Setup starts sqlservr, which needs the fake memory.max, so run it inside
# the mount namespace.
MSSQL_SA_PASSWORD="$SA_PASS" unshare --mount bash -c '
    mount --bind /tmp/fakecgroup /sys/fs/cgroup
    MSSQL_PID=Developer MSSQL_LCID=1033 /opt/mssql/bin/mssql-conf -n setup accept-eula
'

# --- Set the SA password (same value) via set-sa-password. ---
# It requires the service to be stopped, and it also starts sqlservr in
# setup mode, so it needs the same namespace workaround.
systemctl stop mssql-server || true
MSSQL_SA_PASSWORD="$SA_PASS" unshare --mount bash -c '
    mount --bind /tmp/fakecgroup /sys/fs/cgroup
    /opt/mssql/bin/mssql-conf -n set-sa-password
'

# --- Memory limit: 1024 MB (this VM is tight on RAM). ---
/opt/mssql/bin/mssql-conf set memory.memorylimitmb 1024
systemctl start mssql-server

# --- Also cap the buffer pool via sp_configure (mssql.conf alone does not
# change the max server memory value). ---
sleep 5
/opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$SA_PASS" -C -Q \
    "EXEC sp_configure 'show advanced options', 1; RECONFIGURE; EXEC sp_configure 'max server memory (MB)', 1024; RECONFIGURE;"

# --- Python packages for the backend. ---
pip3 install --break-system-packages --ignore-installed pyodbc fastapi uvicorn

# --- Verify. ---
systemctl status mssql-server --no-pager | head -4
/opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$SA_PASS" -C -Q "SELECT @@VERSION" -W -s ","
/opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$SA_PASS" -C -Q \
    "SELECT CAST(value_in_use AS INT) AS max_server_memory_MB FROM sys.configurations WHERE name = 'max server memory (MB)'" -W -s ","
python3 -c "import pyodbc; print('pyodbc drivers:', pyodbc.drivers())"
python3 -c "import fastapi, uvicorn; print('fastapi', fastapi.__version__, '| uvicorn', uvicorn.__version__)"
echo "SQL Server reinstall complete. SA password is in $SA_FILE (not printed)."
