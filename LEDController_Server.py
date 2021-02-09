#use sudo python3 <file_nanme> to run
#server side control for LED strips
#the main thread handles communication to the client and pushing frames to the framebuffer
#the light thread pulls data from the framebuffer, decodes it, and sets the led's accordingly
#frames are sent as a 2d list, one list for each pixel containing 3, 8bit integers for the R, G, and B chan$
#each frame is pickled before sent
import pdb
import socket
import rpi_ws281x
from rpi_ws281x import PixelStrip, Color

import os #for restart control
import queue #queue data structure
import threading #multithreading
import pickle #serializing and deserializing data sent
import struct
import time #wait control
import select #only receive data when ready

#constant values------------------------------------------------------------------------
HOST = 'pi-crglick.student.iastate.edu' #server ip or hostname
PORT = 55555 #open port for communication, 1000+ recommended
TIMEOUT = 8.0 #number of seconds to wait for a message before resetting connection, to low and can reset prematurely
MAX_FPS = 60 #Max FPS to run at
MAX_BUFFER = 30
#led strip variables and initialization
LED_COUNT = 322       # Number of LED pixels.
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
            startTime = time.time()
            frame = frameBuffer.get()

            #check frame class
            if isinstance(frame, list) and isinstance(frame[0], list):
                for i in range(len(frame)):
                    led = frame[i]
                    strip.setPixelColorRGB(i, int.from_bytes(led[0],"big"), int.from_bytes(led[1], "big"), int.from_bytes(led[2], "big"))
                
            strip.show()
            endTime = time.time()
            #frame control
            time.sleep(max(0, 1/MAX_FPS-(endTime-startTime)))

        print ("Exiting " + self.name)

#Communication helper functions ---------------------------------

def send_msg(sock, msg):
    try:
        # Prefix each message with a 4-byte length (network byte order)
        msg = struct.pack('>I', len(msg)) + msg
        sock.sendall(msg)
    except Exception as e:
        raise e

def recv_msg(sock):
    try:
        # Read message length and unpack it into an integer
        raw_msglen = recvall(sock, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        # Read the message data
        return recvall(sock, msglen)
    except Exception as e:
        raise e

def recvall(sock, n):
    # Helper function to recv n bytes or return None if EOF is hit
    data = bytearray()
    while len(data) < n:
        ready = select.select([sock], [], [], TIMEOUT)
        if ready[0]:    #if the first item in the list exists, data is ready
            packet = sock.recv(n - len(data))
        else:           #list is empty, no data within timeout period
            print("recvall timeout")
            return None
        data.extend(packet)
    return data
   

class CommThread (threading.Thread):
    def __init__(self, threadID, name, host, port):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def disconnect(self):
        print("Client disconnected")
        #turn off all LEDs
        while frameBuffer.qsize() != 0 :
            try:
                frameBuffer.get(False)
            except Exception as e:
                pass

        currentFrame =  [[0 for i in range(3)] for j in range(LED_COUNT)]
        for led in range(LED_COUNT):
            currentFrame[led] = [b'\x00',b'\x00',b'\x00']
            strip.setPixelColorRGB(led, 0, 0, 0)
        frameBuffer.put(currentFrame)
        strip.show()

        self.socket.close()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.socket.bind((HOST, PORT))
        except socket.error:
            print('Bind failed')
        self.socket.listen(1)
        print('Socket awaiting messages')
        self.conn, self.addr = self.socket.accept()
        print('Connected')
        connectedAnimation()

    def terminate(self):
        #TODO: test terminate function
        self.socket.close()
        self.conn.close()
        quit()

    def restart(self):
        #TODO: test restart function
        os.system('sudo shutdown -r now')
    
    def run(self):
        try:
            self.socket.bind((HOST, PORT))
        except socket.error:
            print('Bind failed')

        self.socket.listen(1)
        print('Socket awaiting messages')
        self.conn, self.addr = self.socket.accept()
        print('Connected')
        connectedAnimation()
        #start communication loop
        while True:
            try:
                data = recv_msg(self.conn)
                #sending reply
                #send_msg(conn, b'Ok',)
                #print('Recieved: ' + data)

                if not (data == None):
                    timeoutCount = 0
                    #TODO: pickleing is insecure, verify connection user before using any data from them
                    frame = pickle.loads(bytes(data))
                    if isinstance(frame, list):
                        frameBuffer.put(frame)
                    elif isinstance(frame, str):
                        if "disconnect" in frame:
                            self.disconnect()
                else:
                    #if data returns false, timeout has occurred, reset connection
                    self.disconnect()

                    #throw out incoming frames if the buffer is 90% full or more
                if(frameBuffer.qsize() >= 0.9*MAX_BUFFER):
                    frameBuffer.get()

            #client disconnected, restart socket and wait for client
            except ConnectionResetError:
                self.disconnect()
        self.conn.close() #close connection

def connectedAnimation():
    for led in range(LED_COUNT):
        strip.setPixelColorRGB(led, 0, 0, 0)
    strip.show()

    for led in range(9, LED_COUNT, 3):
        for i in range(5):
            strip.setPixelColorRGB(led-i, 0, 255, 20)
        for i in range(5, 9):
            strip.setPixelColorRGB(led-i, 0, 0, 0)
        strip.show()
        #time.sleep(1)


#start light control thread
lightControlThread = LightThread(1, "lightControlThread")
lightControlThread.start()

#start comm thread
commThread = CommThread(2, "commThread", HOST, PORT)
commThread.start()