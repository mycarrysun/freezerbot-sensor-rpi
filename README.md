# Freezerbot Sensor Firmware (Raspberry Pi)

## Hardware Wiring

Components:
- Raspberry Pi Zero W
- Momentary push button with built-in LED (waterproof, 16mm or larger)
- Temperature sensor (DS18B20 or similar)
- Case with button mounting hole

GPIO Connections:
1. Button with Built-in LED (typically has 4 pins):
   - Button pin 1: Connect to GPIO 17 (pin 11)
   - Button pin 2: Connect to GND (pin 9)
   - LED anode pin: Connect to GPIO 27 (pin 13)
   - LED cathode pin: Connect to GND (pin 6)
   
   Note: Your specific button may have different pin arrangements. Check the
   datasheet for your button to confirm which pins are which. Typically:
   - Two pins are for the button mechanism (normally open switch)
   - Two pins are for the LED (anode and cathode)

2. Temperature Sensor (DS18B20):
   - Connect VCC to 3.3V (pin 1)
   - Connect GND to GND (pin 6)
   - Connect DATA to GPIO 4 (pin 7)
   - Connect a 4.7k pull-up resistor between DATA and VCC

Installation:
1. Mount the Raspberry Pi inside the case
2. Install the button in the case hole, ensuring the LED is visible
3. Connect all components according to the wiring diagram
4. Power on the Raspberry Pi with a micro USB power supply

Notes:
- The button should be easily accessible to users for resetting
- Since the button has a built-in LED, positioning is important for visibility
- Many illuminated buttons have terminals labeled: typically "NO" (Normally Open) 
  and "C" (Common) for the switch, and "+" and "-" for the LED
- No external resistor is needed for the LED as it has a built-in resistor
- Consider adding a label near the button indicating "Hold 10 seconds to reset"
