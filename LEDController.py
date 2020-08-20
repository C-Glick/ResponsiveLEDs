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
import queue #for queue data structure

#global constants
LED_COUNT = 300 #60led/M 5M strip

#global variables

#global queue to hold commands to send to the server
#TODO: prioritize real time, throw out commands if falling behind too much
#to send command, add the method to the queue as a string
commandBuffer = queue.Queue(0)
isConnected = False
ledBrightness = 255
powerState = True   
currentMode = "mode1"

#solid color values
R = 0
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
                   "Check that the server is running the python script and is available via WiFi.\n" + 
                   "IP: " + self.host + " Port: %d" %self.port,
                   duration=20)
            #FIXME: could cause stackoverflow
            self.run()
        except TimeoutError as e:
            notify.show_toast("Connection Timeout",
                   "Check that the server is running the python script and is available via WiFi.\n" + 
                   "IP: " + self.host + " Port: %d" %self.port,
                   duration=20)
            #FIXME: could cause stackoverflow
            self.run()
        while True:
            try:
                command = commandBuffer.get()
                
                #command to reconnect to server
                if "reconnect" in command:
                    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.socket.connect((self.host, self.port))
                    continue
                #special command to close the connection
                elif "close" in command:
                    #send the command to the server
                    self.socket.send(b'close')
                    break
                else:
                    #send the command to the server
                    self.socket.send(command.encode('ascii'))

                #wait for a return message before sending the next command
                reply = self.socket.recv(256)
            #disconnected from server
            except ConnectionAbortedError as e:
                print("disconnected from server")
                self.socket.close()
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
        
        self.i = 0
    def run(self):
        print ("Starting " + self.name)
        while True:
            #only proccess and push commands when connected and powered on
            if isConnected and powerState:
                self.i = self.i + 1
                print("Proccessing lights...")
                commandBuffer.put("print('printing from string %d')" % (self.i))
                time.sleep(1)

        print ("Exiting " + self.name)


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
       

#main program initialization


#creates a new thread to set the user color and starts it
def setColorThreadStart():
    setColorThread = SetColorThread(3, "setColorThread1", )
    setColorThread.start()


def togglePower(icon, item):
    global powerState
    if powerState:
        powerState = False
        #TODO: push command to set all LEDs to 0 brightness
    else:
        powerState = True

def checkMode(mode):
    def inner(item):
        return currentMode == mode
    return inner

def setCurrentMode(mode):
    def inner(item):
        global currentMode
        currentMode = mode
    return inner

icon = pystray.Icon('test name')


image = Image.open("icon2.png")

icon.icon = image
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
                text = 'Mode 4',
                action=setCurrentMode('mode4'),
                checked=checkMode('mode4')
            )
        )
    )
)


commThread = CommThread(1, "commThread1", "101fdisplay.lib.iastate.edu",55555)
lightThread = LightThread(2, "lightThread1", commThread)

commThread.start()
lightThread.start()



#display the icon in the system tray
#ready for use
icon.run()