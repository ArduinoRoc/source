from multiprocessing import Process, Pipe, Queue, Value, freeze_support
from queue import Empty
import socket
import ctypes
import time
import serial
import select
import os

from tkinter import *
from functools import partial


def set_loc_function(loc, function):
    # F1 * 1 + F2 * 2 + F3 * 4 + F4 * 8 + F0 * 16
    funcs = [k for k, i in enumerate('{0:08b}'.format(function)) if i == '1']
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
    return on


def handle_command(data, track_conn, turnout_q):
    if data[0] == '1':
        print('> [CMD] Turning power on.')
        track_conn.send({'cmd': 'p_on'})
    elif data[0] == '0':
        print('> [CMD] Turning power off.')
        track_conn.send({'cmd': 'p_off'})
    elif data[0] == 't':
        loc = data[2]
        speed = data[3]
        direction = 1 if data[4] == '1' else 2
        print(f'> [CMD] Loc {loc} speed set to {speed} and direction {direction}.')
        track_conn.send({'cmd': 'loc_change', 'data': {'address': loc, 'speed': speed, 'direction': direction}})
    elif data[0] == 'Z' and len(data) == 3:
        switch = data[1]
        pos = data[2]
        print(f'> [CMD] Switch {switch} set to {pos}.')
        track_conn.send({'cmd': 'switch_set', 'data': {'address': switch, 'pos': pos}})
    elif data[0] == 'c':
        pass
    elif data[0] == 'f':
        loc = data[1]
        func = int(data[2]) - 128
        funcs_on = set_loc_function(loc, func)
        track_conn.send({'cmd': 'loc_func', 'data': {'address': loc, 'on': funcs_on}})


def handle_rocrail_connection(track_conn, sensor_q, turnout_q):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Ensure that you can restart your server quickly when it terminates
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', 2560))
    # Set the number of clients waiting for connection that can be queued
    sock.listen(5)
    print('> [ROC] Waiting for Rocrail to connect.')
    newSocket, address = sock.accept()
    newSocket.setblocking(False)
    print(f'> [ROC] Connected from {address}.')
    # loop serving the new client
    while True:
        ready_to_read, ready_to_write, _ = select.select([newSocket], [newSocket], [], 0.1)
        if len(ready_to_read) == 0 and len(ready_to_write) > 0:
            if sensor_q is not None:
                try:
                    sensor_update = sensor_q.get_nowait()
                except Empty:
                    pass
                else:
                    print(f'> [ROC] Update from sensor: {sensor_update.id}')
                    if sensor_update.state == 0:
                        ready_to_write[0].send(f"<q {sensor_update.id}>".encode())
                    elif sensor_update.state == 1:
                        ready_to_write[0].send(f"<Q {sensor_update.id}>".encode())
        elif len(ready_to_read) > 0:
            receivedData = ready_to_read[0].recv(1024)
            data = receivedData.decode()
            print(f'> [ROC]: {data}')
            if '>' in data:
                cmds = [i.split('>')[0].split(' ') for i in data.split('<') if len(i) > 0]
                for cmd in cmds:
                    handle_command(cmd, track_conn, turnout_q)


class Loco:
    def __init__(self, address):
        self.address = address
        self.speed = 0
        self.direction = 1
        self.functions = {i: 0 for i in range(32)}


class Layout:
    def __init__(self, comport):
        try:
            ser = serial.Serial(comport, timeout=0.5, baudrate=115200)  # open serial port
        except Exception:
            print(
                f'> [Arduino] Could not connect to Gleisbox Arduino on {comport}. The port can be changed in the config.txt file.')
            self.connected = False
            return
        self.loco_list = {}
        i = 0
        while True:
            line = ser.readline().decode().replace('\n', '')
            i += 1
            if line:
                print(f'> [Arduino] {line}')
                if '100 Ready' in line:
                    self.ser = ser
                    self.connected = True
                    break
            if i == 10:
                self.connected = False
                break

    def listen(self, log):
        seen = []
        while True:
            line = self.ser.readline().decode().replace('\n', '')
            if len(line) > 0:
                print(f'> [Arduino] {line}')
                if '@MFXBIND' in line:
                    log.put(f'--> MFX loco at adress {line.split(",")[-2]}')
                elif '@SPD' in line:
                    msg = f'--> loco at adress {line.split(",")[2]}'
                    if msg not in seen:
                        seen.append(msg)
                        log.put(msg)

    def send_command(self, cmd):
        while True:
            k = 0
            self.ser.write((cmd + '\n').encode())
            while k < 5:
                line = self.ser.readline().decode().replace('\n', '')
                print(f'> [Arduino] {line}')
                if line and ('==>' not in line) and ('<==' not in line):
                    if '200 Ok' in line:
                        return True
                if len(line) > 0:
                    k += 1
            print('> [Arduino] Serial command timed out!')


