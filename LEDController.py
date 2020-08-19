#This is the code that runs on the controlling device (same device that drives audio)
import pystray #lib for system tray icon
from pystray import Icon as icon, Menu as menu, MenuItem as item
from PIL import Image, ImageDraw

import threading #multithreading
import time #sleep command
import socket #lib for socket communication to server
import queue #for queue data structure

#global constants
LED_COUNT = 300 #60led/M 5M strip
LED_BRIGHTNESS = 255


#global queue to hold commands to send to the server
#TODO: prioritize real time, throw out commands if falling behind too much

#to send command, add the method to the queue as a string
commandBuffer = queue.Queue(0)


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
        print ("Starting " + self.name)
        print ("Starting communication...")
        self.socket.connect((self.host, self.port))
        while True:
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
                self.socket.send(command.encode('ascii'))

            #wait for a return message before sending the next command
            reply = self.socket.recv(256)

        self.socket.close()
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
            self.i = self.i + 1
            print ("processing lights...")
            commandBuffer.put("print('printing from string %d')" % (self.i))
            time.sleep(1)

        print ("Exiting " + self.name)

#main program initialization

state = False

def on_clicked(icon, item):
    global state
    state = not item.checked

icon = pystray.Icon('test name')

#In order for the icon to be displayed, we must provide an icon. This icon must be specified as a PIL.Image.Image:
# Generate an image
width = 50
height = 50

image = Image.new('RGB', (width, height), (0,0,0))
dc = ImageDraw.Draw(image)
dc.rectangle((width // 2, 0, width, height // 2), fill=(0,0,0))
dc.rectangle((0, height // 2, width // 2, height), fill=(0,0,0))

icon.icon = image
icon.menu = menu(
    item(
        'checkable',
        on_clicked,
        checked=lambda item: state))


commThread = CommThread(1, "commThread1", "101fdisplay.lib.iastate.edu",55555)
lightThread = LightThread(2, "lightThread1", commThread)

commThread.start()
lightThread.start()

#display the icon in the system tray
#ready for use
icon.run()