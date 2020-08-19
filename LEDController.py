#This is the code that runs on the controlling device (same device that drives audio)
import pystray #lib for system tray icon
from pystray import Icon as icon, Menu as menu, MenuItem as item
from PIL import Image, ImageDraw

import threading #multithreading
import time #sleep command
import socket #lib for socket communication to server
import queue #for queue data structure

#global queue to hold commands to send to the server
#TODO: prioritize real time, throw out commands if falling behind too much
commandBuffer = queue.Queue(0)
commandBuffer.put("test")


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
        print ("Starting communicating...")
        self.socket.connect((self.host, self.port))
        while True:
            try:
                #FIXME: sending multiple commands at a time, need a way to separate commands when sending, space between commands? semicolon?
                command = commandBuffer.get()
            except queue.Empty:
                print("commandBuffer empty")
                continue

            #command to reconnect to server
            if command == "reconnect":
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect((self.host, self.port))
                continue
            
            #send the command to the server
            self.socket.send(command.encode('ascii'))
            
            #special command to close the connection
            if command == "close":
                break
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
            commandBuffer.put("test%d" % (self.i))
            time.sleep(.001)

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


commThread = CommThread(1, "commThread1", "10.37.11.78",55555)
lightThread = LightThread(2, "lightThread1", commThread)

commThread.start()
lightThread.start()

#display the icon in the system tray
#ready for use
icon.run()