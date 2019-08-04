from appJar import gui
import os
import sys
from picamera import PiCamera
import time
import RPi.GPIO as GPIO
import pigpio
import time
import pygame, sys

from pygame.locals import *
import pygame.camera

width = 640
height = 640

#initialise pygame
pygame.init()
pygame.camera.init()


os.system("sudo pigpiod")
app = gui()

ROWS = 24       # number of rows in the tray
COLS = 12      # number of columns in tray

x_DIR = 20     # x_DIRection GPIO Pin
x_STEP = 21    # x_STEP GPIO Pin

y_DIR = 19     # y_DIRection GPIO Pin
y_STEP = 26    # y_STEP GPIO Pin

SWITCH_X = 16    # GPIO pin of kill switch for x axis
SWITCH_Y = 24   # GPIO pin of kill switch for y axis

# Use BCM GPIO references
# instead of physical pin numbers
GPIO.setmode(GPIO.BCM)

# Connect to pigpiod daemon
pi = pigpio.pi()

# Set up Nema pins as an output
pi.set_mode(x_DIR, pigpio.OUTPUT)
pi.set_mode(x_STEP, pigpio.OUTPUT)
pi.set_mode(y_DIR, pigpio.OUTPUT)
pi.set_mode(y_STEP, pigpio.OUTPUT)

# Set up input switch
pi.set_mode(SWITCH_X, pigpio.INPUT)
pi.set_pull_up_down(SWITCH_X, pigpio.PUD_UP)
pi.set_mode(SWITCH_Y, pigpio.INPUT)
pi.set_pull_up_down(SWITCH_Y, pigpio.PUD_UP)

def generate_ramp(ramp, motor):
    """Generate ramp wave forms.
    ramp:  List of [Frequency, x_STEPs]
    """
    if(motor == 'x'):
        STEP = x_STEP
    elif(motor == 'y'):
        STEP = y_STEP
    pi.wave_clear()     # clear existing waves
    length = len(ramp)  # number of ramp levels
    wid = [-1] * length

    # Generate a wave per ramp level
    for i in range(length):
        frequency = ramp[i][0]
        micros = int(500000 / frequency)
        wf = []
        wf.append(pigpio.pulse(1 << STEP, 0, micros))  # pulse on
        wf.append(pigpio.pulse(0, 1 << STEP, micros))  # pulse off
        pi.wave_add_generic(wf)
        wid[i] = pi.wave_create()

    # Generate a chain of waves
    chain = []
    for i in range(length):
        steps = ramp[i][1]
        x = steps & 255
        y = steps >> 8
        chain += [255, 0, wid[i], 255, 1, x, y]

    pi.wave_chain(chain)  # Transmit chain.

def take_picture(direction, row, col):
    """Uses Pygame to take picture with the microscope
    camera
    """
    cam = pygame.camera.Camera("/dev/video0",(width,height))
    cam.start()
    time.sleep(.5)
    if(direction==1):
        image = cam.get_image()
        cam.stop()
        pygame.image.save(image, 'pics/well_(%s%s).jpg'%(chr(row + 65), 12-col))   #save image as well_A4 for instance
    elif(direction == 0):
        image = cam.get_image()
        cam.stop()
        pygame.image.save(image,'pics/well_(%s%s).jpg'%(chr(row + 65), col+1))

def move_x_axis(direction, pulse = 1):
    """For controlling the x-axis motor
    params:
    direction: 0 or 1 signifies direction of axis movement
    pulse: 0 means no pulse, 1 means pulse the motor
    """
    if pulse == 1:                    #if pulse is 1, motor will accel then decel
        if (direction ==1):
                pi.write(x_DIR, True)
                generate_ramp([[700, 45],
                              [800, 45],
		    	      [900, 45],
			      [800, 45],
	    		      [700, 45]], 'x')
                time.sleep(.5)
        elif direction ==0:
                pi.write(x_DIR, False)
                generate_ramp([[700, 45],
                              [800, 45],
                              [900, 45],
                              [800, 45],
                              [700, 45]], 'x')
                time.sleep(.5)
    elif pulse == 0:		    #when pulse is 0, motor will just accel
        if (direction ==1):
            pi.write(x_DIR, True)
            generate_ramp([[700, 100]], 'x')
            time.sleep(.2)
        else:
            pi.write(x_DIR, False)
            generate_ramp([[700, 100]], 'x')
            time.sleep(.2)


