#This is the code that runs on the controlling device (same device that drives audio)
import pystray #lib for system tray icon
from pystray import Icon as icon, Menu as menu, MenuItem as item
from PIL import Image, ImageDraw
#lib for GUI window
import tkinter
from tkinter import Tk, DoubleVar, Scale, CENTER, HORIZONTAL, Button

#lib for system notification
from win10toast import ToastNotifier
notify = ToastNotifier()

import threading #multithreading
import time #sleep command
import socket #lib for socket communication to server
import pickle #serializing and deserializing data sent
import struct
import queue #for queue data structure

#------------------------------------------------------------------------------------------------

#global constants
LED_COUNT = 60 #60led/M 6M strip

#global variables

#global queue to hold commands to send to the server
#TODO: prioritize real time, throw out commands if falling behind too much
#hold the arrays to be sent to the server
frameBuffer = queue.Queue(30)
#the current working frame
#TODO: make sure values in frame are 8 bit numbers to reduce size as much as possible
currentFrame =  [[0 for i in range(3)] for j in range(LED_COUNT)] 
#to send command, add the method to the queue as a string
commandBuffer = queue.Queue(0)
closeLightThread = False  #set this to false to close the LightThread
isConnected = False
ledBrightness = 255
powerState = True   
currentMode = "simpleSolid"

#solid user color values
R = 255
G = 0
B = 0



