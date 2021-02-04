#This is the code that runs on the controlling device (same device that drives audio)
import pystray #lib for system tray icon
from pystray import Icon as icon, Menu as menu, MenuItem as item
from PIL import Image, ImageDraw
import sys
import configparser #library for config file handling
import os.path #lib for checking if config file exists
from os import path
#lib for GUI window
import tkinter
from tkinter import Tk, DoubleVar, Scale, CENTER, HORIZONTAL, Button

#lib for system notification
from win10toast import ToastNotifier
notify = ToastNotifier()

#lib for audio processing
from Realtime_pyaudio_ftt.src.stream_analyzer import Stream_Analyzer
import colorsys

import threading #multithreading
import time #sleep command
import socket #lib for socket communication to server
import pickle #serializing and deserializing data sent
import struct
import queue #for queue data structure
import math
import numpy as np
import collections

#constants---------------------------------------------------------------------
#values are set from the config file
LED_COUNT = 0
RIGHT_SECTION = 0
TOP_SECTION = 0
LEFT_SECTION = 0
BOTTOM_SECTION = 0
MAX_FPS = 0 #limit the number of frames sent to the server per second, lower fps can reduce delay 
            #50 percent MAX_FPS for solid modes to reduce unneeded network usage
HOST = ""
PORT = 0

#global variables--------------------------------------------------------------

#frames to be sent to the server
frameBuffer = queue.Queue(30)
#the current working frame
currentFrame =  [[b'\x00' for i in range(3)] for j in range(LED_COUNT)]
pulseList = [] #list to hold pulses 
#to send frame, frameBuffer.put(currentFrame)
#TODO: buffer to send commands such as reboot.
commandBuffer = queue.Queue(0)
closeLightThread = False  #set this to true to close the LightThread
closeCommThread = False #set this to true to close the commThread
isConnected = False #true if connected to the server
ledBrightness = 0
frameCount = 0
animationSpeed = 0
powerState = True
currentMode = ""

#solid user color values
R = 0
G = 0
B = 0

#config-----------------------------------------------------------------------
#check if config file exists, if it does, read from it and set variables accordingly
#if does not exist, creates one with default settings values
def readConfig():

    global LED_COUNT
    global currentFrame
    global HOST
    global PORT
    global MAX_FPS
    global RIGHT_SECTION
    global TOP_SECTION
    global LEFT_SECTION
    global BOTTOM_SECTION
    global ledBrightness
    global animationSpeed
    global currentMode
    global R
    global G
    global B


    config = configparser.ConfigParser(allow_no_value=True)

    
    if(path.exists("config.ini")):
        #load config file
        config.read("config.ini")

        bothConfig = config['CHANGE_ON_SERVER_TOO']

        LED_COUNT = int(bothConfig['led_count'])
        currentFrame =  [[b'\x00' for i in range(3)] for j in range(LED_COUNT)]
        HOST = bothConfig['host']
        PORT = int(bothConfig['port'])

        clientConfig = config['CLIENT_ONLY_SETTINGS']

        MAX_FPS = int(clientConfig['max_fps'])
        RIGHT_SECTION = [int(clientConfig['right_section_start']),int(clientConfig['right_section_end'])]
        TOP_SECTION = [int(clientConfig['top_section_start']),int(clientConfig['top_section_end'])]
        LEFT_SECTION = [int(clientConfig['left_section_start']),int(clientConfig['left_section_end'])]
        BOTTOM_SECTION = [int(clientConfig['bottom_section_start']),int(clientConfig['bottom_section_end'])]
        ledBrightness = int(clientConfig['led_brightness'])
        animationSpeed = float(clientConfig['animation_speed'])
        currentMode = clientConfig['current_mode']
        R = int(clientConfig['r'])
        G = int(clientConfig['g'])
        B = int(clientConfig['b'])

    else:
        #write default settings to config.ini
        config['CHANGE_ON_SERVER_TOO'] = {
            '# these values need to be changed on both the client and the server side': None,
            'led_count': 322,
            'host': 'pi-crglick.student.iastate.edu',
            'port' : 55555,
        }

        config['CLIENT_ONLY_SETTINGS'] = {
            'max_fps': 30,
            'right_section_start': 0,
            'right_section_end': 35,
            'top_section_start': 36,
            'top_section_end': 161,
            'left_section_start': 162,
            'left_section_end': 197,
            'bottom_section_start': 198,
            'bottom_section_end': 322,
            'led_brightness': 255,
            'animation_speed': 50,
            'current_mode': 'simpleSolid',
            '# Current user color, 0-255': None,
            'r': 255,
            'g': 0,
            'b': 0
            
        }
        with open("config.ini", 'w') as configFile:
            config.write(configFile)
        #load default settings
        readConfig()
