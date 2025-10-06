from RPLCD.i2c import CharLCD

# Common addresses are 0x27 or 0x3f
lcd = CharLCD('PCF8574', 0x27)

lcd.clear()
lcd.write_string('Hello World!')
