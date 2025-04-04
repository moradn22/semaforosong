#!/bin/bash
# Script de instalación para SemaforoSong
echo "=== Instalando SemaforoSong ==="

# Crear directorios
mkdir -p $HOME/semaforosong
mkdir -p $HOME/.config/autostart

# Descargar archivos
echo "Descargando archivos de la aplicación..."
curl -sSL https://raw.githubusercontent.com/TU_USUARIO/semaforosong/main/semaforosong_app.py -o $HOME/semaforosong/semaforosong_app.py

# Instalar dependencias
echo "Instalando dependencias necesarias..."
sudo apt update
sudo apt install -y python3-pip python3-pyqt5 unclutter
pip3 install pyserial requests pillow

# Configurar autoarranque
echo "Configurando inicio automático..."
cat > $HOME/.config/autostart/semaforosong.desktop << EOL
[Desktop Entry]
Type=Application
Name=SemaforoSong
Exec=python3 $HOME/semaforosong/semaforosong_app.py
Terminal=false
X-GNOME-Autostart-enabled=true
EOL

# Ocultar cursor
cat > $HOME/.config/autostart/unclutter.desktop << EOL
[Desktop Entry]
Type=Application
Name=Unclutter
Exec=unclutter -idle 0.1 -root
Terminal=false
EOL

# Dar permisos
chmod +x $HOME/semaforosong/semaforosong_app.py

echo "=== Instalación completada ==="
echo "¿Quieres iniciar la aplicación ahora? (s/n)"
read respuesta
if [ "$respuesta" = "s" ]; then
  python3 $HOME/semaforosong/semaforosong_app.py
else
  echo "Para iniciar manualmente, ejecuta: python3 $HOME/semaforosong/semaforosong_app.py"
  echo "La aplicación también se iniciará automáticamente al reiniciar"
fi
