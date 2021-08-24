import serial
import time
import os


class Connection:
    def __init__(self):
        with open('serial_port.txt') as f:
            port = f.read()
        print('Opening Serial on port', port)
        ser = serial.Serial(port, timeout=0.5, baudrate=115200)  # open serial port
        i = 0
        while True:
            line = ser.readline().decode().replace('\n', '')
            i += 1
            if line:
                print(line)
                if '100 Ready' in line:
                    self.ser = ser
                    self.connected = True
                    break
            if i == 10:
                self.connected = False
                break

    def command(self, cmd):
        k = 0
        self.ser.write((cmd + '\n').encode())
        while k < 5:
            line = self.ser.readline().decode().replace('\n', '')
            if line and ('==>' not in line) and ('<==' not in line):
                if '200 Ok' in line:
                    return True
                else:
                    print(line)
                    return False
            if not line:
                k += 1
        return False


stopped = False
print('''
                   _       _             _____            
     /\           | |     (_)           |  __ \           
    /  \   _ __ __| |_   _ _ _ __   ___ | |__) |___   ___ 
   / /\ \ | '__/ _` | | | | | '_ \ / _ \|  _  // _ \ / __|
  / ____ \| | | (_| | |_| | | | | | (_) | | \ \ (_) | (__ 
 /_/    \_\_|  \__,_|\__,_|_|_| |_|\___/|_|  \_\___/ \___|                                                
 Build by Tom M, by using this software you accept I cannot take responsibility for any damage!
''')
print('Connecting to Arduino...')
try:
    box = Connection()
except serial.serialutil.SerialException:
    print('Arduino not found!')
else:
    if box.connected:
        print('Connected!')
    else:
        print('Connection failed, try again!')
    try:
        if box.command('setPower(1)'):
            print('Power on!')
        else:
            raise Exception
    except Exception as e:
        print(e)
    locs = [i for i in os.listdir(os.getcwd()) if 'loc_' in i]
    if len(locs) == 0:
        print('No loco files found!')
    loc_data = {i: [] for i in locs}
    while True:
        try:
            with open('stat.dat') as f:
                cmd = f.read()
                if cmd == 'STOP' and not stopped:
                    print('Stopping!')
                    stopped = True
                    if box.command('setPower(0)'):
                        print('Power off!')
                    else:
                        print('Error while turning off power!')
                if cmd == 'GO' and stopped:
                    print('Continuing')
                    stopped = False
                    if box.command('setPower(1)'):
                        print('Power on!')
                    else:
                        print('Error while turning on power!')
            for loc in locs:
                with open(loc) as f:
                    data = f.read().split('\n')
                    if data:
                        if loc_data[loc] != data and len(data) > 3:
                            loc_data[loc] = data
                            speed, direction = data[0], data[1]
                            func_data = data[2].split(',')
                            functions = {i: func_data[i] for i in range(len(func_data))}
                            address = loc.split('.txt')[0].split('loc_')[1]
                            print('Setting loco address:', address, 'speed', speed, 'direction', direction, 'functions',
                                  functions)
                            box.command('setLocoDirection(%s,%s)' % (address, direction))
                            time.sleep(0.05)
                            box.command('setLocoSpeed(%s,%s)' % (address, speed))
                            time.sleep(0.05)
                            for func in functions:
                                box.command('setLocoFunction(%s,%s,%s)' % (address, func, functions[func]))
                                time.sleep(0.05)
        except serial.serialutil.SerialException:
            print('Lost connection, restarting...')
            break
        except FileNotFoundError:
            print('Status, switch or sensor files not found!')
            break
        except Exception as e:
            print('Some other error occurred:', e)
            break
input("Press ENTER to exit!")
