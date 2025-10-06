import board
import busio
from adafruit_ssd1306 import SSD1306_I2C
from PIL import Image, ImageDraw, ImageFont

# Initialize I2C
i2c = busio.I2C(board.SCL, board.SDA)

# 128x32 is the most common size for these tiny displays
display = SSD1306_I2C(128, 32, i2c, addr=0x3c)

# Clear display
display.fill(0)
display.show()

# Create image for drawing
image = Image.new('1', (display.width, display.height))
draw = ImageDraw.Draw(image)

# Draw text (adjust y position for 32 pixel height)
draw.text((0, 0), 'Hello World!', fill=255)

# Display image
display.image(image)
display.show()

print("Display should be showing 'Hello World!'")