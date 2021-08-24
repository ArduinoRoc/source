import os, sys
import pygame
from pygame.locals import *
import matplotlib

matplotlib.use("Agg")
import matplotlib.backends.backend_agg as agg
import pylab
from matplotlib import collections  as mc
import ast

pygame.init()
screen = pygame.display.set_mode((1280, 720))
pygame.display.set_caption('Control')
screen.fill((250, 250, 250))


def draw_layout(ax, fig, screen, lines, color, widths):
    lc = mc.LineCollection(lines, colors=color, linewidths=widths)
    ax.add_collection(lc)
    ax.autoscale()
    ax.margins(0.1)
    canvas = agg.FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    raw_data = renderer.tostring_rgb()
    surf = pygame.image.fromstring(raw_data, canvas.get_width_height(), "RGB")
    screen.blit(surf, (screen.get_width() / 2 - (canvas.get_width_height()[0] / 2), 100))
    matplotlib.pyplot.close(fig)


def draw_loc(screen, loc, speeds, dirs):
    screen.fill((250, 250, 250))
    fig = pylab.figure(figsize=[10, 4],  # Inches
                       dpi=100,  # 100 dots per inch, so the resulting buffer is 400x400 pixels
                       )
    ax = fig.gca()
    layout = [line.split('#') for line in open('layout.txt').read().split('\n')]
    switches = {}
    blocks = {}
    color = [(0, 0, 0) for i in range(len(layout))]
    widths = [1 for i in range(len(layout))]
    while True:
        try:
            status = {line.split(':')[0]: line.split(':')[1] for line in open('status.txt').read().split('\n')}
        except IndexError:
            pass
        else:
            break
    for i in range(len(layout)):
        if 'Switch' in layout[i][1]:
            if 'I' not in layout[i][1]:
                if layout[i][1] not in switches:
                    switches[layout[i][1]] = [int(status[layout[i][1]]), i]
                    x = ast.literal_eval(layout[i][0])[0][1] - 2
                    y = -1 * ast.literal_eval(layout[i][0])[0][0] + 0.3
                    ax.text(x, y, layout[i][1],
                            fontsize=10, bbox={'facecolor': 'white', 'alpha': 0.25, 'pad': 1})
                else:
                    switches[layout[i][1]].append(i)
            else:
                color[i] = (0.5, 0.5, 0.5)
        if 'B' in layout[i][1] and len(layout[i][1]) < 5:
            p1, p2 = ast.literal_eval(layout[i][0])
            x1, y1 = p1
            x2, y2 = p2
            if x1 == x2:
                x = x1
                y = (y1 + y2) / 2
            elif y1 == y2:
                y = y1
                x = (x1 + x2) / 2
            if int(status[layout[i][1]].split(';')[0]) != 0:
                ax.text(y + 0.1, -1 * x + 0.2, status[layout[i][1]].split(';')[0],
                        fontsize=10, bbox={'facecolor': 'gray', 'alpha': 0.25, 'pad': 1})
            blocks[layout[i][1]] = i
            if int(status[layout[i][1]].split(';')[1]) == 0:
                color[i] = (0, 0.5, 0)
            elif int(status[layout[i][1]].split(';')[1]) == 1:
                color[i] = (0.5, 0, 0)
            elif int(status[layout[i][1]].split(';')[1]) == 2:
                color[i] = (0.7, 0.7, 0)
    for switch in switches:
        if switches[switch][0] == 0:
            color[switches[switch][2]] = (0, 0, 0)
            color[switches[switch][1]] = (0.5, 0.5, 0.5)
        elif switches[switch][0] == 1:
            color[switches[switch][1]] = (0, 0, 0)
            color[switches[switch][2]] = (0.5, 0.5, 0.5)
    lines = [ast.literal_eval(layout[i][0]) for i in range(len(layout))]
    draw_layout(ax, fig, screen, [[(line[0][1], -1 * line[0][0]), (line[1][1], -1 * line[1][0])] for line in lines],
                color,
                widths)
    font = pygame.font.Font(None, 36)
    text = font.render("Selected: " + loc, 1, (10, 10, 10))
    textpos = text.get_rect(y=0, centerx=screen.get_width() / 2)
    screen.blit(text, textpos)
    if loc != "not found":
        if dirs[loc] == 1:
            text = font.render("Speed: +" + str(speeds[loc]), 1, (10, 10, 10))
        elif dirs[loc] == 2:
            text = font.render("Speed: -" + str(speeds[loc]), 1, (10, 10, 10))
        textpos = text.get_rect(y=50, centerx=screen.get_width() / 2)
        screen.blit(text, textpos)