readConfig()

#update the config file with the current settings
def updateConfig():
    config = configparser.ConfigParser(allow_no_value=True)

    config['CHANGE_ON_SERVER_TOO'] = {
        '# these values need to be changed on both the client and the server side': None,
        'led_count': LED_COUNT,
        'host': HOST,
        'port' : PORT,
    }

    config['CLIENT_ONLY_SETTINGS'] = {
        'max_fps': int(MAX_FPS),
        'right_section_start': RIGHT_SECTION[0],
        'right_section_end': RIGHT_SECTION[1],
        'top_section_start': TOP_SECTION[0],
        'top_section_end': TOP_SECTION[1],
        'left_section_start': LEFT_SECTION[0],
        'left_section_end': LEFT_SECTION[1],
        'bottom_section_start': BOTTOM_SECTION[0],
        'bottom_section_end': BOTTOM_SECTION[1],
        'led_brightness': int(ledBrightness),
        'animation_speed': animationSpeed,
        'current_mode': currentMode,
        '# Current user color, 0-255': None,
        'r': int(R),
        'g': int(G),
        'b': int(B)
        
    }
    with open("config.ini", 'w') as configFile:
        config.write(configFile)


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
        self.socket = None

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

    def socketConnect(self):
        global isConnected
        #set socket object
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        #self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        self.socket.connect((self.host, self.port))
        print("Connected")
        isConnected = True
        
    def socketDisconnect(self):
        global isConnected
        self.socket.close()
        isConnected = False

    def run(self):
        global commandBuffer
        print ("Starting " + self.name)
        print ("Starting communication...")
        #empty buffer
        commandBuffer = queue.Queue(0)
        while not closeCommThread:
            try:
                if(isConnected): self.socketDisconnect()
                self.socketConnect()
            except ConnectionRefusedError as e:
                notify.show_toast("Connection Refused",
                    "Check that the server is running the python script and is reachable via WiFi.\n" + 
                    "IP: " + self.host + " Port: %d" %self.port,
                    duration=20, threaded=True)
                continue
            except TimeoutError as e:
                notify.show_toast("Connection Timeout",
                    "Check that the server is running the python script and is reachable via WiFi.\n" + 
                    "IP: " + self.host + " Port: %d" %self.port,
                    duration=20, threaded=True)
                continue
            except socket.gaierror as e:
                notify.show_toast("Could Not Resolve Address",
                    "Check that the server is running the python script and is reachable via WiFi.\n" + 
                    "IP: " + self.host + " Port: %d" %self.port,
                    duration=20, threaded=True)
                continue
            while not closeCommThread:
                try:
                    frame = frameBuffer.get()
                    data = pickle.dumps(frame)
                    
                    #send the frame to the server
                    self.send_msg(data)

                    try:
                        command = commandBuffer.get(False)
                        data = pickle.dumps(command)
                        self.send_msg(data)
                    except queue.Empty as e:
                        pass
                    
                    #wait for a return message before sending the next command
                    #self.recv_msg()
                #disconnected from server
                except (ConnectionAbortedError, ConnectionResetError) as e:
                    print("Disconnected from server")
                    self.socketDisconnect()

                    notify.show_toast("Disconnected From Sever",
                    "Check that the server is running the python script and is reachable via WiFi.\n" + 
                    "IP: " + self.host + " Port: %d" %self.port,
                    duration=20, threaded=True)

                    break

        self.socketDisconnect()
        print ("Exiting " + self.name)

