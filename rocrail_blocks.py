import serial
import time
import ast

while True:
    ser = serial.Serial('COM5', timeout=0.5, baudrate=115200)  # open serial port

    sensors = {i: 0 for i in range(1, 16)}
    switches = {i: None for i in range(1, 4)}
    print(switches)
    k = 0
    while True:
        try:
            line = ser.readline().decode().replace('\n', '').replace('\r', '').strip()
        except serial.serialutil.SerialException:
            break
        detected_sensors = line.split(',')
        if len(detected_sensors) == 16:
            for i in range(len(detected_sensors)):
                sensors[i + 1] = int(detected_sensors[i])
                if int(detected_sensors[i]) == 1:
                    print(i + 1)
            with open('sensors.dat', 'w') as f:
                f.write(str(sensors))
        try:
            with open('switches.dat') as f:
                switches_n = ast.literal_eval(f.read())
        except Exception:
            pass
        else:
            if switches_n != switches:
                for switch in switches:
                    if switches_n[switch] != switches[switch]:
                        print('Update from switch: ', switch, switches_n[switch])
                        if switches[switch] == 0:
                            ser.write(("s" + str(switch) + " 0\n").encode())
                        elif switches[switch] == 1:
                            ser.write(("s" + str(switch) + " 1\n").encode())
                switches = switches_n