def move_y_axis(direction, pulse = 1, big_jump = 0):
    """For controlling the y-axis motor
    params:
    direction: 0 or 1 signifies direction of axis movement
    pulse: 0 means no pulse, 1 means pulse the motor
    bigjump: 1 means pulse the motor longer than normal
    """
    if pulse == 1:              # when pulse is on, motor accels and decels
        if direction == 0:
            if (big_jump == 0):    # most rows are a small distance appart, they require no "big jump"
                pi.write(y_DIR, True)
                generate_ramp([[700, 2],
                               [800, 3],
                               [900, 3],
                               [800, 3],
                               [700, 1]], 'y')
                time.sleep(.5)

            elif (big_jump):       #every 3rd row requires a "big jump" to get there
                print("big Jump")
                pi.write(y_DIR, True)
                generate_ramp([[700, 4],
                               [800, 4],
                               [900, 5],
                               [800, 5],
                               [700, 4]], 'y')
                time.sleep(.5)

        elif direction ==1:
            print("generating ramp with 1 step")
            pi.write(y_DIR, False)
            generate_ramp([[700, 2],
                           [800, 3],
                           [900, 3],
                           [800, 3],
                           [700, 1]], 'y')
            time.sleep(.5)

    elif pulse == 0:                       # when pulse is 0, motor just accels
        if direction == 1:
            pi.write(y_DIR, True)
            generate_ramp([[700, 100]], 'y')
            time.sleep(.2)
        elif direction ==0:
            pi.write(y_DIR, False)
            generate_ramp([[700, 100]], 'y')
            time.sleep(.2)


def picture_sequence():
    """This is the main routine, it moves the tray around
    and takes pictures of each well
    """
    app.addStatusbar(fields = 3)
    app.setStatusbar("In Progress:", 0)
    app.setStatusbar("Picture Sequence", 1)

    for row in range(ROWS):  # for each row of wells on the dish
      if (row & 1):          # on odd rows, set x_axis direction to 1
        direction = 1
        print ("direction: 1")
      else:                  # on even rows, set x_axis direction to 0
        direction = 0
        print ("direction: 0")

      for col in range(COLS):                   # for each column in dish,
        take_picture(direction, row, col)       # snap a picture of the well
        move_x_axis(direction)                  # pulse x axis

      if(row<ROWS):	  # while not on the last row of dish,
        if((row+1) % 3 == 0):   # every third row,
           move_y_axis(0, 1, 1) # pulse y axis and perform a big jump: move_y_axis(direction, pulse, big jump)
        else:                   # if not a third row...
           move_y_axis(0)	# pulse y axis down, don't perform a big jump
      row+=1
      #app.clearStatusbar()

def return_home():
    """
    A function to reset the bed to its home position
    """
    app.addStatusbar(fields = 3)
    app.setStatusbar("In Progress", 0)
    app.setStatusbar("Returning Home", 1)
    while(pi.read(SWITCH_X)):      # while x-kill switch is open,
       print('x kill open')
       move_x_axis(1, 0)           # move x_axis without pulse
    while(pi.read(SWITCH_X) == 0): # now kill switch is pushed,
       print('y kill pushed')
       move_x_axis(0, 0)           # move x_axis other direction until kill switch is open

    while(pi.read(SWITCH_Y)):      # while y-kill switch is open,
       print('y kill open')
       move_y_axis(0, 0)           # move y_axis, without pulsing
    while(pi.read(SWITCH_Y) == 0): # now kill switch is pushed,
       print('y kill pushed')
       move_y_axis(1, 0)           # move y_axis other direction until kill switch is open

#move_y_axis(0, 1, 1)
app.setSize(500,500)
app.addButton("Start Picture Sequence", picture_sequence)
app.addButton("Return Home", return_home)
app.go()

