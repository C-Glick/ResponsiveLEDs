#use sudo python3 <file_nanme> to run
#server side control for LED strips
#the main thread handles communication to the client and pushing frames to the framebuffer
#the light thread pulls data from the framebuffer, decodes it, and sets the led's accordingly
#frames are sent as a 2d list, one list for each pixel containing 3, 8bit integers for the R, G, and B channels  
#each frame is pickled before sent
import socket
import rpi_ws281x
from rpi_ws281x import PixelStrip, Color

import os #for restart control
import queue #queue data structure
import threading #multithreading
import pickle #serializing and deserializing data sent
import struct 
import time #wait control

#constant values------------------------------------------------------------------------
HOST = '101fdisplay.lib.iastate.edu' #server ip or hostname
PORT = 55555 #open port for communication, 1000+ recommended
MAX_DELAY = 1/60 #max delay or wait time between displayed frames = 1/min framerate
MAX_BUFFER = 30
#led strip variables and initialization
LED_COUNT = 60       # Number of LED pixels.
LED_PIN = 18          # GPIO pin connected to the pixels (18 uses PWM!).
# LED_PIN = 10        # GPIO pin connected to the pixels (10 uses SPI /dev/spidev0.0).
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10          # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 255  # Set to 0 for darkest and 255 for brightest
LED_INVERT = False    # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53

#global variables-----------------------------------------------------------------------
# Create NeoPixel object with appropriate configuration.
strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()# Intialize the library (must be called once before other functions).
frameBuffer = queue.Queue(MAX_BUFFER)    #queue to hold the frames received
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
                strip.setPixelColorRGB(i, int.from_bytes(led[0],"big"), int.from_bytes(led[1], "big"), int.from_bytes(led[2], "big"))
            strip.show()
            #sleep between frames dependent on how many frames are in the buffer
            #sleep more (lower fps) if there are fewer frames
            #time.sleep(MAX_DELAY - (MAX_DELAY/MAX_BUFFER) * frameBuffer.qsize())
            time.sleep(1/60)
        print ("Exiting " + self.name)


s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
print('Socket created')

try:
    s.bind((HOST, PORT))
except socket.error:
    print('Bind failed')

s.listen(1)
print('Socket awaiting messages')
(conn, addr) = s.accept()
print('Connected')

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

def send_msg(sock, msg):
    # Prefix each message with a 4-byte length (network byte order)
    msg = struct.pack('>I', len(msg)) + msg
    sock.sendall(msg)

def recv_msg(sock):
    # Read message length and unpack it into an integer
    raw_msglen = recvall(sock, 4)
    if not raw_msglen:
        return None
    msglen = struct.unpack('>I', raw_msglen)[0]
    # Read the message data
    return recvall(sock, msglen)

def recvall(sock, n):
    # Helper function to recv n bytes or return None if EOF is hit
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data

#start light control thread
lightControlThread = LightThread(1, "lightControlThread")
lightControlThread.start()

#start communication loop
while True:
    try:
        data = recv_msg(conn)
        #sending reply
        #send_msg(conn, b'Ok',)
        #print('Recieved: ' + data)

        if(frameBuffer.qsize() > 0.9*MAX_BUFFER):
            frameBuffer.get()

        frameBuffer.put(data)

    #client disconnected, restart socket and wait for client
    except ConnectionResetError:
        print("Client disconnected")
        #turn off all LEDs
        for frame in range(MAX_BUFFER):
            currentFrame =  [[0 for i in range(3)] for j in range(LED_COUNT)]
            for led in range(LED_COUNT):
                currentFrame[led] = [b'\x00',b'\x00',b'\x00']
            frameBuffer.put(pickle.dumps(currentFrame))

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