#Represents a pulse that travels down the strip
#
#position, int,
#the position is always defined as the lowest index led in the pulse,
#or the left side of the pulse, if the strips leds are in increasing order
#from left to right,
#EX: position = 1 and length = 4
# [led0] [led1] [led2] [led3] [led4] [led5] [led6]...
#   x     pos.  pos+1  pos+2  pos+3    x      x
#
#Position can be negative or above LED_COUNT as long as position+length is not
#
#Length, int, the number of pixels lit by each pulse
#
#velocity, float, the number of pixels to move each frame, neg. or pos.
#
#fadeRate, float, the rate at which brightness will decrease each frame
#
#loop, boolean, if the pulse should loop to the other end of the strip or not
#
#R, G, B, int 0-255, the color of the pulse
class Pulse ():
    def __init__(self, position, length, velocity, fadeRate, loop, R, G, B):
        self.position = position
        self.length = length
        self.velocity = velocity
        self.fadeRate = -abs(fadeRate)
        self.brightness = 255  #always start at max brightness
        self.loop = loop
        self.R = R
        self.G = G
        self.B = B
    
    def draw(self):
        for led in range(self.length):
            led = int(led + self.position)
            if(self.loop == True):
                #pulse on lower end of strip
                if led < 0:
                    led = (LED_COUNT-1)+led
                #pulse on upper end of strip
                elif led >= LED_COUNT:
                    led = led - (LED_COUNT)
            elif not (0<= led < LED_COUNT):
                continue

            #mix colors
            #red = int(min(255, int.from_bytes(currentFrame[led][0], "big") + (self.R*self.brightness*ledBrightness)/65025))
            #green = int(min(255, int.from_bytes(currentFrame[led][1], "big") + (self.G*self.brightness*ledBrightness)/65025))
            #blue = int(min(255, int.from_bytes(currentFrame[led][2], "big") + (self.B*self.brightness*ledBrightness)/65025))

            red = int(min(255, (self.R*self.brightness*ledBrightness)/65025))
            green = int(min(255, (self.G*self.brightness*ledBrightness)/65025))
            blue = int(min(255, (self.B*self.brightness*ledBrightness)/65025))

            currentFrame[led] = [bytes([red]), bytes([green]), bytes([blue])]

class PulseManager():
    def update():
        global pulseList
        global currentFrame

        #clear frame
        for led in range(LED_COUNT):
            currentFrame[led] = [b'\x00', b'\x00', b'\x00']

        for pulse in pulseList:
            pulse.position = pulse.position + pulse.velocity
            if(pulse.position < 0): pulse.position = LED_COUNT-1
            if(pulse.position >= LED_COUNT): pulse.position = 0

            pulse.brightness = pulse.brightness + pulse.fadeRate

            if int(pulse.brightness) <= 0:
                pulseList.remove(pulse) #pulse has 0 brightness
                continue

            if(not pulse.loop):
                if (pulse.position + pulse.length < 0 or pulse.position - pulse.length > LED_COUNT) :
                    pulseList.remove(pulse) #pulse has reached the end of the lights
                    continue

            pulse.draw()
        frameBuffer.put(currentFrame)