class Sensor:
    def __init__(self, id):
        self.id = id
        self.state = -1

    def check(self, new_state):
        if self.state != new_state:
            self.state = new_state
            return True


def handle_sensors(sensor_q, comport):
    with open('n_sensors.txt') as f:
        n_sensors = int(f.read())
    print(f'> [Sys] Using {n_sensors} number of sensors for detection.')
    while True:
        try:
            ser = serial.Serial(comport, timeout=0.5, baudrate=115200)  # open serial port
        except Exception:
            print(f'> [Arduino] Could not connect to sensor Arduino on {comport}.')
            time.sleep(2)
        else:
            break
    sensors = [Sensor(i + 1) for i in range(n_sensors)]
    while True:
        try:
            line = ser.readline().decode().replace('\n', '').replace('\r', '').strip()
        except serial.serialutil.SerialException:
            break
        detected_sensors = line.split(',')
        if len(detected_sensors) == (n_sensors):
            for i in range(len(detected_sensors)):
                if sensors[i].check(int(detected_sensors[i])):
                    sensor_q.put(sensors[i])


def handle_layout(conn, comport):
    while True:
        tracks = Layout(comport)
        if tracks.connected:
            print('> [Arduino] Connected to track box.')
            break
        else:
            print('> [Arduino] Could not connect to track box!')
            time.sleep(2)
    while True:
        data = conn.recv()
        if 'cmd' in data:
            result = False
            if data['cmd'] == 'p_on':
                result = tracks.send_command('setPower(1)')
            elif data['cmd'] == 'p_off':
                result = tracks.send_command('setPower(0)')
            elif data['cmd'] == 'loc_change':
                address, speed, direction = data['data'].values()
                with open('binds.txt') as f:
                    binds = {i.split(':')[1].split('=>')[1]: [i.split(':')[0], i.split(':')[1].split('=>')[0]] for i in
                             f.read().split('\n') if i != ''}
                if address in binds:
                    temp = address
                    prot, add = binds[address]
                    if prot == 'MFX':
                        address = int(f'0x4{(3 - len(add)) * "0"}{add}', base=16)
                        print(f'> [CMD] Translated MFX address {temp} to 0x4{(3 - len(add)) * "0"}{add}')
                    elif prot == 'DCC':
                        address = int(f'0xC{(3 - len(add)) * "0"}{add}', base=16)
                        print(f'> [CMD] Translated DCC address {temp} to 0xC{(3 - len(add)) * "0"}{add}')
                if address not in tracks.loco_list:
                    tracks.loco_list[address] = Loco(address)
                if tracks.loco_list[address].direction != direction:
                    tracks.loco_list[address].direction = direction
                    result = tracks.send_command(f'setLocoDirection({address},{direction})')
                if tracks.loco_list[address].speed != speed:
                    tracks.loco_list[address].speed = speed
                    result = tracks.send_command(f'setLocoSpeed({address},{8 * int(speed)})')
            elif data['cmd'] == 'switch_set':
                address, pos = data['data'].values()
                tracks.send_command('setTurnout(%s,%s)' % (12287 + int(address), pos))
                print(f'> [CMD] Set turnout {12287 + int(address)} to {pos}.')
            elif data['cmd'] == 'loc_func':
                address, funcs_on = data['data'].values()
                with open('binds.txt') as f:
                    binds = {i.split(':')[1].split('=>')[1]: [i.split(':')[0], i.split(':')[1].split('=>')[0]] for i in
                             f.read().split('\n') if i != ''}
                if address in binds:
                    temp = address
                    prot, add = binds[address]
                    if prot == 'MFX':
                        address = int(f'0x4{(3 - len(add)) * "0"}{add}', base=16)
                        print(f'> [CMD] Translated MFX address {temp} to 0x4{(3 - len(add)) * "0"}{add}')
                    elif prot == 'DCC':
                        address = int(f'0xC{(3 - len(add)) * "0"}{add}', base=16)
                        print(f'> [CMD] Translated DCC address {temp} to 0xC{(3 - len(add)) * "0"}{add}')
                if address not in tracks.loco_list:
                    tracks.loco_list[address] = Loco(address)
                for func in funcs_on:
                    if tracks.loco_list[address].functions[func] != 1:
                        tracks.loco_list[address].functions[func] = 1
                        result = tracks.send_command('setLocoFunction(%s,%s,%s)' % (address, func, 1))
                for func in tracks.loco_list[address].functions:
                    if func not in funcs_on:
                        tracks.loco_list[address].functions[func] = 0
                        result = tracks.send_command('setLocoFunction(%s,%s,%s)' % (address, func, 0))
            if not result:
                print('> [Arduino] No command executed.')


