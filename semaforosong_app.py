#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QFrame
from PyQt5.QtGui import QPixmap, QImage
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
        
        # Estilo general - Fuentes más pequeñas para pantalla menor
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
                padding: 5px;
                font-size: 14px;
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
        
        # Título - Más pequeño
        title = QLabel('SemaforoSong')
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet('font-size: 22px; font-weight: bold; color: #00A5E0;')
        layout.addWidget(title)
        
        # Estado del semáforo - Más pequeño
        self.status_label = QLabel('Esperando...')
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet('font-size: 16px; color: white;')
        layout.addWidget(self.status_label)
        
        # Marco para la imagen QR - Más pequeño para pantalla menor
        qr_frame = QFrame()
        qr_frame.setStyleSheet("background-color: white; border-radius: 10px;")
        qr_layout = QVBoxLayout(qr_frame)
        qr_layout.setContentsMargins(5, 5, 5, 5)
        
        # Imagen QR - Más pequeña
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setMinimumSize(200, 200)  # Tamaño menor
        self.qr_label.setMaximumSize(200, 200)  # Limitar tamaño máximo
        self.qr_label.setStyleSheet("background-color: white;")
        qr_layout.addWidget(self.qr_label)
        
        layout.addWidget(qr_frame)
        
        # Estado de conexión - Más pequeño
        self.connection_label = QLabel('Buscando Arduino...')
        self.connection_label.setAlignment(Qt.AlignCenter)
        self.connection_label.setStyleSheet('color: #FFD700; font-size: 12px;')
        layout.addWidget(self.connection_label)
        
        # Botón de reinicio - Más pequeño
        self.reset_button = QPushButton('Reiniciar Sistema')
        self.reset_button.clicked.connect(self.reset_system)
        self.reset_button.setStyleSheet("""
            QPushButton {
                background-color: #8B0000;
                color: white;
                font-size: 14px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #B22222;
            }
        """)
        layout.addWidget(self.reset_button)
        
        # Botón para conectar manualmente (para depuración)
        self.connect_button = QPushButton('Conectar Arduino')
        self.connect_button.clicked.connect(self.manual_connect_arduino)
        layout.addWidget(self.connect_button)
        
        self.setLayout(layout)
        
    def manual_connect_arduino(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        if not ports:
            self.connection_label.setText("No hay puertos disponibles")
            return
            
        port = ports[0]  # Usar el primer puerto disponible
        try:
            self.arduino_thread = ArduinoThread(port)
            self.arduino_thread.signal.connect(self.process_arduino_message)
            self.arduino_thread.start()
            self.connection_label.setText(f"Conectado a {port}")
            self.connection_label.setStyleSheet('color: green; font-size: 12px;')
        except Exception as e:
            self.connection_label.setText(f"Error: {str(e)}")
            self.connection_label.setStyleSheet('color: red; font-size: 12px;')
        
    def autoconnect_arduino(self):
        if self.connect_attempts > 5:
            self.connection_label.setText("No se pudo conectar. Use botón manual.")
            self.connection_label.setStyleSheet('color: red; font-size: 12px;')
            return
            
        self.connect_attempts += 1
        self.connection_label.setText(f"Buscando... (intento {self.connect_attempts})")
        
        # Imprimir puertos disponibles para depuración
        ports = [port.device for port in serial.tools.list_ports.comports()]
        print(f"Puertos disponibles: {ports}")
        
        if not ports:
            # No hay puertos disponibles, intentar de nuevo después
            QTimer.singleShot(2000, self.autoconnect_arduino)
            return
            
        for port in ports:
            try:
                print(f"Intentando puerto: {port}")
                # Intentar conectar a cada puerto
                arduino = serial.Serial(port, 9600, timeout=1)
                time.sleep(2)  # Esperar a que Arduino se reinicie
                
                # Limpiar el buffer de entrada
                arduino.reset_input_buffer()
                
                # Esperar el mensaje de inicio
                for _ in range(3):  # Intentar 3 veces
                    arduino.write(b"\n")  # Enviar un newline para despertar el Arduino
                    time.sleep(0.5)
                    if arduino.in_waiting > 0:
                        message = arduino.readline().decode('utf-8').strip()
                        print(f"Mensaje recibido: {message}")
                        if "SEMAFOROSONG_READY" in message:
                            arduino.close()  # Cerrar para que el thread pueda abrirlo
                            
                            # Iniciar hilo para comunicación con Arduino
                            self.arduino_thread = ArduinoThread(port)
                            self.arduino_thread.signal.connect(self.process_arduino_message)
                            self.arduino_thread.start()
                            
                            self.connection_label.setText(f"Conectado a {port}")
                            self.connection_label.setStyleSheet('color: green; font-size: 12px;')
                            return
                            
                arduino.close()
            except Exception as e:
                print(f"Error con puerto {port}: {str(e)}")
                continue
                
        # No se encontró, intentar de nuevo después
        QTimer.singleShot(2000, self.autoconnect_arduino)
        
    def process_arduino_message(self, message):
        print(f"Arduino: {message}")
        
        if message == "BUTTON_PRESSED":
            self.status_label.setText("Procesando...")
            self.status_label.setStyleSheet('font-size: 16px; color: #FFA500;')
            self.qr_label.clear()
            self.request_qr_code()
        elif "ERROR" in message:
            self.connection_label.setText(f"Error: {message}")
            self.connection_label.setStyleSheet('color: red; font-size: 12px;')
            
    def request_qr_code(self):
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
        try:
            qr_data = base64.b64decode(qr_image_base64)
            qr_img = Image.open(BytesIO(qr_data))
            
            # Convertir PIL Image a QImage
            qr_img = qr_img.convert("RGBA")
            qimage = QImage(qr_img.tobytes(), qr_img.width, qr_img.height, QImage.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qimage)
            
            # Mostrar imagen - Limitada a 180x180 para pantalla pequeña
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
            
    def reset_system(self):
        if self.arduino_thread:
            self.arduino_thread.send_command("RESET")
            
        self.status_label.setText("Sistema reiniciado")
        self.status_label.setStyleSheet('font-size: 16px; color: white;')
        self.qr_label.clear()
                
    def closeEvent(self, event):
        if self.arduino_thread:
            self.arduino_thread.stop()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = SemaforoApp()
    sys.exit(app.exec_())