#thread for audio processing and light control
class LightThread (threading.Thread):
    def __init__(self, threadID, name, commThread):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.commThread = commThread
        self.pulseManager = PulseManager()

        self.frequencyBins = 300
        self.minAmp = 0.01 #the minimum amplitude allowed for visualization (to not visualize noise)
        self.triggerPercent = 6 #if amp > average amp * triggerPercent, then trigger a visualization event
        self.numAudioHistory = 30 # the number of frames to hold in memory when calculating average

        self.audio = Stream_Analyzer(
                device = 2,               # Manually play with this (int) if you don't see anything
                rate   = None,               # Audio samplerate, None uses the default source settings
                FFT_window_size_ms  = 60,    # Window size used for the FFT transform
                updates_per_second  = 3000,  # How often to read the audio stream for new data
                smoothing_length_ms = 50,    # Apply some temporal smoothing to reduce noisy features
                n_frequency_bins    = self.frequencyBins,   # The FFT features are grouped in bins
                visualize = 0,               # Visualize the FFT features with PyGame
                verbose   = 0                # Print running statistics (latency, fps, ...)
                )

    def num_to_rgb(self, val, max_val):
        i = (val * 255 / max_val)
        r = round(math.sin(0.024 * i + 0) * 127 + 128)
        g = round(math.sin(0.024 * i + 2) * 127 + 128)
        b = round(math.sin(0.024 * i + 4) * 127 + 128)
        return (r,g,b)


    def run(self):
        global frameCount
        global R
        global G
        global B

        #Audio visualizer data       
        history =  collections.deque(maxlen=self.numAudioHistory)
        averageBinAmp = [0] * self.frequencyBins 

        print ("Starting " + self.name)
        while not closeLightThread:
            #only proccess and push commands when connected and powered on
            if isConnected and powerState:
                startTime = time.time()
    #------------------non-responsive modes-------------
                if(currentMode=='simpleSolid'):
                    for led in range(LED_COUNT):
                        currentFrame[led] = [bytes([int(R*ledBrightness/255)]), bytes([int(G*ledBrightness/255)]), bytes([int(B*ledBrightness/255)])]
                    frameBuffer.put(currentFrame)
                    #time.sleep(.1)
                elif(currentMode=='topSolid'):
                    #before section
                    for led in range(0, TOP_SECTION[0]):
                        currentFrame[led] = [b'\x00', b'\x00', b'\x00']

                    for led in range(TOP_SECTION[0], TOP_SECTION[1]):
                        currentFrame[led] = [bytes([int(R*ledBrightness/255)]), bytes([int(G*ledBrightness/255)]), bytes([int(B*ledBrightness/255)])]
                    
                    #after section
                    for led in range(TOP_SECTION[1], LED_COUNT):
                        currentFrame[led] = [b'\x00', b'\x00', b'\x00']

                    frameBuffer.put(currentFrame)
                elif(currentMode=='bottomSolid'):
                    #before section
                    for led in range(0, BOTTOM_SECTION[0]):
                        currentFrame[led] = [b'\x00', b'\x00', b'\x00']

                    for led in range(BOTTOM_SECTION[0], BOTTOM_SECTION[1]):
                        currentFrame[led] = [bytes([int(R*ledBrightness/255)]), bytes([int(G*ledBrightness/255)]), bytes([int(B*ledBrightness/255)])]
                    
                    #after section
                    for led in range(BOTTOM_SECTION[1], LED_COUNT):
                        currentFrame[led] = [b'\x00', b'\x00', b'\x00']

                    frameBuffer.put(currentFrame)
                elif(currentMode=='topAndBottomSolid'):
                    #before section
                    for led in range(0, TOP_SECTION[0]):
                        currentFrame[led] = [b'\x00', b'\x00', b'\x00']

                    for led in range(TOP_SECTION[0], TOP_SECTION[1]):
                        currentFrame[led] = [bytes([int(R*ledBrightness/255)]), bytes([int(G*ledBrightness/255)]), bytes([int(B*ledBrightness/255)])]
                    
                    #between sections
                    for led in range(TOP_SECTION[1], BOTTOM_SECTION[0]):
                        currentFrame[led] = [b'\x00', b'\x00', b'\x00']

                    for led in range(BOTTOM_SECTION[0], BOTTOM_SECTION[1]):
                        currentFrame[led] = [bytes([int(R*ledBrightness/255)]), bytes([int(G*ledBrightness/255)]), bytes([int(B*ledBrightness/255)])]
                    
                    #after section
                    for led in range(BOTTOM_SECTION[1], LED_COUNT):
                        currentFrame[led] = [b'\x00', b'\x00', b'\x00']

                    frameBuffer.put(currentFrame)
                elif(currentMode=='leftSolid'):
                    #before section
                    for led in range(0, LEFT_SECTION[0]):
                        currentFrame[led] = [b'\x00', b'\x00', b'\x00']

                    for led in range(LEFT_SECTION[0], LEFT_SECTION[1]):
                        currentFrame[led] = [bytes([int(R*ledBrightness/255)]), bytes([int(G*ledBrightness/255)]), bytes([int(B*ledBrightness/255)])]
                    
                    #after section
                    for led in range(LEFT_SECTION[1], LED_COUNT):
                        currentFrame[led] = [b'\x00', b'\x00', b'\x00']

                    frameBuffer.put(currentFrame)
                elif(currentMode=='rightSolid'):
                    #before section
                    for led in range(0, RIGHT_SECTION[0]):
                        currentFrame[led] = [b'\x00', b'\x00', b'\x00']

                    for led in range(RIGHT_SECTION[0], RIGHT_SECTION[1]):
                        currentFrame[led] = [bytes([int(R*ledBrightness/255)]), bytes([int(G*ledBrightness/255)]), bytes([int(B*ledBrightness/255)])]
                    
                    #after section
                    for led in range(RIGHT_SECTION[1], LED_COUNT):
                        currentFrame[led] = [b'\x00', b'\x00', b'\x00']

                    frameBuffer.put(currentFrame)
                elif(currentMode=='sidesSolid'):
                    #before section
                    for led in range(0, RIGHT_SECTION[0]):
                        currentFrame[led] = [b'\x00', b'\x00', b'\x00']

                    for led in range(RIGHT_SECTION[0], RIGHT_SECTION[1]):
                        currentFrame[led] = [bytes([int(R*ledBrightness/255)]), bytes([int(G*ledBrightness/255)]), bytes([int(B*ledBrightness/255)])]
                    
                    #between sections
                    for led in range(RIGHT_SECTION[1], LEFT_SECTION[0]):
                        currentFrame[led] = [b'\x00', b'\x00', b'\x00']

                    for led in range(LEFT_SECTION[0], LEFT_SECTION[1]):
                        currentFrame[led] = [bytes([int(R*ledBrightness/255)]), bytes([int(G*ledBrightness/255)]), bytes([int(B*ledBrightness/255)])]
                    
                    #after section
                    for led in range(LEFT_SECTION[1], LED_COUNT):
                        currentFrame[led] = [b'\x00', b'\x00', b'\x00']

                    frameBuffer.put(currentFrame)
                elif(currentMode=='breathe'):
                    for led in range(LED_COUNT):
                        breatheBrightness = 0.5 + 0.5 * math.cos(animationSpeed/300 * frameCount)
                        currentFrame[led] = [bytes([int((R*breatheBrightness*ledBrightness)/255)]), bytes([int((G*breatheBrightness*ledBrightness)/255)]), bytes([int((B*breatheBrightness*ledBrightness)/255)])]
                    frameBuffer.put(currentFrame)
                                 
                elif(currentMode=='movieTheater'):
                    for q in range(14):
                        for i in range(0, LED_COUNT, 14):
                            currentFrame[i+q] = [bytes([int(R*ledBrightness/255)]), bytes([int(G*ledBrightness/255)]), bytes([int(B*ledBrightness/255)])]
                        frameBuffer.put(currentFrame)
                        #(wait time, 0.15s - 0s ) + specific pattern wait time 
                        time.sleep((0.10-(animationSpeed/1000)) +0.01 )

                        for i in range(0, LED_COUNT, 14):
                            currentFrame[i+q] = [b'\x00', b'\x00', b'\x00']
                elif(currentMode == 'rainbow'):
                    for led in range(LED_COUNT):
                        #set the hue to a value between 0 and 1, hue is based on led number
                        #and frameCount to get a rainbow animation
                        #speed is controlled by multiplying frame count by animation speed
                        #size of rainbow is controlled by the constant on LED_COUNT
                        hue = (led + (frameCount * animationSpeed / 10))/(LED_COUNT / 2)
                        hue = hue - int(hue)

                        (r,g,b) = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                        red, green, blue = int(r * ledBrightness), int(g * ledBrightness), int(b * ledBrightness)
                        currentFrame[led] = [bytes([red]), bytes([green]), bytes([blue])]
                    frameBuffer.put(currentFrame)
    #-----------Responsive modes----------------
                elif(currentMode=='pulse'):
                    PulseManager.update()
                    raw_fftx, raw_fft, binned_fftx, binned_fft = self.audio.get_audio_features()

                    for freq in range(len(binned_fft)):
                        amp= binned_fft[freq]

                        if(amp>self.minAmp):
                            if(amp > averageBinAmp[freq] * self.triggerPercent):
                                pulseList.insert(0, Pulse(0, 2, 2, max(2, 10 * averageBinAmp[freq]/amp), False, *(self.num_to_rgb(freq, self.frequencyBins/2))))

                    #push current data to history and recalculate averages
                    history.append(binned_fft)

                    #find the average amplitude for each frequency
                    for freq in range(len(history[0])):
                        sum=0
                        for frame in range(len(history)):
                            sum += history[frame][freq]
                        averageBinAmp[freq] = sum/len(history)

                elif(currentMode=='waveform'):
                    startLED = LEFT_SECTION[1]
                    endLED = RIGHT_SECTION[0]

                    #clear frame
                    for led in range(LED_COUNT):
                        currentFrame[led] = [b'\x00', b'\x00', b'\x00']

                    raw_fftx, raw_fft, binned_fftx, binned_fft = self.audio.get_audio_features()
                    #push current data to history and recalculate averages
                    history.append(binned_fft)

                    #map amplitude to brightness
                    maxAmp = max(binned_fft)
                    maxBrightness = 255
                    minAmp = min(binned_fft)
                    minBrightness = -5

                    for freq in range(len(binned_fft)):
                        amp= binned_fft[freq]
                        led = startLED + int(freq * (endLED - startLED) / len(binned_fft))

                        #translate amplitude to led brightness, max amp = max brightness, min amp = minBrightness
                        #floor of 0
                        #y=(y2-y1)/(x2-x1) * (x - x2) + y2
                        audioBrightness = max(0, ((maxBrightness - minBrightness) / (maxAmp - minAmp) * (amp - maxAmp) + maxBrightness) )

                        if(amp>self.minAmp):
                            currentFrame[led] = [bytes([int((R * ledBrightness * audioBrightness / 65025) )]),
                                                 bytes([int((G * ledBrightness * audioBrightness / 65025) )]),
                                                 bytes([int((B * ledBrightness * audioBrightness / 65025) )])]
                        else:
                            currentFrame[led] = [b'\x00', b'\x00', b'\x00']


                    frameBuffer.put(currentFrame)
                elif(currentMode=='rainbowWaveform'):
                    startLED = LEFT_SECTION[1]
                    endLED = RIGHT_SECTION[0]

                    #clear frame
                    for led in range(LED_COUNT):
                        currentFrame[led] = [b'\x00', b'\x00', b'\x00']
                  

                    raw_fftx, raw_fft, binned_fftx, binned_fft = self.audio.get_audio_features()
                    #push current data to history and recalculate averages
                    history.append(binned_fft)

                    #map amplitude to brightness
                    maxAmp = max(binned_fft)
                    maxBrightness = 255
                    minAmp = min(binned_fft)
                    minBrightness = -5

                    for freq in range(len(binned_fft)):
                        amp= binned_fft[freq]
                        led = startLED + int(freq * (endLED - startLED) / len(binned_fft))
                        
                        if(amp>self.minAmp):
                            #translate amplitude to led brightness, max amp = max brightness, min amp = minBrightness
                            #floor of 0
                            #y=(y2-y1)/(x2-x1) * (x - x2) + y2
                            audioBrightness = max(0, ((maxBrightness - minBrightness) / (maxAmp - minAmp) * (amp - maxAmp) + maxBrightness) )

                            #calculate colors
                            #set the hue to a value between 0 and 1, hue is based on led number
                            #and frameCount to get a rainbow animation
                            #speed is controlled by multiplying frame count by animation speed
                            #size of rainbow is controlled by the constant on LED_COUNT
                            hue = (led + (frameCount * animationSpeed / 10))/(LED_COUNT / 2)
                            hue = hue - int(hue)

                            (r,g,b) = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                        
                            currentFrame[led] = [bytes([int((r * ledBrightness * audioBrightness / 255) )]),
                                                 bytes([int((g * ledBrightness * audioBrightness / 255) )]),
                                                 bytes([int((b * ledBrightness * audioBrightness / 255) )])]
                        else:
                            currentFrame[led] = [b'\x00', b'\x00', b'\x00']


                    frameBuffer.put(currentFrame)

                endTime = time.time()
                
                #framerate cap
                if currentMode.find("Solid") != -1:
                    time.sleep(max(0, 1/(MAX_FPS*0.5)-(endTime-startTime)))     #50 percent MAX_FPS for solid modes to reduce unneeded network usage
                else:
                    time.sleep(max(0, 1/MAX_FPS-(endTime-startTime)))
                frameCount = frameCount + 1

            elif(isConnected and not powerState):
                for led in range(LED_COUNT):
                    currentFrame[led] = [b'\x00', b'\x00', b'\x00']
                frameBuffer.put(currentFrame)
                time.sleep(1)

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
            updateConfig()     

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
            updateConfig()     

        scale = Scale( root, variable = brightness, label="LED Brightness", orient=HORIZONTAL, to=255, length=255)
        scale.pack(anchor = CENTER)
        button = Button(root, text = "Update", command = updateBrightness)
        button.pack(anchor = CENTER)

        root.mainloop()

