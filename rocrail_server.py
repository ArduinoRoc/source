import socket
import time
import ast

# Create a socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Ensure that you can restart your server quickly when it terminates
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Set the client socket's TCP "well-known port" number

sock.bind(('127.0.0.1', 2560))
print('''
                   _       _             _____            
     /\           | |     (_)           |  __ \           
    /  \   _ __ __| |_   _ _ _ __   ___ | |__) |___   ___ 
   / /\ \ | '__/ _` | | | | | '_ \ / _ \|  _  // _ \ / __|
  / ____ \| | | (_| | |_| | | | | | (_) | | \ \ (_) | (__ 
 /_/    \_\_|  \__,_|\__,_|_|_| |_|\___/|_|  \_\___/ \___|                                                
 Build by Tom M, by using this software you accept I cannot take responsibility for any damage!
''')
print('Waiting for Rocrail to connect...')
# Set the number of clients waiting for connection that can be queued
sock.listen(5)


def set_loc_speed(loc, speed, direction):
    try:
        with open('loc_' + loc + '.txt') as f:
            ldat = f.read().split('\n')
            lmin, lmax = ldat[3].split(',')[0], ldat[3].split(',')[1]
            print(lmin,lmax, speed)
            ldat[0] = str(int(int(lmax) * (int(speed) / 100)))
            ldat[1] = str(direction)
            print("Speed set:", loc, ldat[0], ldat[1])
        with open('loc_' + loc + '.txt', 'w') as f:
            f.write("\n".join(ldat))
    except FileNotFoundError:
        pass


def set_loc_function(loc, function):
    # F1 * 1 + F2 * 2 + F3 * 4 + F4 * 8 + F0 * 16
    funcs = [k for k,i in enumerate('{0:08b}'.format(function)) if i == '1']
    on = []
    if 3 in funcs:
        on.append(0)
    if 4 in funcs:
        on.append(4)
    if 5 in funcs:
        on.append(3)
    if 6 in funcs:
        on.append(2)
    if 7 in funcs:
        on.append(1)
    try:
        with open('loc_' + loc + '.txt') as f:
            ldat = f.read().split('\n')
            # current = [k for k,i in enumerate(ldat[2].split(',')) if i == '1']
            ldat[2] = ','.join(['1' if i in on else '0' for i in range(5)])
            print("Function set to on:", loc, on)
        with open('loc_' + loc + '.txt', 'w') as f:
            f.write("\n".join(ldat))
    except FileNotFoundError:
        pass


class Sensors:
    def __init__(self):
        with open('sensors.dat') as f:
            self.sensors = ast.literal_eval(f.read())
        for i in self.sensors:
            self.sensors[i] = None

    def update(self):
        while True:
            to_update = []
            try:
                with open('sensors.dat') as f:
                    sensors = ast.literal_eval(f.read())
            except Exception:
                pass
            else:
                if sensors != self.sensors:
                    for sensor in self.sensors:
                        if sensors[sensor] != self.sensors[sensor]:
                            print('Update from sensor: ', sensor, sensors[sensor])
                            if sensors[sensor] == 0:
                                to_update.append("<q " + str(sensor) + ">")
                            elif sensors[sensor] == 1:
                                to_update.append("<Q " + str(sensor) + ">")
                    self.sensors = sensors
                return to_update


sensors = Sensors()
# loop waiting for connections (terminate with Ctrl-C)
try:
    while True:
        newSocket, address = sock.accept()
        newSocket.settimeout(0.5)
        print("Connected from", address)
        # loop serving the new client
        while True:
            try:
                receivedData = newSocket.recv(1024)
                data = receivedData.decode()
                print('Rocrail send command:',data)
                cmds = data.split('<')
                for command in cmds:
                    data = command.split('>')[0].split(' ')
                    if data[0] == '1':
                        print('Turning power on.')
                        with open('stat.dat', 'w') as f:
                            f.write('GO')
                    elif data[0] == '0':
                        print('Turning power off.')
                        with open('stat.dat', 'w') as f:
                            f.write('STOP')
                    elif data[0] == 't':
                        loc = data[2]
                        speed = data[3]
                        direction = 1 if data[4] == '1' else 2
                        set_loc_speed(loc, speed, direction)
                    elif data[0] == 'Z' and len(data) == 3:
                        switch = data[1]
                        pos = data[2]
                        print('Switch set:', switch, pos)
                        while True:
                            try:
                                with open('switches.dat') as f:
                                    switches = ast.literal_eval(f.read())
                                    switches[int(switch)] = int(pos)
                                with open('switches.dat', 'w') as f:
                                    f.write(str(switches))
                            except Exception:
                                pass
                            else:
                                break
                    elif data[0] == 'f':
                        loc = data[1]
                        func = int(data[2]) - 128
                        set_loc_function(loc, func)

            except socket.timeout:
                pass
            to_update = sensors.update()
            if to_update is not None:
                for update in to_update:
                    newSocket.send(update.encode())
        newSocket.close()
        print("Disconnected from", address)
finally:
    sock.close()
input("Press ENTER to exit!")
