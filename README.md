# ResponsiveLEDs
A Python program to drive an addressable LED strip based on system audio

Audio and light processing is done on the host device and individual frames are sent to the raspberry pi. Sends data over wifi to raspberry Pi where it is then decoded and used to update the LED strip.


## Todo
- Data compression and other speed optimizations
- Adjustable color presets
- Additional pulse patterns
- Fire animation
- Day/night animation based on time of day
- Animation based on weather


## Auto start with windows
- use task scheduler 
- new task
    - name = LED_Controller
    - action, start a program
        - program / script points to pythonw.exe `C:\Users\<userName>\AppData\Local\Programs\Python\Python38-32\pythonw.exe`
        - argument is the script name `LEDController_Client.pyw`
        - start in, folder containing the script `C:\Users\<userName>\git\ResponsiveLEDs`
    - Trigger, at log on
        - any user
        - enabled
