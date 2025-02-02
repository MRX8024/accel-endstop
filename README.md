## Welcome to the accelerometer-based axes homing project

### Supported accelerometers:
`adxl345`

### How does it work?
The adxl345 accelerometers have int1 and int2 outputs, which produce signal
pulses at a certain acceleration, which is configured in advance. We solder
the wire from the int pin of the accelerometer to the mcu of the printer
board, and read its signals as a regular endstop. Some CAN printhead boards
with built-in adxl345 have a pin already connected to the self mcu.

### Installing the calibration script on the printer host
```
cd ~
git clone https://github.com/MRX8024/accel-endstop
bash ~/accel-endstop/install.sh
```

### Configuration
Add the following section to the printer's configuration:
```
[accel_endstop]
accel_chip: adxl345
#    Accelerometer for vibrations collection.
int_type: int1/int2
#    Your chosen adxl345 output pin type.
int_pin: ^<pin>
#    Endstop pin on the control board.
tap_thresh: 15000
#    Sensor trigger state threshold.
tap_dur: 0.01
#    Sensor trigger state time.
#activate_gcode:
#deactivate_gcode:
```

In the axis endstop configuration:
```
endstop_pin: <accel_chip>:virtual_endstop
```

### Threshold tuning
Move the head to the maximum position. Start parking and try to stop the
head with hand strikes, change `TAP_THRESH` until you achieve an acceptable
result. Same as when setting up sensorless homing. Typical values: 10-15k.
```
SET_ACCEL_ENDSTOP TAP_THRESH=[<value>] TAP_DUR=[<value>]
```
If the print head does not budge at any value, you have a configuration,
wiring, or accelerometer problem. Perhaps your head start acceleration on
homing faster than you configured `tap_thresh`. In the `activate_gcode`
parameter you can add gcode commands that will reduce the acceleration
while homing is running, and then restore them in `deactivate_gcode`.

### Contacts
Use the issue GitHub system.
You can also write to me personally in discord - @mrx8024.

### Credits:
Thanks [Jochen Niebuhr](https://github.com/jniebuhr) for the [adxl probe](
https://github.com/jniebuhr/adxl345-probe) idea.
