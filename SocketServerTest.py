#use python3 <file_nanme> to run
import socket
import rpi_ws281x
from rpi_ws281x import PixelStrip, Color

#led strip variables and initialization
LED_COUNT = 360       # Number of LED pixels.
LED_PIN = 18          # GPIO pin connected to the pixels (18 uses PWM!).
# LED_PIN = 10        # GPIO pin connected to the pixels (10 uses SPI /dev/spidev0.0).
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10          # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 255  # Set to 0 for darkest and 255 for brightest
LED_INVERT = False    # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53

# Create NeoPixel object with appropriate configuration.
strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
# Intialize the library (must be called once before other functions).
strip.begin()

HOST = '101fdisplay.lib.iastate.edu' #server ip or hostname
PORT = 55555 #open port for communication, 1000+ recommended
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
print('Socket created')

try:
        s.bind((HOST, PORT))
except socket.error:
        print('Bind failed')

s.listen(1)
print('Socket awaiting messages')
(conn, addr) = s.accept()
print('Connected')

#awaiting for message
while True:
        try:
                data = conn.recv(1024).decode('ascii')
                #sending reply
                conn.send(b'Ok')
                print('Recieved: ' + data)

                #print('I sent a message back in response to: ' + data)

                #process message
                #if data == 'Hello':
                #       reply = 'Hi back!'
                #elif data == 'important':
                #       reply = 'I have done the important thing!'
                if data == 'terminate':
                        conn.send(b'terminate')
                        break
                elif data == 'restart':
                        print('reboot')
                if data == 'close':
                        raise ConnectionResetError
                else:
                        exec(data)

        #client disconnected, restart socket and wait for client
        except ConnectionResetError as e:
                print("Client disconnected")
                s.close()
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                        s.bind((HOST, PORT))
                except socket.error:
                        print('Bind failed')
                s.listen(1)
                print('Socket awaiting messages')
                (conn, addr) = s.accept()
                print('Connected')
                continue


conn.close() #close connection