#thread for handeling the speed slider
class SetSpeedThread (threading.Thread):
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

        speed = DoubleVar()
        speed.set(animationSpeed)

        def updateSpeed():
            global animationSpeed
            animationSpeed = speed.get()
            updateConfig()

        scale = Scale( root, variable = speed, label="Animation Speed", orient=HORIZONTAL, from_=1, to=100, length=255, resolution=0.1)
        scale.pack(anchor = CENTER)
        button = Button(root, text = "Update", command = updateSpeed)
        button.pack(anchor = CENTER)

        root.mainloop()
       
       

#main program initialization-----------------------------------------------

#creates a new thread to set the user color and starts it
def setColorThreadStart():
    setColorThread = SetColorThread(3, "setColorThread", )
    setColorThread.start()

#creates a new thread to set the animation speed and starts it
def setSpeedThreadStart():
    setSpeedThread = SetSpeedThread(3, "setSpeedThread", )
    setSpeedThread.start()

#creates a new thread to set the LED brightness and starts it
def setBrightnessThreadStart():
    setBrightnessThread = SetBrightnessThread(3, "setBrightnessThread", )
    setBrightnessThread.start()

#toggle the powerstate variable
def togglePower(icon, item):
    global powerState
    if powerState:
        powerState = False
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
        updateConfig()
    return inner