def draw_choice(screen):
    screen.fill((250, 250, 250))
    font = pygame.font.Font(None, 36)
    text = font.render("Pick a loc:", 1, (10, 10, 10))
    textpos = text.get_rect(centerx=screen.get_width() / 2)
    screen.blit(text, textpos)


locs = [i for i in os.listdir(os.getcwd()) if 'loc_' in i]
speeds = {}
dirs = {}
speed_limits = {}
for loc in locs:
    with open(loc) as f:
        loc = loc.split('.dat')[0].split('loc_')[1]
        data = f.read().split('\n')
        speeds[loc] = int(data[0])
        dirs[loc] = int(data[1])
        speed_limits[loc] = data[3].split(',')

clock = pygame.time.Clock()
running = True
loc = ""
stopped = False
selecting = False
old_speeds = {loc_: None for loc_ in speed_limits}
old_dirs = {loc_: None for loc_ in speed_limits}

while running:
    with open('stat.dat', 'w') as f:
        f.write('STOP') if stopped else f.write('GO')
    clock.tick(60)
    for event in pygame.event.get():
        if event.type == KEYDOWN and event.key == 8:
            print('Got power command.')
            if not stopped:
                stopped = True
            else:
                stopped = False
        if event.type == QUIT:
            running = False
        elif event.type == KEYDOWN and event.key == K_ESCAPE:
            running = False
        elif event.type == KEYDOWN and event.key == K_KP_MULTIPLY:
            selecting = True
            loc = ""
        elif event.type == KEYDOWN and selecting:
            if event.key - 256 < 10:
                loc += str(event.key - 256)
            if event.key - 256 == 15:
                if loc not in speed_limits:
                    loc = "not found"
                selecting = False
        elif event.type == KEYDOWN and not selecting and loc:
            step = (int(speed_limits[loc][1]) - int(speed_limits[loc][0])) // 5
            speed = speeds[loc]
            dir = dirs[loc]
            if event.key - 256 == 0:
                speed = 0
                speeds[loc] = speed
            elif event.key - 256 == 8:
                if speed + step > int(speed_limits[loc][1]):
                    speed = int(speed_limits[loc][1])
                elif speed + step < int(speed_limits[loc][1]):
                    if speed + step < int(speed_limits[loc][0]):
                        speed = int(speed_limits[loc][0])
                    else:
                        speed += step
                speeds[loc] = speed
                dirs[loc] = dir
            elif event.key - 256 == 2:
                if speed - step < int(speed_limits[loc][0]):
                    speed = 0
                elif speed - step >= int(speed_limits[loc][0]):
                    speed -= step
                speeds[loc] = speed
                dirs[loc] = dir
            elif event.key - 256 == 13:
                dir = 2
                speed = 0
                speeds[loc] = speed
                dirs[loc] = dir
            elif event.key - 256 == 14:
                dir = 1
                speed = 0
                speeds[loc] = speed
                dirs[loc] = dir

    for loc_ in speeds:
        with open("loc_" + str(loc_) + ".dat") as f:
            data = f.read().split('\n')
        if old_speeds[loc_] != speeds[loc_] or old_dirs[loc_] != dirs[loc_]:
            old_speeds[loc_], old_dirs[loc_] = speeds[loc_], dirs[loc_]
            print('Updating:')
            with open("loc_" + str(loc_) + ".dat", 'w') as f:
                f.write(str(speeds[loc_]) + "\n")
                f.write(str(dirs[loc_]) + "\n")
                f.write(data[2] + "\n")
                f.write(data[3] + "\n")
    if not selecting and loc:
        draw_loc(screen, str(loc), speeds, dirs)
    elif selecting:
        draw_choice(screen)
    pygame.display.flip()
