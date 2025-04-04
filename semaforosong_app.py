#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# SemaforoSong - Aplicación para Raspberry Pi con soporte para pantalla pequeña y simulación Arduino

import sys
import os
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QFrame, QShortcut
from PyQt5.QtGui import QPixmap, QImage, QKeySequence
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
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
        # Ajustado para pantalla de 3.5" (480x320)
        self.setGeometry(0, 0, 480, 320)
        self.showFullScreen()
        
        # Estilo general - Optimizado para pantallas pequeñas
        self.setStyleSheet("""
            QWidget {
                background-color: #1E1E1E;
                color: white;
                font-family: Arial;
            }
            QPushButton {
                background-color: #3D3D3D;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-size: 16px;
                min-height: 50px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QLabel {
                font-size: 14px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Título
        title = QLabel('SemaforoSong')
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet('font-size: 22px; font-weight: bold; color: #00A5E0;')
        layout.addWidget(title)
        
        # Estado del semáforo
        self.status_label = QLabel('Esperando...')
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet('font-size: 16px; color: white;')
        layout.addWidget(self.status_label)
        
        # Marco para la imagen QR - Optimizado para pantalla pequeña
        qr_frame = QFrame()
        qr_frame.setStyleSheet("background-color: white; border-radius: 10px;")
        qr_layout = QVBoxLayout(qr_frame)
        qr_layout.setContentsMargins(5, 5, 5, 5)
        
        # Imagen QR
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setMinimumSize(180, 180)  # Tamaño para pantalla pequeña
        self.qr_label.setMaximumSize(180, 180)
        self.qr_label.setStyleSheet("background-color: white;")
        qr_layout.addWidget(self.qr_label)
        
        layout.addWidget(qr_frame)
        
        # Estado de conexión
        self.connection_label = QLabel('Presiona C para conectar')
        self.connection_label.setAlignment(Qt.AlignCenter)
        self.connection_label.setStyleSheet('color: #FFD700; font-size: 14px;')
        layout.addWidget(self.connection_label)
        
        # Botones grandes y con atajos de teclado
        button_layout = QVBoxLayout()
        
        # Botón para simular pulsación
        self.test_button = QPushButton('SIMULAR PULSADOR (P)')
        self.test_button.clicked.connect(self.simulate_button_press)
        self.test_button.setStyleSheet("""
            QPushButton {
                background-color: #1E90FF;
                color: white;
                font-size: 16px;
                padding: 10px;
                min-height: 50px;
            }
            QPushButton:hover {
                background-color: #4169E1;
            }
        """)
        button_layout.addWidget(self.test_button)
        
        # Botón para conectar
        self.connect_button = QPushButton('CONECTAR ARDUINO (C)')
        self.connect_button.clicked.connect(self.manual_connect_arduino)
        self.connect_button.setStyleSheet("""
            QPushButton {
                background-color: #006400;
                color: white;
                font-size: 16px;
                padding: 10px;
                min-height: 50px;
            }
            QPushButton:hover {
                background-color: #008000;
            }
        """)
        button_layout.addWidget(self.connect_button)
        
        # Botón para salir
        self.exit_button = QPushButton('SALIR (ESC)')
        self.exit_button.clicked.connect(self.close)
        self.exit_button.setStyleSheet("""
            QPushButton {
                background-color: #8B0000;
                color: white;
                font-size: 16px;
                padding: 10px;
                min-height: 50px;
            }
            QPushButton:hover {
                background-color: #B22222;
            }
        """)
        button_layout.addWidget(self.exit_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
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
                self.connection_label.setText(f"Conectado a {port}")
                self.connection_label.setStyleSheet('color: green; font-size: 14px;')
            except Exception as e:
                # Si falla, usa simulación
                self.arduino_thread = FakeArduinoThread()
                self.connection_label.setText(f"Usando Arduino simulado (no real)")
                self.connection_label.setStyleSheet('color: orange; font-size: 14px;')
        else:
            # No hay puertos disponibles, usar simulación
            self.arduino_thread = FakeArduinoThread()
            self.connection_label.setText("Usando Arduino simulado (no real)")
            self.connection_label.setStyleSheet('color: orange; font-size: 14px;')
        
    def autoconnect_arduino(self):
        """Intenta conectar automáticamente con el Arduino al inicio"""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        
        if not ports:
            self.connection_label.setText("No se encontró Arduino. Presiona C.")
            self.connection_label.setStyleSheet('color: #FFD700; font-size: 14px;')
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
                
        self.connection_label.setText("No se pudo conectar. Presiona C.")
        self.connection_label.setStyleSheet('color: #FFD700; font-size: 14px;')
        
    def process_arduino_message(self, message):
        """Procesa mensajes recibidos del Arduino"""
        print(f"Arduino: {message}")
        
        if message == "BUTTON_PRESSED":
            self.status_label.setText("Procesando...")
            self.status_label.setStyleSheet('font-size: 16px; color: #FFA500;')
            self.qr_label.clear()
            self.request_qr_code()
        elif "ERROR" in message:
            self.connection_label.setText(f"Error: {message}")
            self.connection_label.setStyleSheet('color: red; font-size: 14px;')
            
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
                    self.status_label.setText("Error en la respuesta del servidor")
                    self.status_label.setStyleSheet('font-size: 16px; color: red;')
            else:
                self.status_label.setText(f"Error: {response.status_code}")
                self.status_label.setStyleSheet('font-size: 16px; color: red;')
                
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            self.status_label.setStyleSheet('font-size: 16px; color: red;')
            
    def display_qr(self, qr_image_base64, is_green, result_command):
        """Muestra el código QR en la interfaz"""
        try:
            qr_data = base64.b64decode(qr_image_base64)
            qr_img = Image.open(BytesIO(qr_data))
            
            # Convertir PIL Image a QImage
            qr_img = qr_img.convert("RGBA")
            qimage = QImage(qr_img.tobytes(), qr_img.width, qr_img.height, QImage.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qimage)
            
            # Mostrar imagen - Optimizada para pantalla pequeña
            self.qr_label.setPixmap(pixmap.scaled(180, 180, Qt.KeepAspectRatio))
            
            # Actualizar estado según el comando
            if result_command == "SUCCESS_GREEN":
                self.status_label.setText("¡VERDE! Solicita canción")
                self.status_label.setStyleSheet('font-size: 16px; color: #00FF00;')
            elif result_command == "SUCCESS_YELLOW":
                self.status_label.setText("¡ÁMBAR! Inténtalo de nuevo")
                self.status_label.setStyleSheet('font-size: 16px; color: #FFA500;')
            elif result_command == "POLICE_SIREN":
                self.status_label.setText("¡SIRENA! Inténtalo de nuevo")
                self.status_label.setStyleSheet('font-size: 16px; color: #00A5E0;')
            elif result_command == "ERROR":
                self.status_label.setText("¡ROJO! No hay más opciones")
                self.status_label.setStyleSheet('font-size: 16px; color: red;')
            else:
                self.status_label.setText(f"Resultado: {result_command}")
                
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            self.status_label.setStyleSheet('font-size: 16px; color: red;')
            
    def closeEvent(self, event):
        """Maneja el evento de cierre de la aplicación"""
        if hasattr(self.arduino_thread, 'stop'):
            self.arduino_thread.stop()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = SemaforoApp()
    sys.exit(app.exec_())