class Turnout:
    def __init__(self, id):
        self.id = id
        with open(f'/config_files/s{id}.config') as f:
            self.stats = {i.split('=')[0]: i.split('=')[1] for i in f.read().split('\n')}
        self.state = int(self.stats['state'])

    def update_stats(self, key, value):
        self.stats[key] = value
        lines = '\n'.join([f'{key}={self.stats[key]}' for key in self.stats])
        with open(f'/config_files/s{self.id}.config', 'w') as f:
            f.write(lines)

    def throw(self, new_pos):
        with open(f'/config_files/s{self.id}.config') as f:
            self.stats = {i.split('=')[0]: i.split('=')[1] for i in f.read().split('\n')}
        if new_pos == 0:
            if self.state == 90:
                from_ = 90
            elif self.state == 1:
                from_ = int(self.stats['max'])
            else:
                from_ = int(self.stats['min'])
            go_to = int(self.stats['min'])
        elif new_pos == 1:
            if self.state == 90:
                from_ = 90
            elif self.state == 0:
                from_ = int(self.stats['min'])
            else:
                from_ = int(self.stats['max'])
            go_to = int(self.stats['max'])
        elif new_pos == 90:
            from_ = int(self.stats['min']) if self.state == 0 else int(self.stats['max'])
            go_to = 90
        else:
            raise ValueError('Incorrect switch position given!')
        self.state = new_pos
        self.update_stats('state', str(new_pos))
        return from_, go_to


def handle_turnouts(turnout_q, comport):
    try:
        ser = serial.Serial(comport, timeout=0.5, baudrate=115200)  # open serial port
    except Exception:
        print(f'> [Arduino] Could not connect to turnout Arduino on {comport}.')
        return
    step = 10
    files = [i.split('s')[1].split('.')[0] for i in os.listdir('/config_files') if
             's' in i]
    turnouts = {}
    for id in files:
        turnouts[int(id)] = Turnout(int(id))
    while True:
        try:
            turnout_data = turnout_q.get_nowait()
            print(f'> [Turnouts] {turnout_data}')
        except Empty:
            pass
        else:
            if turnout_data['type'] == 'set' or turnout_data['type'] == 'force_set':
                turnout_update = turnout_data['data']
                for turnout_to_update in turnout_update:
                    turnout = turnouts[int(turnout_to_update)]
                    if turnout.stats['type'] == 'servo':
                        if turnout.state != int(turnout_update[turnout_to_update]) or turnout_data[
                            'type'] == 'force_set':
                            from_, go_to = turnout.throw(int(turnout_update[turnout_to_update]))
                            # for i in range(from_, go_to + step if from_ <= go_to else go_to - step,
                            #                step if from_ <= go_to else -step):
                            msg = f'{turnout.stats["address"]},{go_to},{turnout.stats["type"]}\n'
                            print(f'> [Turnouts] {msg}')
                            ser.write(msg.encode())
                            time.sleep(0.1)
                    else:
                        if turnout.state != int(turnout_update[turnout_to_update]):
                            _, go_to = turnout.throw(int(turnout_update[turnout_to_update]))
                            msg = f'{go_to},{turnout.stats["address"]},{turnout.stats["type"]}\n'
                            print(f'> [Turnouts] {msg}')
                            ser.write(msg.encode())
                            time.sleep(0.1)

            elif turnout_data['type'] == 'update':
                files = [i.split('s')[1].split('.')[0] for i in
                         os.listdir('/config_files') if 's' in i]
                turnouts = {}
                for id in files:
                    turnouts[int(id)] = Turnout(int(id))
            elif turnout_data['type'] == 'change':
                turnout_update = turnout_data['data']
                for turnout_to_update in turnout_update:
                    turnout = turnouts[int(turnout_to_update)]
                    key = turnout_update[turnout_to_update]['key']
                    val = turnout_update[turnout_to_update]['val']
                    turnout.update_stats(key, val)