#thread for communication 
#provide the host ip address or hostname
#and the port number to communicate to server
class CommThread (threading.Thread):
    def __init__(self, threadID, name, host, port):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        #self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def send_msg(self, msg):
        # Prefix each message with a 4-byte length (network byte order)
        msg = struct.pack('>I', len(msg)) + msg
        self.socket.sendall(msg)

    def recv_msg(self):
        # Read message length and unpack it into an integer
        raw_msglen = self.recvall(4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        # Read the message data
        return self.recvall(msglen)

    def recvall(self, n):
        # Helper function to recv n bytes or return None if EOF is hit
        data = bytearray()
        while len(data) < n:
            packet = self.socket.recv(n - len(data))
            if not packet:
                return None
            data.extend(packet)
        return data
    
    def run(self):
        global isConnected
        global commandBuffer
        isConnected = False
        print ("Starting " + self.name)
        print ("Starting communication...")
        #empty buffer
        commandBuffer = queue.Queue(0)
        try:
            self.socket.connect((self.host, self.port))
            isConnected = True
        except ConnectionRefusedError as e:
            notify.show_toast("Connection Refused",
                   "Check that the server is running the python script and is reachable via WiFi.\n" + 
                   "IP: " + self.host + " Port: %d" %self.port,
                   duration=20)
            #FIXME: could cause stackoverflow
            self.run()
        except TimeoutError as e:
            notify.show_toast("Connection Timeout",
                   "Check that the server is running the python script and is reachable via WiFi.\n" + 
                   "IP: " + self.host + " Port: %d" %self.port,
                   duration=20)
            #FIXME: could cause stackoverflow
            self.run()
        while True:
            try:
                frame = frameBuffer.get()
                data = pickle.dumps(frame)
                
                #send the frame to the server
                self.send_msg(data)

                
                #wait for a return message before sending the next command
                #self.recv_msg()
            #disconnected from server
            except (ConnectionAbortedError, ConnectionResetError) as e:
                print("disconnected from server")
                self.socket.close()
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                isConnected = False

                notify.show_toast("Disconnected From Sever",
                   "Check that the server is running the python script and is reachable via WiFi.\n" + 
                   "IP: " + self.host + " Port: %d" %self.port,
                   duration=20)

                self.run()

        self.socket.close()
        isConnected = False
        print ("Exiting " + self.name)

#thread for audio processing and light control
class LightThread (threading.Thread):
    def __init__(self, threadID, name, commThread):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.commThread = commThread
        
    def run(self):
        print ("Starting " + self.name)
        while not closeLightThread:
            #only proccess and push commands when connected and powered on
            if isConnected and powerState:
                print("Proccessing lights...")
                
                if(currentMode=='simpleSolid'):
                    for led in range(LED_COUNT):
                        currentFrame[led] = [bytes([int(R*ledBrightness/255)]), bytes([int(G*ledBrightness/255)]), bytes([int(B*ledBrightness/255)])]
                    frameBuffer.put(currentFrame)
                    #time.sleep(.1)
                elif(currentMode=='movieTheater'):
                    for q in range(10):
                        for i in range(0, LED_COUNT, 10):
                            currentFrame[i+q] = [bytes([int(R*ledBrightness/255)]), bytes([int(G*ledBrightness/255)]), bytes([int(B*ledBrightness/255)])]
                        frameBuffer.put(currentFrame)
                        time.sleep(20 / 1000.0)

                        for i in range(0, LED_COUNT, 10):
                            currentFrame[i+q] = [b'\x00', b'\x00', b'\x00']

                else: 
                    commandBuffer.put("print('printing from string')" )

        print ("Exiting " + self.name)

#thread for handeling the window to set the user color
class SetColorThread (threading.Thread):
    def __init__(self, threadID, name):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name

    def run(self):
        root = Tk()
        #initial window location
        #<<<<<<<<<MODIFY FOR DIFFERENT SCREEN SIZES>>>>>>>>>
        #+<width offset>+<height offset>
        root.geometry("+2250+800")

        red = DoubleVar()
        green = DoubleVar()
        blue = DoubleVar()

        #initialize the value of the UI variables equal to the global ones
        red.set(R)
        green.set(G)
        blue.set(B)

        def updateColor():
            global R
            global G
            global B

            R = red.get()
            G = green.get()
            B = blue.get()
            print(R)
            print(G)
            print(B)      

        scale = Scale( root, variable = red, label="Red Value", orient=HORIZONTAL, to=255, length=255)
        scale.pack(anchor = CENTER)
        scale = Scale( root, variable = green, label="Green Value", orient=HORIZONTAL, to=255, length=255)
        scale.pack(anchor = CENTER)
        scale = Scale( root, variable = blue, label="Blue Value", orient=HORIZONTAL, to=255, length=255)
        scale.pack(anchor = CENTER)
        button = Button(root, text = "Update", command = updateColor)
        button.pack(anchor = CENTER)

        root.mainloop()

#thread for handeling the brightness slider
class SetBrightnessThread (threading.Thread):
    def __init__(self, threadID, name):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name

    def run(self):
        root = Tk()
        #initial window location
        #<<<<<<<<<MODIFY FOR DIFFERENT SCREEN SIZES>>>>>>>>>
        #+<width offset>+<height offset>
        root.geometry("+2250+900")

        brightness = DoubleVar()
        brightness.set(ledBrightness)

        def updateBrightness():
            global ledBrightness
            ledBrightness = brightness.get()
            commandBuffer.put("strip.setBrightness(%d)" % ledBrightness)
            print(ledBrightness)      

        scale = Scale( root, variable = brightness, label="LED Brightness", orient=HORIZONTAL, to=255, length=255)
        scale.pack(anchor = CENTER)
        button = Button(root, text = "Update", command = updateBrightness)
        button.pack(anchor = CENTER)

        root.mainloop()
       

#<<<<<<<<<<<<<<<main program initialization>>>>>>>>>>>>>>>>>>>


#creates a new thread to set the user color and starts it
def setColorThreadStart():
    setColorThread = SetColorThread(3, "setColorThread", )
    setColorThread.start()

#creates a new thread to set the LED brightness and starts it
def setBrightnessThreadStart():
    setBrightnessThread = SetBrightnessThread(3, "setBrightnessThread", )
    setBrightnessThread.start()

#toggle the powerstate variable
def togglePower(icon, item):
    global powerState
    if powerState:
        powerState = False
        #TODO: push command to set all LEDs to 0 brightness
    else:
        powerState = True

#check if the given mode is the current mode
def checkMode(mode):
    def inner(item):
        return currentMode == mode
    return inner

#sets the current mode to the given mode
def setCurrentMode(mode):
    def inner(item):
        global currentMode
        currentMode = mode
    return inner

#FIXME: server side, bind failed to reconnect on client exit.
#works fine if forcefully disconnected
def exitController():
    global closeLightThread
    
    icon.stop()
    closeLightThread = True
    commandBuffer.put("close")
    commThread.join
    lightThread.join
    quit()

icon = pystray.Icon('LED Control')

#set the system tray icon
icon.icon = Image.open("icon2.png")

#setup the right-click menu
icon.menu = menu(
    item(
        text = 'Power',
        action = togglePower,
        checked = lambda item: powerState),
    
    item(
        'Responsive',
        menu(
            item(
                text = 'Mode 1',
                action = setCurrentMode('mode1'),
                checked= checkMode('mode1')
            ),
            item(
                text = 'Mode 2',
                action = setCurrentMode('mode2'),
                checked = checkMode('mode2')
            )
        )
    ),
    item(
        'Non-Responsive',
        menu(
            item(
                text = 'Set Single Color',
                action = setColorThreadStart
            ),
            item(
                text = 'Solid Color',
                action=setCurrentMode('simpleSolid'),
                checked=checkMode('simpleSolid')
            ),
            item(
                text = 'Movie Theater',
                action=setCurrentMode('movieTheater'),
                checked=checkMode('movieTheater')
            )
        )
    ),
    item(
        text = 'Brightness',
        action = setBrightnessThreadStart
    ),
    item(
        text = 'Exit',
        action = exitController
    )
)

#create the threads for communication and light processing
commThread = CommThread(1, "commThread", "101fdisplay.lib.iastate.edu",55555)
lightThread = LightThread(2, "lightThread", commThread)

#start the threads
commThread.start()
lightThread.start()

#display the icon in the system tray
#loop here listening for input
#ready for use
icon.run()