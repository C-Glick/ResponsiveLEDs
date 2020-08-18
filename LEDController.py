#This is the code that runs on the controlling device (same device that drives audio)
import pystray
import threading
from pystray import Icon as icon, Menu as menu, MenuItem as item
from PIL import Image, ImageDraw

class myThread (threading.Thread):
   def __init__(self, threadID, name, counter, icon):
      threading.Thread.__init__(self)
      self.threadID = threadID
      self.name = name
      self.counter = counter
      self.icon = icon
   def run(self):
      print ("Starting " + self.name)
      self.icon.run()
      print ("Exiting " + self.name)


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

#need to start this on another thread
#thread1 = myThread(1, "Thread-1", 1, icon)
#thread1.start()

icon.run()


#does not support OSX, see pystray docs
#icon.visible = True