def exitController():
    global closeLightThread
    global closeCommThread
    
    commandBuffer.put("disconnect")
    time.sleep(0.1)

    closeCommThread = True
    commThread.join
    closeLightThread = True
    lightThread.join

    icon.stop()
    os._exit(0)

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
                text = 'Pulse ',
                action = setCurrentMode('pulse'),
                checked= checkMode('pulse')
            ),
            item(
                text = 'Waveform',
                action = setCurrentMode('waveform'),
                checked = checkMode('waveform')
            ),
            item(
                text = 'Rainbow Waveform',
                action = setCurrentMode('rainbowWaveform'),
                checked = checkMode('rainbowWaveform')
            )
        )
    ),
    item(
        'Non-Responsive',
        menu(
            item(
                text = 'Solid Color',
                action=setCurrentMode('simpleSolid'),
                checked=checkMode('simpleSolid')
            ),
            item(
                text = 'Top Solid',
                action=setCurrentMode('topSolid'),
                checked=checkMode('topSolid')
            ),
            item(
                text = 'Bottom Solid',
                action=setCurrentMode('bottomSolid'),
                checked=checkMode('bottomSolid')
            ),
            item(
                text = 'Top and Bottom Solid',
                action=setCurrentMode('topAndBottomSolid'),
                checked=checkMode('topAndBottomSolid')
            ), 
            item(
                text = 'Left Solid',
                action=setCurrentMode('leftSolid'),
                checked=checkMode('leftSolid')
            ),
            item(
                text = 'Right Solid',
                action=setCurrentMode('rightSolid'),
                checked=checkMode('rightSolid')
            ),
            item(
                text = 'Sides Solid',
                action=setCurrentMode('sidesSolid'),
                checked=checkMode('sidesSolid')
            ),             
            item(
                text = 'Movie Theater',
                action=setCurrentMode('movieTheater'),
                checked=checkMode('movieTheater')
            ),
            item(
                text = 'Breathe',
                action=setCurrentMode('breathe'),
                checked=checkMode('breathe')
            ),
            item(
                text = 'Rainbow',
                action=setCurrentMode('rainbow'),
                checked=checkMode('rainbow')
            )
        )
    ),
    item(
        text = 'Set Brightness',
        action = setBrightnessThreadStart
    ),
    item(
        text = 'Set Color',
        action = setColorThreadStart
    ),
    item(
        text = 'Set Speed',
        action = setSpeedThreadStart
    ),
    item(
        text = 'Exit',
        action = exitController
    )
)

#create the threads for communication and light processing
commThread = CommThread(1, "commThread", HOST,PORT)
lightThread = LightThread(2, "lightThread", commThread)

#start the threads
commThread.start()
lightThread.start()

#display the icon in the system tray
#loop here listening for input
#ready for use
icon.run()