def listen(comport, log):
    while True:
        print('> [Arduino] Starting up detection process.')
        tracks = Layout(comport)
        if tracks.connected:
            print('> [Arduino] Started listening to track box.')
            break
        else:
            print('> [Arduino] Listener could not connect to track box!')
            time.sleep(2)
    tracks.listen(log)


class UI:
    def __init__(self):
        parent_conn_track, self.child_conn_track = Pipe()
        with open('config.txt') as f:
            lines = f.read().split('\n')
            self.modules = {i: k for i, k in zip(lines[0].split(','), lines[1].split(','))}
        sensor_q = Queue() if 'sensors' in self.modules else None
        turnout_q = Queue() if 'turnouts' in self.modules else None

        self.listener_running = False

        self.ps = [Process(target=handle_rocrail_connection, args=(parent_conn_track, sensor_q, turnout_q)),
                   Process(target=handle_layout, args=(self.child_conn_track, self.modules['rocrail']))]
        if turnout_q is not None:
            print('> [Sys] Starting with turnout module.')
            self.ps += [Process(target=handle_turnouts, args=(turnout_q, self.modules['turnouts']))]
        if sensor_q is not None:
            print('> [Sys] Starting with sensor module.')
            self.ps += [Process(target=handle_sensors, args=(sensor_q, self.modules['sensors']))]
        for p in self.ps:
            p.start()

        self.do_turnouts = turnout_q is not None
        self.turnout_q = turnout_q

        self.window = Tk()
        self.window.geometry('800x800')
        self.log_out = StringVar()
        self.bind_out = StringVar()
        self.frame = Frame(self.window)
        self.render_main_menu()

    def render_servo_menu(self, servo=None, servo_address=0, servo_min=90, servo_max=90):
        self.frame.destroy()
        self.frame = Frame(self.window)
        self.frame.pack()

        lbl = Label(self.frame, text="Servo configurator", font=("Arial Bold", 12))
        lbl.grid(column=0, row=0)
        btn = Button(self.frame, text="Back", command=partial(self.btn_clicked, 'goto_main'))
        btn.grid(column=0, row=1)
        lbl = Label(self.frame, text="Servo:", font=("Arial Bold", 12))
        lbl.grid(column=0, row=2)
        if servo is None:
            self.servo_id_entry = Entry(self.frame)
        else:
            self.servo_id_entry = Entry(self.frame, textvariable=StringVar(self.frame, str(servo)))
        self.servo_id_entry.grid(column=1, row=2)
        btn = Button(self.frame, text="Get or create servo", command=partial(self.btn_clicked, 'get_servo'))
        btn.grid(column=0, row=3)
        if servo is not None:
            btn = Button(self.frame, text="Center servo", command=partial(self.btn_clicked, 'center_servo'))
            btn.grid(column=0, row=4)
            lbl = Label(self.frame, text="Servo address", font=("Arial Bold", 12))
            lbl.grid(column=0, row=5)
            self.servo_address_entry = Entry(self.frame, textvariable=StringVar(self.frame, str(servo_address)))
            self.servo_address_entry.grid(column=1, row=5)
            lbl = Label(self.frame, text="Servo MIN", font=("Arial Bold", 12))
            lbl.grid(column=0, row=6)
            self.servo_min_entry = Entry(self.frame, textvariable=StringVar(self.frame, str(servo_min)))
            self.servo_min_entry.grid(column=1, row=6)
            lbl = Label(self.frame, text="Servo MAX", font=("Arial Bold", 12))
            lbl.grid(column=0, row=7)
            self.servo_max_entry = Entry(self.frame, textvariable=StringVar(self.frame, str(servo_max)))
            self.servo_max_entry.grid(column=1, row=7)
            btn = Button(self.frame, text="Set to MIN", command=partial(self.btn_clicked, 'min_servo'))
            btn.grid(column=0, row=8)
            btn = Button(self.frame, text="Set to MAX", command=partial(self.btn_clicked, 'max_servo'))
            btn.grid(column=1, row=8)
            btn = Button(self.frame, text="SAVE", command=partial(self.btn_clicked, 'save_servo'))
            btn.grid(column=0, row=9)

    def render_listen(self):
        self.frame.destroy()
        self.frame = Frame(self.window)
        self.frame.pack()
        self.log_out.set('>')
        self.bind_out.set('')
        with open('binds.txt') as f:
            locos = ', '.join(f.read().split('\n'))
        lbl = Label(self.frame, text='Bound locomotives:\n' + locos, font=("Arial Bold", 12))
        lbl.grid(column=1, row=0)

        btn = Button(self.frame, text="Back", command=partial(self.btn_clicked, 'goto_main'))
        btn.grid(column=1, row=1)

        btn = Button(self.frame, text="Refresh", command=partial(self.btn_clicked, 'goto_listen'))
        btn.grid(column=2, row=1)

        lbl = Label(self.frame, text="Detect MFX/dcc loco:", font=("Arial Bold", 12))
        lbl.grid(column=1, row=2)
        btn = Button(self.frame, text="Start listening", command=partial(self.btn_clicked, 'start_log'))
        btn.grid(column=1, row=3)
        btn = Button(self.frame, text="End listening", command=partial(self.btn_clicked, 'get_log'))
        btn.grid(column=1, row=4)
        lbl = Label(self.frame, textvariable=self.log_out, font=("Arial Bold", 12))
        lbl.grid(column=1, row=5)
        lbl = Label(self.frame, text="Register MFX/dcc loco:", font=("Arial Bold", 12))
        lbl.grid(column=1, row=6)

        self.loco_address_entry_mfx = Entry(self.frame, textvariable=StringVar(self.frame, ""))
        self.loco_address_entry_mfx.grid(column=2, row=7)
        lbl = Label(self.frame, text="Address MFX\t", font=("Arial Bold", 12))
        lbl.grid(column=1, row=7)

        self.loco_address_entry_dcc = Entry(self.frame, textvariable=StringVar(self.frame, ""))
        self.loco_address_entry_dcc.grid(column=2, row=8)
        lbl = Label(self.frame, text="Address DCC\t", font=("Arial Bold", 12))
        lbl.grid(column=1, row=8)

        self.loco_address_entry = Entry(self.frame, textvariable=StringVar(self.frame, ""))
        self.loco_address_entry.grid(column=2, row=9)
        lbl = Label(self.frame, text="Address Rocrail\t", font=("Arial Bold", 12))
        lbl.grid(column=1, row=9)

        btn = Button(self.frame, text="Register address", command=partial(self.btn_clicked, 'register_loco'))
        btn.grid(column=1, row=10)
        btn = Button(self.frame, text="Remove bind", command=partial(self.btn_clicked, 'un_register_loco'))
        btn.grid(column=2, row=10)

        lbl = Label(self.frame, textvariable=self.bind_out, font=("Arial Bold", 12))
        lbl.grid(row=11, column=1)

    def render_main_menu(self):
        self.frame.destroy()
        self.frame = Frame(self.window)
        self.frame.pack()

        lbl = Label(self.frame, text="Main Menu", font=("Arial Bold", 12))
        lbl.grid(column=0, row=0)
        if (self.do_turnouts):
            btn = Button(self.frame, text="Servo Config", command=partial(self.btn_clicked, 'goto_servo_config'))
            btn.grid(column=0, row=1)
        btn = Button(self.frame, text="DCC / MFX loco", command=partial(self.btn_clicked, 'goto_listen'))
        btn.grid(column=0, row=2)

    def btn_clicked(self, id):
        if id == 'goto_servo_config':
            self.render_servo_menu()
        elif id == 'un_register_loco':
            mfx = self.loco_address_entry_mfx.get()
            dcc = self.loco_address_entry_dcc.get()
            roc = self.loco_address_entry.get()
            if mfx and dcc:
                self.bind_out.set('Enter either DCC or MFX address!')
            elif not roc:
                self.bind_out.set('Enter Rocrail address!')
            elif not mfx and not dcc:
                self.bind_out.set('Enter either DCC or MFX address!')
            else:
                with open('binds.txt') as f:
                    binds = f.read().split('\n')
                if f'{"MFX" if mfx else "DCC"}:{mfx if mfx else dcc}=>{roc}' in binds:
                    binds.remove(f'{"MFX" if mfx else "DCC"}:{mfx if mfx else dcc}=>{roc}')
                    with open('binds.txt', 'w') as f:
                        f.write('\n'.join(binds))
                    self.bind_out.set('Unbound loco!')
                else:
                    self.bind_out.set(f'Loco {"MFX" if mfx else "DCC"}:{mfx if mfx else dcc}=>{roc} not yet bound!')

        elif id == 'register_loco':
            mfx = self.loco_address_entry_mfx.get()
            dcc = self.loco_address_entry_dcc.get()
            roc = self.loco_address_entry.get()
            if mfx and dcc:
                self.bind_out.set('Enter either DCC or MFX address!')
            elif not roc:
                self.bind_out.set('Enter Rocrail address!')
            elif not mfx and not dcc:
                self.bind_out.set('Enter either DCC or MFX address!')
            else:
                with open('binds.txt') as f:
                    binds = [i.split(':')[1].split('=>') for i in f.read().split('\n') if i != '']
                error = False
                for bind in binds:
                    if mfx or dcc in bind[0]:
                        self.bind_out.set('Loco already bound!')
                        error = True
                    elif roc in bind[1]:
                        self.bind_out.set('Loco already in rocrail!')
                        error = True
                if not error:
                    with open('binds.txt', 'a') as f:
                        f.write(f'{"MFX" if mfx else "DCC"}:{mfx if mfx else dcc}=>{roc}\n')
                        self.bind_out.set(
                            f'Bound {"MFX" if mfx else "DCC"} loco with address {mfx if mfx else dcc}.'
                            f'\nAdd loco in Rocrail with address {roc} to control this loco.')
        elif id == 'goto_listen':
            self.render_listen()
        elif id == 'goto_main':
            self.render_main_menu()
        elif id == 'start_log':
            if not self.listener_running:
                self.listener_running = True
                self.ps[1].terminate()
                self.ps[1].join()
                self.log = Queue()
                self.ps += [Process(target=listen, args=(self.modules['rocrail'], self.log))]
                self.ps[-1].start()
                self.log_out.set(">Started listening, do NOT restart!")
            else:
                self.log_out.set('Listener already running!')
        elif id == 'get_log':
            if self.listener_running:
                self.ps[-1].terminate()
                self.ps[-1].join()
                logged = ''
                while not self.log.empty():
                    logged += self.log.get_nowait() + '\n'
                self.ps[1] = Process(target=handle_layout, args=(self.child_conn_track, self.modules['rocrail']))
                self.ps[1].start()
                self.log_out.set(logged)
                self.listener_running = False
            else:
                self.log_out.set('Listener not running!')
        elif id == 'get_servo':
            try:
                servo = self.servo_id_entry.get()
            except ValueError:
                pass
            else:
                files = [i.split('s')[1].split('.')[0] for i in os.listdir('config_files') if 's' in i]
                if servo in files:
                    with open(f'config_files/s{servo}.config') as f:
                        stats = {i.split('=')[0]: i.split('=')[1] for i in f.read().split('\n')}
                        self.render_servo_menu(servo=int(servo), servo_address=stats['address'], servo_min=stats['min'],
                                               servo_max=stats['max'])
                else:
                    self.render_servo_menu(servo=int(servo))
        elif id == 'save_servo':
            servo = self.servo_id_entry.get()
            files = [i.split('s')[1].split('.')[0] for i in os.listdir('config_files') if 's' in i]
            if servo in files:
                with open(f'config_files/s{servo}.config') as f:
                    stats = {i.split('=')[0]: i.split('=')[1] for i in f.read().split('\n')}
            else:
                stats = {'state': 90}
            stats['min'] = self.servo_min_entry.get()
            stats['max'] = self.servo_max_entry.get()
            stats['address'] = self.servo_address_entry.get()
            stats['type'] = 'servo'

            lines = '\n'.join([f'{key}={stats[key]}' for key in stats])
            with open(f'config_files/s{servo}.config', 'w') as f:
                f.write(lines)
            self.turnout_q.put({'type': 'update'})
            self.turnout_q.put({'type': 'set', 'data': {servo: stats['state']}})
        elif id == 'center_servo':
            try:
                servo = self.servo_id_entry.get()
            except ValueError:
                pass
            else:
                self.turnout_q.put({'type': 'set', 'data': {servo: '90'}})
        elif id == 'min_servo':
            self.servo_min_entry.get()
            id = self.servo_id_entry.get()
            min_ = self.servo_min_entry.get()
            self.turnout_q.put({'type': 'change', 'data': {id: {'key': 'min', 'val': min_}}})
            self.turnout_q.put({'type': 'force_set', 'data': {id: '0'}})
        elif id == 'max_servo':
            self.servo_min_entry.get()
            id = self.servo_id_entry.get()
            max_ = self.servo_max_entry.get()
            self.turnout_q.put({'type': 'change', 'data': {id: {'key': 'max', 'val': max_}}})
            self.turnout_q.put({'type': 'force_set', 'data': {id: '1'}})


if __name__ == '__main__':
    freeze_support()
    ui = UI()
    ui.window.mainloop()
    for p in ui.ps:
        p.terminate()
        p.join()
