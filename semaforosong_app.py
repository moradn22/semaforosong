#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# SemaforoSong - Aplicación estilo cartel de tráfico optimizada para pantalla 3.5"

import sys
import os
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QFrame, QShortcut, QGridLayout
from PyQt5.QtGui import QPixmap, QImage, QKeySequence, QFont, QPalette, QColor
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
import requests
import serial
import serial.tools.list_ports
import json
import base64
from io import BytesIO
from PIL import Image
import time

class ArduinoThread(QThread):
    signal = pyqtSignal(str)
    
    def __init__(self, port):
        QThread.__init__(self)
        self.port = port
        self.running = True
        
    def run(self):
        try:
            self.arduino = serial.Serial(self.port, 9600, timeout=1)
            while self.running:
                if self.arduino.in_waiting > 0:
                    message = self.arduino.readline().decode('utf-8').strip()
                    if message:
                        self.signal.emit(message)
                time.sleep(0.1)
        except Exception as e:
            self.signal.emit(f"ERROR: {str(e)}")
            
    def send_command(self, cmd):
        try:
            if hasattr(self, 'arduino') and self.arduino.is_open:
                self.arduino.write(f"{cmd}\n".encode())
                return True
        except:
            pass
        return False
            
    def stop(self):
        self.running = False
        if hasattr(self, 'arduino') and self.arduino.is_open:
            self.arduino.close()

# Clase Arduino simulado para cuando no hay hardware
class FakeArduinoThread:
    def __init__(self):
        pass
    def send_command(self, cmd):
        print(f"Comando enviado (simulado): {cmd}")
        return True

class SemaforoApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.arduino_thread = None
        self.connect_attempts = 0
        
        # Iniciar búsqueda de Arduino con un timer
        QTimer.singleShot(2000, self.autoconnect_arduino)
        
    def initUI(self):
        self.setWindowTitle('SemaforoSong')
        # Ajustado exactamente para 3.5" (480x320)
        self.setGeometry(0, 0, 480, 320)
        self.showFullScreen()
        
        # Estilo de cartel de tráfico
        self.setStyleSheet("""
            QWidget {
                background-color: #003366;
                color: white;
                font-family: Arial, sans-serif;
            }
            QPushButton {
                background-color: #FF6600;
                color: white;
                border: 2px solid white;
                border-radius: 10px;
                padding: 8px;
                font-size: 14px;
                font-weight: bold;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: #FF9933;
            }
            QLabel {
                font-size: 14px;
                font-weight: bold;
            }
        """)
        
        # Layout principal - Usamos un layout vertical para maximizar espacio para QR
        main_layout = QVBoxLayout()
        main_layout.setSpacing(4)
        main_layout.setContentsMargins(4, 4, 4, 4)
        
        # Cabecera estilo cartel de tráfico
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #0066CC; border-radius: 5px; margin: 0px;")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(2, 2, 2, 2)
        header_layout.setSpacing(0)
        
        title = QLabel('SEMÁFORO SONG')
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet('color: white; font-size: 18px; font-weight: bold; background-color: transparent;')
        header_layout.addWidget(title)
        
        # Estado como subtítulo
        self.status_label = QLabel('ESPERANDO PULSACIÓN')
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet('color: #FFCC00; font-size: 16px; font-weight: bold; background-color: transparent;')
        header_layout.addWidget(self.status_label)
        
        main_layout.addWidget(header_frame)
        
        # Área central para QR y botones
        central_layout = QGridLayout()
        central_layout.setSpacing(4)
        
        # Marco para el QR con borde de señal - MUCHO MÁS GRANDE
        qr_frame = QFrame()
        qr_frame.setStyleSheet("""
            background-color: white; 
            border: 4px solid #FF6600; 
            border-radius: 10px;
        """)
        qr_layout = QVBoxLayout(qr_frame)
        qr_layout.setContentsMargins(4, 4, 4, 4)
        qr_layout.setSpacing(0)
        qr_layout.setAlignment(Qt.AlignCenter)  # Centrar el contenido
        
        # Imagen QR - MUCHO MÁS GRANDE
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setFixedSize(240, 240)  # QR más grande
        self.qr_label.setStyleSheet("border: none;")
        qr_layout.addWidget(self.qr_label)
        
        central_layout.addWidget(qr_frame, 0, 0, 3, 2)  # QR ocupa más celdas
        
        # Botones en vertical a la derecha
        self.test_button = QPushButton('PULSE PARA\nSOLICITAR (P)')
        self.test_button.clicked.connect(self.simulate_button_press)
        self.test_button.setStyleSheet("""
            QPushButton {
                background-color: #FF6600;
                color: white;
                border: 2px solid white;
                border-radius: 10px;
                padding: 5px;
                font-size: 14px;
                font-weight: bold;
                min-height: 50px;
            }
            QPushButton:hover {
                background-color: #FF9933;
            }
        """)
        central_layout.addWidget(self.test_button, 0, 2, 1, 1)
        
        self.connect_button = QPushButton('CONECTAR\nSISTEMA (C)')
        self.connect_button.clicked.connect(self.manual_connect_arduino)
        self.connect_button.setStyleSheet("""
            QPushButton {
                background-color: #009900;
                color: white;
                border: 2px solid white;
                border-radius: 10px;
                padding: 5px;
                font-size: 14px;
                font-weight: bold;
                min-height: 50px;
            }
            QPushButton:hover {
                background-color: #00CC00;
            }
        """)
        central_layout.addWidget(self.connect_button, 1, 2, 1, 1)
        
        self.exit_button = QPushButton('SALIR DEL\nSISTEMA (ESC)')
        self.exit_button.clicked.connect(self.close)
        self.exit_button.setStyleSheet("""
            QPushButton {
                background-color: #CC0000;
                color: white;
                border: 2px solid white;
                border-radius: 10px;
                padding: 5px;
                font-size: 14px;
                font-weight: bold;
                min-height: 50px;
            }
            QPushButton:hover {
                background-color: #FF0000;
            }
        """)
        central_layout.addWidget(self.exit_button, 2, 2, 1, 1)
        
        # Ajustar proporciones de la rejilla para dar más espacio al QR
        central_layout.setColumnStretch(0, 40)  # 40% izquierda del QR
        central_layout.setColumnStretch(1, 40)  # 40% derecha del QR
        central_layout.setColumnStretch(2, 20)  # 20% para botones
        
        main_layout.addLayout(central_layout)
        
        # Barra de estado inferior
        self.connection_label = QLabel('TOQUE PARA CONECTAR')
        self.connection_label.setAlignment(Qt.AlignCenter)
        self.connection_label.setStyleSheet('color: #FFCC00; background-color: #0066CC; border-radius: 5px; padding: 5px;')
        main_layout.addWidget(self.connection_label)
        
        # Establecer el layout
        self.setLayout(main_layout)
        
        # Proporciones del layout vertical principal
        main_layout.setStretchFactor(header_frame, 1)  # 10% cabecera
        main_layout.setStretchFactor(central_layout, 8)  # 80% QR y botones
        main_layout.setStretchFactor(self.connection_label, 1)  # 10% estado
        
        # Atajos de teclado
        QShortcut(QKeySequence('P'), self).activated.connect(self.simulate_button_press)
        QShortcut(QKeySequence('C'), self).activated.connect(self.manual_connect_arduino)
        QShortcut(QKeySequence('Escape'), self).activated.connect(self.close)
        
    def simulate_button_press(self):
        """Simula una pulsación del botón físico"""
        self.process_arduino_message("BUTTON_PRESSED")
        
    def manual_connect_arduino(self):
        """Intenta conectar con el Arduino o simula una conexión"""
        # Buscar puertos disponibles
        ports = [port.device for port in serial.tools.list_ports.comports()]
        
        if ports:
            # Intenta conectar con el primer puerto disponible
            port = ports[0]
            try:
                self.arduino_thread = ArduinoThread(port)
                self.arduino_thread.signal.connect(self.process_arduino_message)
                self.arduino_thread.start()
                self.connection_label.setText(f"CONECTADO: {port}")
                self.connection_label.setStyleSheet('color: white; background-color: #009900; border-radius: 5px; padding: 5px;')
            except Exception as e:
                # Si falla, usa simulación
                self.arduino_thread = FakeArduinoThread()
                self.connection_label.setText("MODO SIMULACIÓN")
                self.connection_label.setStyleSheet('color: white; background-color: #FF9900; border-radius: 5px; padding: 5px;')
        else:
            # No hay puertos disponibles, usar simulación
            self.arduino_thread = FakeArduinoThread()
            self.connection_label.setText("MODO SIMULACIÓN")
            self.connection_label.setStyleSheet('color: white; background-color: #FF9900; border-radius: 5px; padding: 5px;')
        
    def autoconnect_arduino(self):
        """Intenta conectar automáticamente con el Arduino al inicio"""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        
        if not ports:
            self.connection_label.setText("PULSE CONECTAR")
            self.connection_label.setStyleSheet('color: #FFCC00; background-color: #0066CC; border-radius: 5px; padding: 5px;')
            return
            
        for port in ports:
            try:
                arduino = serial.Serial(port, 9600, timeout=1)
                arduino.close()  # Solo verificamos si está disponible
                
                # Usar conexión manual con el primer puerto disponible
                self.manual_connect_arduino()
                return
            except:
                continue
                
        self.connection_label.setText("PULSE CONECTAR")
        self.connection_label.setStyleSheet('color: #FFCC00; background-color: #0066CC; border-radius: 5px; padding: 5px;')
        
    def process_arduino_message(self, message):
        """Procesa mensajes recibidos del Arduino"""
        print(f"Arduino: {message}")
        
        if message == "BUTTON_PRESSED":
            self.status_label.setText("PROCESANDO...")
            self.status_label.setStyleSheet('color: #FFCC00; font-size: 16px; font-weight: bold; background-color: transparent;')
            self.qr_label.clear()
            self.request_qr_code()
        elif "ERROR" in message:
            self.connection_label.setText(f"ERROR DE CONEXIÓN")
            self.connection_label.setStyleSheet('color: white; background-color: #CC0000; border-radius: 5px; padding: 5px;')
            
    def request_qr_code(self):
        """Solicita un nuevo código QR al servidor"""
        try:
            response = requests.get(
                "https://moradn22.pythonanywhere.com/api/generate-qr-code",
                params={"api_key": "clave_super_secreta_semaforo_song_2025"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success'):
                    is_green = data.get('is_green', True)
                    qr_image_base64 = data.get('qr_image')
                    result_command = data.get('result_command', 'SUCCESS_GREEN')
                    
                    # Mostrar QR
                    self.display_qr(qr_image_base64, is_green, result_command)
                    
                    # Enviar comando al Arduino
                    if self.arduino_thread:
                        self.arduino_thread.send_command(result_command)
                else:
                    self.status_label.setText("ERROR DE SERVIDOR")
                    self.status_label.setStyleSheet('color: white; font-size: 16px; font-weight: bold; background-color: #CC0000;')
            else:
                self.status_label.setText(f"ERROR {response.status_code}")
                self.status_label.setStyleSheet('color: white; font-size: 16px; font-weight: bold; background-color: #CC0000;')
                
        except Exception as e:
            self.status_label.setText("ERROR DE CONEXIÓN")
            self.status_label.setStyleSheet('color: white; font-size: 16px; font-weight: bold; background-color: #CC0000;')
            
    def display_qr(self, qr_image_base64, is_green, result_command):
        """Muestra el código QR en la interfaz"""
        try:
            qr_data = base64.b64decode(qr_image_base64)
            qr_img = Image.open(BytesIO(qr_data))
            
            # Convertir PIL Image a QImage
            qr_img = qr_img.convert("RGBA")
            qimage = QImage(qr_img.tobytes(), qr_img.width, qr_img.height, QImage.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qimage)
            
            # Mostrar imagen - Con tamaño MÁS GRANDE
            self.qr_label.setPixmap(pixmap.scaled(230, 230, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            
            # Actualizar estado según el comando - Estilo cartel de tráfico
            if result_command == "SUCCESS_GREEN":
                self.status_label.setText("¡VERDE! PUEDE PASAR")
                self.status_label.setStyleSheet('color: white; font-size: 16px; font-weight: bold; background-color: #009900;')
            elif result_command == "SUCCESS_YELLOW":
                self.status_label.setText("¡ÁMBAR! PRECAUCIÓN")
                self.status_label.setStyleSheet('color: black; font-size: 16px; font-weight: bold; background-color: #FFCC00;')
            elif result_command == "POLICE_SIREN":
                self.status_label.setText("¡CONTROL POLICIAL!")
                self.status_label.setStyleSheet('color: white; font-size: 16px; font-weight: bold; background-color: #0066FF;')
            elif result_command == "ERROR":
                self.status_label.setText("¡STOP! PROHIBIDO")
                self.status_label.setStyleSheet('color: white; font-size: 16px; font-weight: bold; background-color: #CC0000;')
            else:
                self.status_label.setText(f"SEÑAL: {result_command}")
                self.status_label.setStyleSheet('color: white; font-size: 16px; font-weight: bold; background-color: #666666;')
                
        except Exception as e:
            self.status_label.setText("ERROR DE IMAGEN")
            self.status_label.setStyleSheet('color: white; font-size: 16px; font-weight: bold; background-color: #CC0000;')
            
    def closeEvent(self, event):
        """Maneja el evento de cierre de la aplicación"""
        if hasattr(self.arduino_thread, 'stop'):
            self.arduino_thread.stop()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = SemaforoApp()
    sys.exit(app.exec_())
