#use sudo python3 <file_nanme> to run
import socket
import rpi_ws281x
from rpi_ws281x import PixelStrip, Color

import os #for restart control
import queue #queue data structure
import threading #multithreading
import pickle #serializing and deserializing data sent

#constant values
HOST = '101fdisplay.lib.iastate.edu' #server ip or hostname
PORT = 55555 #open port for communication, 1000+ recommended
#led strip variables and initialization
LED_COUNT = 60       # Number of LED pixels.
LED_PIN = 18          # GPIO pin connected to the pixels (18 uses PWM!).
# LED_PIN = 10        # GPIO pin connected to the pixels (10 uses SPI /dev/spidev0.0).
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10          # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 255  # Set to 0 for darkest and 255 for brightest
LED_INVERT = False    # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53

#global variables
# Create NeoPixel object with appropriate configuration.
strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()# Intialize the library (must be called once before other functions).

frameBuffer = queue.Queue(0)    #queue to hold the frames received
closeLightThread = False        #set this to true to close the light thread


#thread for light control
class LightThread (threading.Thread):
		def __init__(self, threadID, name):
				threading.Thread.__init__(self)
				self.threadID = threadID
				self.name = name

		def run(self):
				print ("Starting " + self.name)
				while not closeLightThread:
						data = frameBuffer.get()
						#TODO: pickleing is insecure, verify connection user before using any data from them
						frame = pickle.loads(bytes(data))
						for i in range(len(frame)):
								led = frame[i]
								#print(led)
								strip.setPixelColorRGB(i, int.from_bytes(led[0],"big"), int.from_bytes(led[1], "big"), int.from_bytes(led[2], "big"))
						strip.show()
				print ("Exiting " + self.name)


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

def setAllPixelColorRGB(r, g, b):
				for i in range(LED_COUNT):
								strip.setPixelColorRGB(i, r, g, b)

def close():
				raise ConnectionResetError

def terminate():
				#TODO: test terminate function
				s.close()
				conn.close()
				quit()
def restart():
				#TODO: test restart function
				os.system('sudo shutdown -r now')

#start light control thread
lightControlThread = LightThread(1, "lightControlThread")
lightControlThread.start()

#start communication loop
while True:
				try:
								#TODO:  pickle trucating issue
								data = conn.recv(4096)
								#sending reply
								conn.send(b'Ok')
								#print('Recieved: ' + data)

								#print('I sent a message back in response to: ' + data)

								#process message
								#if data == 'Hello':
								#       reply = 'Hi back!'
								#elif data == 'important':
								#       reply = 'I have done the important thing!'
								frameBuffer.put(data)



				#client disconnected, restart socket and wait for client
				except ConnectionResetError:
								print("Client disconnected")
								setAllPixelColorRGB(0,0,0)
								strip.show()

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
