#This is the code that runs on the controlling device (same device that drives audio)
import pystray
from PIL import Image, ImageDraw

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

icon.visible = True