# Copyright 2009 by Wade Brainerd.  
# This file is part of Bounce.
#
# Bounce is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Bounce is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Bounce.  If not, see <http://www.gnu.org/licenses/>.
#!/usr/bin/env python
"""Bounce - 3D action game by Wade Brainerd <wadetb@gmail.com>."""

import logging, os, time, math, threading, random, time
from gettext import gettext as _

try:
    import json
    json.dumps
except (ImportError, AttributeError):
    import simplejson as json

from pongc import *

# Import GTK.
import gobject, pygtk, gtk, pango, cairo
gobject.threads_init()  

# Import the PyGame mixer for sound output.
import pygame.mixer
pygame.mixer.init()

# Import Sugar modules.
from sugar.activity import activity
from sugar.graphics import *
from sugar.graphics import alert
from sugar.graphics import toggletoolbutton
from sugar.graphics import icon
from sugar.presence import presenceservice

# Initialize logging.
log = logging.getLogger('bounce')
log.setLevel(logging.DEBUG)
logging.basicConfig()
gtk.add_log_handlers()

# This section can be modified to change the default stages that are built into the activity.
DEFAULT_STAGE_DESCS = [
    { 'Name': _('practice'), 'StageDepth': 160, 'StageXGravity': 0,   'StageYGravity': 0,   'BallSize': 1, 'BallSpeed':  2, 'PaddleWidth': 20, 'PaddleHeight': 20, 'AISpeed': 1, 'AIRecenter': 1, },
    { 'Name': _('gravity'),  'StageDepth': 160, 'StageXGravity': 0,   'StageYGravity': 0.5, 'BallSize': 1, 'BallSpeed':  2, 'PaddleWidth': 20, 'PaddleHeight': 20, 'AISpeed': 2, 'AIRecenter': 1, },
    { 'Name': _('wide'),     'StageDepth': 160, 'StageXGravity': 0,   'StageYGravity': 0.5, 'BallSize': 1, 'BallSpeed':  3, 'PaddleWidth': 50, 'PaddleHeight': 15, 'AISpeed': 3, 'AIRecenter': 1, },
    { 'Name': _('deep'),     'StageDepth': 500, 'StageXGravity': 0,   'StageYGravity': 0,   'BallSize': 1, 'BallSpeed': 10, 'PaddleWidth': 25, 'PaddleHeight': 25, 'AISpeed': 2.5, 'AIRecenter': 0, },
    { 'Name': _('rotate'),   'StageDepth': 160, 'StageXGravity': 0.5, 'StageYGravity': 0,   'BallSize': 1, 'BallSpeed':  5, 'PaddleWidth': 25, 'PaddleHeight': 20, 'AISpeed': 3, 'AIRecenter': 1, },
]

# These are the settings that will be applied when a new stage is created using the editor.
NEW_STAGE = { 'Name': _('new stage'), 'StageDepth': 160, 'StageXGravity': 0, 'StageYGravity': 0, 'BallSize': 1, 'BallSpeed':  3, 'PaddleWidth': 20, 'PaddleHeight': 20, 'AISpeed': 1, 'AIRecenter': 1, }

def clamp(a, b, c):
    if (a<b): return b
    elif (a>c): return c
    else: return a

def to_fixed(a):
    return int(a * 256)

def from_fixed(a):
    return a >> 8

def fixed_mul(a, b):
    return (a * b) >> 8

# Three dimensional vector class.
class Vector:
    def __init__(self, x=0, y=0, z=0):
        self.x = x
        self.y = y
        self.z = z

zerovec = Vector(0, 0, 0)

# RGB color class.
class Color:
    def __init__(self, r=255, g=255, b=255):
        self.r = r
        self.g = g
        self.b = b

# Two dimensional rectangle class.
class Rect:
    def __init__(self):
        self.top = 0
        self.left = 0
        self.right = 0
        self.bottom = 0

# Virtual screen dimensions
screen_width = 1200
screen_height = 825
viewport_scale = to_fixed(100)

# Game constants
time_res = 32

def text_cairo (text, x, y, size, c):
    game.cairo.set_source_rgb(c, c, c)

    game.cairo.set_font_size(size)
    x_bearing, y_bearing, width, height = game.cairo.text_extents(text)[:4]
    
    if x == -1: x = screen_width/2
    if y == -1: y = screen_height/2

    game.cairo.move_to(x - width/2 - x_bearing, y - height/2 - y_bearing)
    game.cairo.show_text(text)

class Ball:
    def __init__(self):
        self.lastpos = Vector()
        self.lastvel = Vector()
        self.pos = Vector()
        self.vel = Vector()
        self.size = 1
        self.speed = 1
    
    def setup (self, desc):
        self.size = to_fixed(desc['BallSize'])
        self.speed = to_fixed(desc['BallSpeed'])

        self.pos = Vector(to_fixed(50), to_fixed(25), to_fixed(desc['StageDepth'])/2)
        self.vel = Vector(to_fixed(2), to_fixed(2), self.speed)

    def draw_3d (self, stage):
        # Draw the ball.
        fill_circle_3d(game.drawimage, self.pos.x, self.pos.y, self.pos.z, self.size, game.brightness/100.0)

        # Draw the shadows.
        draw_ellipse_3d(game.drawimage, self.pos.x, stage.window.bottom, self.pos.z, self.size*2, self.size, game.brightness/2/100.0)
        draw_ellipse_3d(game.drawimage, self.pos.x, stage.window.top, self.pos.z, self.size*2, self.size, game.brightness/2/100.0)
        draw_ellipse_3d(game.drawimage, stage.window.left, self.pos.y, self.pos.z, self.size, self.size*2, game.brightness/2/100.0)
        draw_ellipse_3d(game.drawimage, stage.window.right, self.pos.y, self.pos.z, self.size, self.size*2, game.brightness/2/100.0)

    # 0 if nobody scored, 1 if Paddle1 scored, 2 if Paddle2 scored.
    def update (self, paddle1, paddle2, stage):
        # Ball collisions are handled very accurately, as this is the basis of the game.
        # All times are in 1sec/time_res units.
        # 1. Loop through all the surfaces and finds the first one the ball will collide with
        # in this animation frame (if any). 
        # 2. Update the Ball velocity based on the collision, and advance the current time to 
        # the exact time of the collision.
        # 3. Goto step 1, until no collisions remain in the current animation frame.
    
        time_left = time_res                  # Time remaining in this animation frame.
        first_collision_time = 0              # -1 means no collision found.
        first_collision_vel = Vector()    # New ball velocity from first collision.
        first_collision_type = 0              # 0 for normal collision (wall), otherwise the scorezone number hit. 
    
        self.lastpos.x = self.pos.x
        self.lastpos.y = self.pos.y
        self.lastpos.z = self.pos.z
        self.lastvel.x = self.vel.x
        self.lastvel.y = self.vel.y
        self.lastvel.z = self.vel.z
    
        next_ball_pos = Vector()          # Hypothetical ball position assuming no collision.
        cur_time = 0                            # cur_time of current collision.
        
        collision_type = 0                   # Stored return value.
    
        iterations = 0
    
        while True:
            iterations = iterations+1
            if ( iterations > 5 ):
                break
    
            # Calculate new next ball position.
            next_ball_pos.x = self.pos.x + (self.vel.x * time_left) / time_res
            next_ball_pos.y = self.pos.y + (self.vel.y * time_left) / time_res
            next_ball_pos.z = self.pos.z + (self.vel.z * time_left) / time_res
    
            # Reset first_collision_cur_time.     
            first_collision_cur_time = -1
    
            # Check stage walls.  First checks to see if the boundary was crossed, if so then calculates cur_time, etc.
            if ( next_ball_pos.x - self.size <= 0 ): # Left wall
                cur_time = ( self.pos.x - self.size ) * time_res / -self.vel.x # negative Vx is to account for left wall facing.
                if ( first_collision_cur_time == -1 or cur_time < first_collision_cur_time ):
                    # Set new first collision.
                    first_collision_cur_time = cur_time
                    first_collision_vel.x = -self.vel.x
                    first_collision_vel.y = self.vel.y
                    first_collision_vel.z = self.vel.z
                    first_collision_type = 5
            if ( next_ball_pos.x + self.size >= stage.window.right ): # Right wall
                cur_time = ( stage.window.right - ( self.pos.x + self.size ) ) * time_res / self.vel.x
                if ( first_collision_cur_time == -1 or cur_time < first_collision_cur_time ):
                    # Set new first collision.
                    first_collision_cur_time = cur_time
                    first_collision_vel.x = -self.vel.x
                    first_collision_vel.y = self.vel.y
                    first_collision_vel.z = self.vel.z
                    first_collision_type = 5
            if ( next_ball_pos.y - self.size <= 0 and self.vel.y != 0): # Top wall
                cur_time = ( self.pos.y - self.size ) * time_res / -self.vel.y
                if ( first_collision_cur_time == -1 or cur_time < first_collision_cur_time ):
                    # Set new first collision.
                    first_collision_cur_time = cur_time
                    first_collision_vel.x = self.vel.x
                    first_collision_vel.y = -self.vel.y
                    first_collision_vel.z = self.vel.z
                    first_collision_type = 5
            if ( next_ball_pos.y + self.size >= stage.window.bottom  and self.vel.y != 0): # Bottom wall
                cur_time = ( stage.window.bottom - ( self.pos.y + self.size ) ) * time_res / self.vel.y
                if ( first_collision_cur_time == -1 or cur_time < first_collision_cur_time ):
                    # Set new first collision.
                    first_collision_cur_time = cur_time
                    first_collision_vel.x = self.vel.x
                    first_collision_vel.y = -self.vel.y
                    first_collision_vel.z = self.vel.z
                    first_collision_type = 5
            if ( next_ball_pos.z <= 0 ): # Front wall
                cur_time = self.pos.z * time_res / -self.vel.z
                if ( first_collision_cur_time == -1 or cur_time < first_collision_cur_time ):
                    # Set new first collision.
                    first_collision_cur_time = cur_time
                    first_collision_vel.x = self.vel.x #(random.randint(0, 3))-1 * self.speed
                    first_collision_vel.y = self.vel.y #(random.randint(0, 3))-1 * self.speed
                    first_collision_vel.z = self.speed
                    first_collision_type = 2
            if ( next_ball_pos.z >= stage.depth ): # Back wall
                cur_time = ( stage.depth - self.pos.z ) * time_res / self.vel.z
                if ( first_collision_cur_time == -1 or cur_time < first_collision_cur_time ):
                    # Set new first collision.
                    first_collision_cur_time = cur_time
                    first_collision_vel.x = self.vel.x #(random.randint(0, 3))-1 * self.speed
                    first_collision_vel.y = self.vel.y #(random.randint(0, 3))-1 * self.speed
                    first_collision_vel.z = -self.speed
                    first_collision_type = 1
            # Paddle collision.  Paddle collisions are inaccurate, in that it doesn't take into account the velocity of 
            # the ball in its 2D check, it uses the original 2D position.
            if (        self.vel.z < 0 
                    and ( self.pos.z >= paddle1.pos.z or self.pos.z >= paddle1.pos.z - math.fabs(paddle1.delta.z) ) 
                    and ( next_ball_pos.z <= paddle1.pos.z or next_ball_pos.z <= paddle1.pos.z + math.fabs(paddle1.delta.z) )
                    and self.pos.x >= paddle1.pos.x - paddle1.halfwidth
                    and self.pos.x <= paddle1.pos.x + paddle1.halfwidth 
                    and self.pos.y >= paddle1.pos.y - paddle1.halfheight
                    and self.pos.y <= paddle1.pos.y + paddle1.halfheight ):
                cur_time = ( self.pos.z - paddle1.pos.z ) * time_res / -self.vel.z
                if ( first_collision_cur_time == -1 or cur_time <= first_collision_cur_time ):
                    # Set new first collision.
                    first_collision_cur_time = cur_time
                    first_collision_vel.x = self.vel.x
                    first_collision_vel.y = self.vel.y
                    first_collision_vel.z = -self.vel.z
    
                    # If paddle is moving forward, bounce the ball off.
                    if ( paddle1.delta.z > 0 ):
                        first_collision_vel.z += 4*246
    
                        # Apply some pong like angling based on where it hits the paddle.
                        if ( next_ball_pos.x - paddle1.pos.x > 20 ):
                            first_collision_vel.x += 2*256
                        if ( next_ball_pos.x - paddle1.pos.x < -20 ):
                            first_collision_vel.x -= 2*256
    
                        if ( next_ball_pos.y - paddle1.pos.y > 15 ):
                            first_collision_vel.y += 2*256
                        if ( next_ball_pos.y - paddle1.pos.y < -15 ):
                            first_collision_vel.y -= 2*256
                    # Likewise if paddle is moving backwards, cushion it.
                    #if ( paddle1.delta.z < 0 ):
                    #    first_collision_vel.z -= 2*256
                    
                    first_collision_type = 3
            # Computer paddle.
            if (        self.vel.z > 0 
                    and ( self.pos.z <= paddle2.pos.z ) 
                    and ( next_ball_pos.z >= paddle2.pos.z )
                    and self.pos.x >= paddle2.pos.x - paddle2.halfwidth
                    and self.pos.x <= paddle2.pos.x + paddle2.halfwidth 
                    and self.pos.y >= paddle2.pos.y - paddle2.halfheight
                    and self.pos.y <= paddle2.pos.y + paddle2.halfheight ): # Paddle 2
                cur_time = ( paddle2.pos.z - self.pos.z ) * time_res / self.vel.z
                if ( first_collision_cur_time == -1 or cur_time <= first_collision_cur_time ):
                    # Set new first collision.
                    first_collision_cur_time = cur_time
                    first_collision_vel.x = self.vel.x
                    first_collision_vel.y = self.vel.y
                    first_collision_vel.z = -self.vel.z + ( paddle1.delta.z > 0 ) * 2*256 + ( paddle1.delta.z < 0 ) * 2*256
                    first_collision_type = 4
    
            # Advance the ball to the point of the first collision.
            if ( first_collision_cur_time != -1 ):
                self.pos.x += self.vel.x * first_collision_cur_time / time_res
                self.pos.y += self.vel.y * first_collision_cur_time / time_res
                self.pos.z += self.vel.z * first_collision_cur_time / time_res
                self.vel.x = first_collision_vel.x
                self.vel.y = first_collision_vel.y
                self.vel.z = first_collision_vel.z
                
                time_left -= first_collision_cur_time
                collision_type = first_collision_type
            if ( not (first_collision_cur_time != -1 and time_left > 0) ):
                break
    
        # If there's time left in the frame w/o collision, finish it up.    
        if time_left > 0:
            self.pos.x += self.vel.x * time_left / time_res
            self.pos.y += self.vel.y * time_left / time_res
            self.pos.z += self.vel.z * time_left / time_res
    
        # Apply gravity.
        self.vel.y += game.stage.gravity
        if ( self.pos.y + self.size + 20 > stage.window.bottom and math.fabs(self.vel.y) == 0 ):
            self.vel.y -= 6
        self.vel.x += game.stage.crossgravity
    
        # Calculate scores if any collisions with the back wall happened.
        if collision_type == 1:
            paddle1.score += 1
            game.scoresnd.play()
        elif collision_type == 2:
            paddle2.score += 1  
            game.scoresnd.play()
        elif collision_type == 3:
            game.paddle1snd.play()
        elif collision_type == 4:
            game.paddle2snd.play()
        elif collision_type == 5:
            game.wallsnd.play()

        return collision_type

class Paddle:
    def __init__(self):
        # Center of the paddle
        self.pos = Vector()
        
        # Physics stuff
        self.delta = Vector() # Amount moved since last update for spin calc.
        self.halfwidth = 0
        self.halfheight = 0

        # Stuff for moving the paddle forward.
        self.targetz = 0
        self.defaultz = 0
        self.forwardz = 0

        # AI stuff
        self.vel = Vector()
        self.speed = 0

        # Game stuff
        self.score = 0

    def draw_3d (self, stage):
        v = game.brightness/100.0

        r = Rect()
        r.left = self.pos.x - self.halfwidth 
        r.right = self.pos.x + self.halfwidth    
        r.top = self.pos.y - self.halfheight 
        r.bottom = self.pos.y + self.halfheight  
        
        draw_rect_3d( game.drawimage, r.left, r.top, r.right, r.bottom, self.pos.z, v )
    
        x = r.left + ( ( r.right - r.left ) / 2 )
        draw_line_3d( game.drawimage, x, r.bottom, self.pos.z, x, stage.window.bottom, self.pos.z, v )

    def clip_position (self):
        self.pos.x = max(self.pos.x, self.halfwidth)
        self.pos.y = max(self.pos.y, self.halfheight)
        self.pos.x = min(self.pos.x, game.stage.window.right - self.halfwidth)
        self.pos.y = min(self.pos.y, game.stage.window.bottom - self.halfheight)

    def setup_player(self, desc):
        w = to_fixed(desc['PaddleWidth'])
        h = to_fixed(desc['PaddleHeight'])

        self.halfwidth = w
        self.halfheight = h

        self.delta = zerovec
        self.pos = Vector(to_fixed(25), to_fixed(50), to_fixed(10))
        self.clip_position()

        self.defaultz = self.pos.z
        self.targetz = self.pos.z
        self.forwardz = to_fixed(40)

        self.score = 0

    def update_player (self, stage):
        """Check paddle inputs and apply to paddle."""
        lastpos = Vector()
        lastpos.x = self.pos.x
        lastpos.y = self.pos.y
        lastpos.z = self.pos.z

        penx = game.mousex*100/screen_width
        peny = game.mousey*100/screen_height
        pendown = 1

        if ( game.mousedown ):
            self.targetz = self.forwardz
        else:
            self.targetz = self.defaultz

        # Snaps forward, eases back.
        if ( self.pos.z < self.targetz ):
            if ( self.delta.z < to_fixed(4) ):
                self.delta.z = to_fixed(6)
            self.pos.z += self.delta.z + to_fixed(2)
            if ( self.pos.z > self.targetz ):
                self.pos.z = self.targetz

        if ( self.pos.z > self.targetz ):
            self.pos.z += ( self.targetz - self.pos.z ) / 4

        # Get the 2d position from the pen.
        if ( pendown ): 
            self.pos.x = to_fixed(penx)
            self.pos.y = to_fixed(peny)
            self.clip_position()
    
        self.delta.x = self.pos.x - lastpos.x
        self.delta.y = self.pos.y - lastpos.y
        self.delta.z = self.pos.z - lastpos.z

    def setup_ai(self, desc):
        w = to_fixed(desc['PaddleWidth'])
        h = to_fixed(desc['PaddleHeight'])

        self.score = 0

        self.halfwidth = w
        self.halfheight = h

        self.pos = Vector(to_fixed(75), to_fixed(50), game.stage.depth - to_fixed(10))

        self.defaultz = self.pos.z
        self.targetz = self.pos.z
        self.forwardz = game.stage.depth - 40*256

        self.delta = zerovec
        self.vel = zerovec

        self.clip_position()
    
    def update_ai (self, ball, stage):
        """Compute AI and move paddle."""
        # Only move when the ball is coming back, that way it appears to react to the players hit.
        # Actually, start moving just before the player hits it.
        if ( ball.vel.z > 0 or ball.vel.z < 0 and ball.pos.z < to_fixed(30)) :
            # Acceleration towards the ball.
            if ( math.fabs( ( self.pos.x - ball.pos.x ) ) > to_fixed(5) ):
                if ( self.pos.x < ball.pos.x ):
                    self.vel.x += to_fixed(4)
                if ( self.pos.x > ball.pos.x ):
                    self.vel.x -= to_fixed(4)
                
            if ( math.fabs( ( self.pos.y - ball.pos.y ) ) > to_fixed(5) ):
                if ( self.pos.y < ball.pos.y ):
                    self.vel.y += to_fixed(4)
                if ( self.pos.y > ball.pos.y ): 
                    self.vel.y -= to_fixed(4)
            
            # Speed clamping
            self.vel.x = clamp( self.vel.x, -game.ai.speed, game.ai.speed )
            self.vel.y = clamp( self.vel.y, -game.ai.speed, game.ai.speed )
        elif ( ball.pos.z < game.stage.depth/2 ):
            self.vel.x = 0
            self.vel.y = 0
            # Drift towards the center.
            if ( game.ai.recenter ):
                self.pos.x += ( to_fixed(50) - self.pos.x ) / 4
                self.pos.y += ( to_fixed(50) - self.pos.y ) / 4
                
        # Friction
        if ( self.vel.x > 0 ):
            self.vel.x -= 1
        if ( self.vel.x < 0 ):
            self.vel.x += 1
            
        if ( self.vel.y > 0 ):
            self.vel.y -= 1
        if ( self.vel.y < 0 ):
            self.vel.y += 1
            
        self.pos.x += self.vel.x
        self.pos.y += self.vel.y
        self.clip_position()

class Stage:
    def __init__(self):
        self.depth = 0
        self.gravity = 0
        self.crossgravity = 0
        self.window = Rect()

    def setup(self, desc):
        self.name = desc['Name']
        self.depth = to_fixed(desc['StageDepth'])
        self.gravity = to_fixed(desc['StageYGravity'])
        self.crossgravity = to_fixed(desc['StageXGravity'])

        self.window.left = 0
        self.window.right = to_fixed(99)
        self.window.top = 0
        self.window.bottom = to_fixed(99)

    def draw_3d (self):
        window = self.window

        # Wall grids.
        v = game.brightness/4/100.0
        
        i = 1
        while i < 5:
            x = i*(window.right-window.left)/5
            i += 1
            draw_line_3d(game.drawimage, x, window.top, 1, x, window.top, self.depth, v)
            draw_line_3d(game.drawimage, x, window.bottom, 1, x, window.bottom, self.depth, v)
        
        i = 1
        while i < 5:
            x = i*(window.bottom-window.top)/5
            i += 1
            draw_line_3d(game.drawimage, window.left, x, 1, window.left, x, self.depth, v)
            draw_line_3d(game.drawimage, window.right, x, 1, window.right, x, self.depth, v)
            
        i = 1
        while i < 5:
            x = i*(self.depth)/5
            i += 1
            draw_line_3d(game.drawimage, window.left, window.top, x, window.right, window.top, x, v)
            draw_line_3d(game.drawimage, window.left, window.bottom, x, window.right, window.bottom, x, v)
            draw_line_3d(game.drawimage, window.left, window.top, x, window.left, window.bottom, x, v)
            draw_line_3d(game.drawimage, window.right, window.top, x, window.right, window.bottom, x, v)

        # The actual stage.
        v = game.brightness/100.0
    
        # Near and far rectangles   
        draw_rect_3d( game.drawimage, window.left, window.top, window.right, window.bottom, 0, v )
        draw_rect_3d( game.drawimage, window.left, window.top, window.right, window.bottom, self.depth, v )
    
        # Diagonals
        draw_line_3d( game.drawimage, window.left, window.top, 1, window.left, window.top, self.depth, v )
        draw_line_3d( game.drawimage, window.left, window.bottom, 1, window.left, window.bottom, self.depth, v )
        draw_line_3d( game.drawimage, window.right, window.top, 1, window.right, window.top, self.depth, v )
        draw_line_3d( game.drawimage, window.right, window.bottom, 1, window.right, window.bottom, self.depth, v )

class AI:
    def __init__(self):
        self.speed = 0
        self.recenter = False

    def setup (self, desc):
        self.speed = to_fixed(desc['AISpeed'])
        self.recenter = desc['AIRecenter']

class IntroSequence:
    def enter (self):
        self.timer0 = 0
        self.timer1 = 0

    def leave (self):
        pass

    def draw_3d (self):
        if (self.timer1 == 1):
            game.draw_3d()

    def draw_cairo (self):
        if (self.timer1 == 1):
            game.draw_cairo()
        text_cairo(_("b o u n c e"), -1, -1, 100, self.timer0/100.0)

    def update (self):
        if (self.timer1 == 0):
            game.brightness = 0
            self.timer0 += 1
            if (self.timer0 >= 100):
                self.timer1 = 1
        elif (self.timer1 == 1):
            if (game.brightness < 100): game.brightness += 1
            self.timer0 -= 2
            if (self.timer0 <= 0):
                game.introsnd.play()
                game.set_sequence(BallReleaseSequence())

class NewStageSequence:
    def __init__ (self, nextlevel):
        if nextlevel >= len(game.stage_descs):
            nextlevel = 0
        self.nextlevel = nextlevel

    def enter (self):
        self.timer0 = 0
        self.timer1 = 0

    def leave (self):
        pass

    def draw_3d (self):
        game.draw_3d()

    def draw_cairo (self):
        game.draw_cairo()
        text_cairo(game.stage_descs[self.nextlevel]['Name'], -1, -1, 100, (100-game.brightness)/100.0)

    def update (self):
        if (self.timer1 == 0):
            if (game.brightness > 0): game.brightness -= 5
            self.timer0 += 1
            if (self.timer0 >= 20):
                self.timer0 = 0
                self.timer1 = 1
                game.set_level(self.nextlevel)
        elif (self.timer1 == 1):
            self.timer0 += 1
            if (self.timer0 >= 20):
                self.timer0 = 0
                self.timer1 = 2
        elif (self.timer1 == 2):
            if (game.brightness < 100): game.brightness += 5
            self.timer0 += 1
            if (self.timer0 >= 20):
                game.introsnd.play()
                game.set_sequence(BallReleaseSequence())

class BallReleaseSequence:
    def enter (self):
        self.timer0 = 0
        self.timer1 = 0

    def leave (self):
        pass

    def draw_3d (self):
        game.draw_3d()

    def draw_cairo (self):
        game.draw_cairo()
        text_cairo(str(3-self.timer1), -1, -1, 20, math.sin(math.pi*self.timer0/35))

    def update (self):
        if (game.brightness < 100): game.brightness += 1
        self.timer0 += 1
        if (self.timer0 > 35):
            self.timer1 += 1
            self.timer0 = 0
        if (self.timer1 >= 3):
            game.set_sequence(PlaySequence())

class PlaySequence:
    def enter (self):
        self.timer0 = 0
        self.timer1 = 0
        self.endtimeout = 0
        game.brightness = 100

    def leave (self):
        pass

    def draw_3d (self):
        game.draw_3d()

    def draw_cairo (self):
        game.draw_cairo()

    def update (self):
        # Process player input and AI.
        game.paddle1.update_player(game.stage)
        game.paddle2.update_ai(game.ball, game.stage)

        # Run the ball simulation.
        score = game.ball.update(game.paddle1, game.paddle2, game.stage)
        #if game.mousedown:
        #    score = 1
        #    game.paddle1.score += 1
        if score == 1 or score == 2:
            game.set_sequence(ScoreSequence())

class ScoreSequence:
    def enter (self):
        self.step = 0
        self.num_steps = 20
        #game.scoreWav.play()

    def leave (self):
        #game.ball.vel = Vector(to_fixed(2), to_fixed(2), game.ball.vel.z)
        pass

    def draw_3d (self):
        ring_spacing = to_fixed(1)
        ring_speed = to_fixed(1)
        num_rings = 10

        v = (1.0-float(self.step)/self.num_steps)

        fill_circle_3d(game.drawimage, game.ball.lastpos.x+game.ball.lastvel.x*self.step/2, game.ball.lastpos.y+game.ball.lastvel.y*self.step/2, game.ball.lastpos.z+game.ball.lastvel.z*self.step/2, game.ball.size, v)
        random.seed(12345678)
        for ring in range(0, num_rings):
            b = (1.0-float(self.step)/self.num_steps)*(0.5+0.5*math.cos(math.pi*float(ring)/num_rings))
            draw_circle_3d(game.drawimage, game.ball.lastpos.x+game.ball.lastvel.x*ring, game.ball.lastpos.y+game.ball.lastvel.y*ring, game.ball.lastpos.z+game.ball.lastvel.z*ring, (-ring+1)*ring_spacing + ring_speed*self.step, b)

        game.draw_3d()

    def draw_cairo (self):
        game.draw_cairo()

    def update (self):
        self.step += 1
        if self.step >= self.num_steps:
            # Record the scores.
            game.stage_descs[game.curlevel]['Paddle1Score'] = game.paddle1.score
            game.stage_descs[game.curlevel]['Paddle2Score'] = game.paddle2.score
            # Win, Lose or Keep Playing.
            if game.paddle1.score == 5:
                if (game.curlevel == len(game.stage_descs)-1):
                    game.set_sequence(WinSequence())
                else:
                    game.set_sequence(NewStageSequence(game.curlevel+1))
            elif game.paddle2.score == 5:
                game.set_sequence(LoseSequence())
            else:
                game.set_sequence(PlaySequence())

class LoseSequence:
    def enter (self):
        self.timer0 = 0
        self.timer1 = 0

    def leave (self):
        pass

    def draw_3d (self):
        game.draw_3d()

    def draw_cairo (self):
        game.draw_cairo()
        text_cairo("; - {", -1, -1, 24, self.timer0/100.0)

    def update (self):
        if (self.timer1 == 0):
            if (game.brightness > 0): game.brightness -= 5
            self.timer0 += 2
            if (self.timer0 >= 100):
                self.timer1 = 1
                game.new_game()
        elif (self.timer1 == 1):
            self.timer0 -= 2
            if (self.timer0 <= 0):
                game.set_sequence(IntroSequence())
                self.timer0 = 0
                self.timer1 = 0

class WinSequence:
    def enter (self):
        # Create a new score history entry.
        paddle1_score = 0
        paddle2_score = 0
        for i in range(0, len(game.stage_descs)):
            paddle1_score += game.stage_descs[i].get('Paddle1Score', 0)
            paddle2_score += game.stage_descs[i].get('Paddle2Score', 0)

        game.scores.append({'Player1Name':game.player1.props.nick, 'Player1Score':paddle1_score,
                            'Player2Name':game.player2.props.nick, 'Player2Score':paddle2_score})

        self.timer0 = 0
        self.timer1 = 0

    def leave (self):
        pass

    def update (self):
        if (self.timer1 == 0):
            if (game.brightness > 0): game.brightness -= 5
            if (game.brightness <= 0):
                self.timer0 = 0
                self.timer1 = 1
        elif (self.timer1 == 1):
            self.timer0 += 1                
            if self.timer0 >= 1000 or game.mousedown:
                self.timer1 = 2
                self.timer0 = (len(game.stage_descs)-1)*30
        elif (self.timer1 == 2):
            self.timer0 -= 1
            if (self.timer0 <= 0):
                game.new_game()
                game.set_sequence(IntroSequence())
                self.timer0 = 0
                self.timer1 = 0

    def draw_3d (self):
        game.draw_3d()

    def draw_cairo (self):
        game.draw_cairo()

        starty = 250
        total_score = 0
        for i in range(0, len(game.stage_descs)):
            v = clamp(255*self.timer0/60.0 - i*60, 0, 255)/255.0

            player_score = game.stage_descs[i].get('Paddle1Score', 0)
            ai_score = game.stage_descs[i].get('Paddle2Score', 0)
            diff_score = player_score - ai_score

            game.draw_score_cairo(250, starty + i*50, player_score, 1, v)
            text_cairo('-', 475, starty + i*50, 20, v)
            game.draw_score_cairo(550, starty + i*50, ai_score, 2, v)
            text_cairo('=', 775, starty + i*50, 20, v)
            game.draw_score_cairo(850, starty + i*50, diff_score, 1, v)

            text_cairo(game.stage_descs[i]['Name'], 125, starty + i*50, 24, v)

            total_score += diff_score
    
        v = self.timer0/60.0
        game.cairo.set_source_rgb(v, v, v)
        game.cairo.move_to(250, starty + len(game.stage_descs)*50)
        game.cairo.line_to(950, starty + len(game.stage_descs)*50)
        game.cairo.stroke()
        x = 250
        y = starty + (len(game.stage_descs)+1)*50
        for j in range(0, 5*len(game.stage_descs)):
            game.cairo.move_to(game.xpoints[0][0]*20-10+x, game.xpoints[0][1]*20-10+y)
            for p in game.xpoints:
                game.cairo.line_to(p[0]*20-10+x, p[1]*20-10+y)
            game.cairo.line_to(game.xpoints[0][0]*20-10+x, game.xpoints[0][1]*20-10+y)
            if j >= total_score:
                game.cairo.stroke()
            else:
                game.cairo.fill()
            x += 30
            if (x > 980):
                x = 250
                y += 50
    
        text = "; - |"
        if (total_score >= 5*len(game.stage_descs)):
            text = "; - D"
        elif (total_score >= 4*len(game.stage_descs)):
            text = "; - >"
        elif (total_score >= 3*len(game.stage_descs)):
            text = "; - )"
        elif (total_score >= 2*len(game.stage_descs)):
            text = "; - }"
        text_cairo(text, -1, 150, 24, v)

class EditSequence:
    def enter (self):
        game.brightness = 100

    def leave (self):
        pass

    def draw_3d (self):
        game.draw_3d()

    def draw_cairo (self):
        game.draw_cairo()

    def update (self):
        pass

class TestSequence:
    def enter (self):
        game.brightness = 100

    def leave (self):
        pass

    def draw_3d (self):
        game.draw_3d()

    def draw_cairo (self):
        pass

    def update (self):
        # Process player input and AI.
        game.paddle1.update_player(game.stage)
        game.paddle2.update_ai(game.ball, game.stage)

        # Run the ball simulation.
        game.ball.update(game.paddle1, game.paddle2, game.stage)

class Game:
    def __init__(self):
        self.endtimeout = 0

        self.ai = AI()

        self.stage = Stage()
        self.ball = Ball()
        self.paddle1 = Paddle()
        self.paddle2 = Paddle()
        
        # Current stage.
        self.curlevel = 0

        # Variables affecting the sequencer.
        self.sequence = IntroSequence()
        self.sequence.enter()
        self.brightness = 100

        # Current mouse state.
        self.mousex = 0
        self.mousey = 0
        self.mousedown = 0

        # Default stages.
        self.stage_descs = DEFAULT_STAGE_DESCS 

        # Scores.
        self.scores = []

        # The 'X' shape used as an icon.
        self.xpoints = [ (0,0), (0.3,0), (0.5,0.3), (0.7,0), (1,0), (0.7,0.5), (1,1), (0.7,1), (0.5,0.6), (0.3,1), (0,1), (0.3,0.5) ]

        # Create sounds.
        self.scoresnd = pygame.mixer.Sound(activity.get_bundle_path()+'/sound/score.wav')
        self.paddle1snd = pygame.mixer.Sound(activity.get_bundle_path()+'/sound/player1paddle.wav')
        self.paddle2snd = pygame.mixer.Sound(activity.get_bundle_path()+'/sound/player2paddle.wav')
        self.wallsnd = pygame.mixer.Sound(activity.get_bundle_path()+'/sound/wall.wav')
        self.introsnd = pygame.mixer.Sound(activity.get_bundle_path()+'/sound/intro.wav')

    def set_sequence (self, seq):
        self.sequence.leave()
        self.sequence = seq
        self.sequence.enter()

    def set_level(self, level):
        if level < 0 or level > len(self.stage_descs)-1:
            level = 0

        self.curlevel = level
        desc = self.stage_descs[self.curlevel]

        self.stage.setup(desc)
        self.ball.setup(desc)
        self.ai.setup(desc)

        self.paddle1.setup_player(desc)
        self.paddle2.setup_ai(desc)

    def new_game(self):
        self.set_level(0)

    def draw_score_3d(self, x, y, score, player, v):
        for j in range(0, 5):
            px = x + j*30
            py = y
            if j < score:
                fill_ellipse_2x(game.drawimage, px/2, py/2, 6, 6, int(v*255.0))
            else:
                draw_ellipse_2x(game.drawimage, px/2, py/2, 6, 6, int(v*255.0))

    def draw_score_cairo(self, x, y, score, player, c):
        game.cairo.set_source_rgb(c,c,c)
        for j in range(0, 5):
            px = x + j*30
            py = y

            #if player == 1:
            #    game.cairo.move_to(game.xpoints[0][0]*20-10+px, game.xpoints[0][1]*20-10+py)
            #    for p in game.xpoints:
            #        game.cairo.line_to(p[0]*20-10+px, p[1]*20-10+py)
            #    game.cairo.line_to(game.xpoints[0][0]*20-10+px, game.xpoints[0][1]*20-10+py)
            #elif player == 2:
            
            game.cairo.move_to(px + 10, py)
            game.cairo.arc(px, py, 10, 0, 2*math.pi)

            if j < score:
                game.cairo.fill()
            else:
                game.cairo.stroke()


    def draw_3d(self):
        self.stage.draw_3d()
        self.paddle1.draw_3d(self.stage)
        self.paddle2.draw_3d(self.stage)
        self.ball.draw_3d(self.stage)

        v = self.brightness/100.0
        self.draw_score_3d(screen_width*1/4-75, 30, self.paddle1.score, 1, v)
        self.draw_score_3d(screen_width*3/4-75, 30, self.paddle2.score, 2, v)

    def draw_cairo (self):
        #game.cairo.set_source_rgb(color[0]/255.0, color[1]/255.0, color[2]/255.0)
        #text_cairo(game.stage_descs[game.curlevel]['Name'], -1, 30, 24, v)

        text_cairo("%.2f fps" % self.fps, 50, 30, 12, 1.0)

# Global game instance.
game = Game()

# Panel that appears above the game, allowing the currently active stage to be edited.
class EditorPanel(gtk.EventBox):

    STEP_STAGENAME    = 0
    STEP_STAGEDEPTH   = 1
    STEP_STAGEGRAVITY = 2
    STEP_BALL         = 3
    STEP_PADDLE       = 4
    STEP_AI           = 5
    STEP_MAX          = 6

    def __init__ (self, activity):
        gtk.EventBox.__init__(self)

        self.activity = activity

        self.hbox = gtk.HBox()
        self.add(self.hbox)

        self.hbox.set_border_width(10)
        self.hbox.set_spacing(10)

        self.prevbtn = gtk.Button()
        self.prevbtn.add(icon.Icon(icon_name='go-left'))
        self.prevbtn.connect('clicked', self.on_prev)

        self.nextbtn = gtk.Button()
        self.nextbtn.add(icon.Icon(icon_name='go-right'))
        self.nextbtn.connect('clicked', self.on_next)

        self.hbox.pack_end(self.nextbtn, False, False)
        self.hbox.pack_end(self.prevbtn, False, False)

        self.propbox = gtk.HBox()
        self.propbox.set_spacing(20)

        self.hbox.pack_start(self.propbox)

        self.separator = gtk.VSeparator()

        self.stage_label = gtk.Label()
        self.stage_label.set_markup('<big>'+_('Stage')+'</big>')

        self.stagename_label = gtk.Label(_('Name'))
        self.stagename_entry = gtk.Entry()
        self.stagename_entry.connect('changed', self.on_entry_changed)

        self.stagedepth_label = gtk.Label(_('Depth'))
        self.stagedepth_adjust = gtk.Adjustment(100, 10, 1000, 1)
        self.stagedepth_adjust.connect('value-changed', self.on_value_changed)
        self.stagedepth_scale = gtk.HScale(self.stagedepth_adjust)

        self.stagegravity_x_label = gtk.Label(_('X Gravity'))
        self.stagegravity_x_adjust = gtk.Adjustment(0, -3, 3, 1)
        self.stagegravity_x_adjust.connect('value-changed', self.on_value_changed)
        self.stagegravity_x_scale = gtk.HScale(self.stagegravity_x_adjust)
        self.stagegravity_y_label = gtk.Label(_('Y Gravity'))
        self.stagegravity_y_adjust = gtk.Adjustment(1, -3, 3, 1)
        self.stagegravity_y_adjust.connect('value-changed', self.on_value_changed)
        self.stagegravity_y_scale = gtk.HScale(self.stagegravity_y_adjust)

        self.ball_label = gtk.Label()
        self.ball_label.set_markup('<big>'+_('Ball')+'</big>')

        self.ballsize_label = gtk.Label(_('Size'))
        self.ballsize_adjust = gtk.Adjustment(1, 1, 5, 1)
        self.ballsize_adjust.connect('value-changed', self.on_value_changed)
        self.ballsize_scale = gtk.HScale(self.ballsize_adjust)
        self.ballspeed_label = gtk.Label(_('Speed'))
        self.ballspeed_adjust = gtk.Adjustment(10, 1, 20, 1)
        self.ballspeed_adjust.connect('value-changed', self.on_value_changed)
        self.ballspeed_scale = gtk.HScale(self.ballspeed_adjust)

        self.paddle_label = gtk.Label()
        self.paddle_label.set_markup('<big>'+_('Paddle')+'</big>')

        self.paddlesize_x_label = gtk.Label(_('X Size'))
        self.paddlesize_x_adjust = gtk.Adjustment(20, 1, 50, 1)
        self.paddlesize_x_adjust.connect('value-changed', self.on_value_changed)
        self.paddlesize_x_scale = gtk.HScale(self.paddlesize_x_adjust)
        self.paddlesize_y_label = gtk.Label(_('Y Size'))
        self.paddlesize_y_adjust = gtk.Adjustment(20, 1, 50, 1)
        self.paddlesize_y_adjust.connect('value-changed', self.on_value_changed)
        self.paddlesize_y_scale = gtk.HScale(self.paddlesize_y_adjust)

        self.ai_label = gtk.Label()
        self.ai_label.set_markup('<big>'+_('AI')+'</big>')

        self.aispeed_label = gtk.Label(_('Speed'))
        self.aispeed_adjust = gtk.Adjustment(1, 1, 10, 1)
        self.aispeed_adjust.connect('value-changed', self.on_value_changed)
        self.aispeed_scale = gtk.HScale(self.aispeed_adjust)

        self.show_all()

        self.ignore_changes = False

        self.set_step(EditorPanel.STEP_STAGENAME)

    def on_entry_changed (self, editable):
        if not self.ignore_changes:
            self.copy_to_desc(game.stage_descs[game.curlevel])
            game.set_level(game.curlevel)
            self.activity.queue_draw()

    def on_value_changed (self, adjustment):
        if not self.ignore_changes:
            self.copy_to_desc(game.stage_descs[game.curlevel])
            game.set_level(game.curlevel)
            self.activity.queue_draw()

    def copy_from_desc (self, desc):
        self.ignore_changes = True
        self.stagename_entry.set_text(desc['Name'])
        self.stagedepth_adjust.set_value(desc['StageDepth'])
        self.stagegravity_x_adjust.set_value(desc['StageXGravity'])
        self.stagegravity_y_adjust.set_value(desc['StageYGravity'])
        self.ballsize_adjust.set_value(desc['BallSize'])
        self.ballspeed_adjust.set_value(desc['BallSpeed'])
        self.paddlesize_x_adjust.set_value(desc['PaddleWidth'])
        self.paddlesize_y_adjust.set_value(desc['PaddleHeight'])
        self.aispeed_adjust.set_value(desc['AISpeed'])
        self.ignore_changes = False

    def copy_to_desc (self, desc):
        desc['Name'] = self.stagename_entry.get_text()
        desc['StageDepth'] = self.stagedepth_adjust.get_value()
        desc['StageXGravity'] = self.stagegravity_x_adjust.get_value()
        desc['StageYGravity'] = self.stagegravity_y_adjust.get_value()
        desc['BallSize'] = self.ballsize_adjust.get_value()
        desc['BallSpeed'] = self.ballspeed_adjust.get_value()
        desc['PaddleWidth'] = self.paddlesize_x_adjust.get_value()
        desc['PaddleHeight'] = self.paddlesize_y_adjust.get_value()
        desc['AISpeed'] = self.aispeed_adjust.get_value()

    def update_step_btns(self):
        self.prevbtn.set_sensitive(self.step > 0)
        self.nextbtn.set_sensitive(self.step < EditorPanel.STEP_MAX-1)

    def on_prev (self, btn):
        if self.step > 0:
            self.set_step(self.step-1)

    def on_next (self, btn):
        if self.step < EditorPanel.STEP_MAX-1:
            self.set_step(self.step+1)

    def set_step (self, step):
        for w in self.propbox.get_children():
            self.propbox.remove(w)

        self.step = step

        self.update_step_btns()

        if self.step == EditorPanel.STEP_STAGENAME:
            self.propbox.pack_start(self.stage_label, False, False)
            self.propbox.pack_start(self.separator, False, False)
            self.propbox.pack_start(self.stagename_label, False, False)
            self.propbox.pack_start(self.stagename_entry)

        if self.step == EditorPanel.STEP_STAGEDEPTH:
            self.propbox.pack_start(self.stage_label, False, False)
            self.propbox.pack_start(self.separator, False, False)
            self.propbox.pack_start(self.stagedepth_label, False, False)
            self.propbox.pack_start(self.stagedepth_scale)

        if self.step == EditorPanel.STEP_STAGEGRAVITY:
            self.propbox.pack_start(self.stage_label, False, False)
            self.propbox.pack_start(self.separator, False, False)
            self.propbox.pack_start(self.stagegravity_x_label, False, False)
            self.propbox.pack_start(self.stagegravity_x_scale)
            self.propbox.pack_start(self.stagegravity_y_label, False, False)
            self.propbox.pack_start(self.stagegravity_y_scale)

        if self.step == EditorPanel.STEP_BALL:
            self.propbox.pack_start(self.ball_label, False, False)
            self.propbox.pack_start(self.separator, False, False)
            self.propbox.pack_start(self.ballsize_label, False, False)
            self.propbox.pack_start(self.ballsize_scale)
            self.propbox.pack_start(self.ballspeed_label, False, False)
            self.propbox.pack_start(self.ballspeed_scale)

        if self.step == EditorPanel.STEP_PADDLE:
            self.propbox.pack_start(self.paddle_label, False, False)
            self.propbox.pack_start(self.separator, False, False)
            self.propbox.pack_start(self.paddlesize_x_label, False, False)
            self.propbox.pack_start(self.paddlesize_x_scale)
            self.propbox.pack_start(self.paddlesize_y_label, False, False)
            self.propbox.pack_start(self.paddlesize_y_scale)

        if self.step == EditorPanel.STEP_AI:
            self.propbox.pack_start(self.ai_label, False, False)
            self.propbox.pack_start(self.separator, False, False)
            self.propbox.pack_start(self.aispeed_label, False, False)
            self.propbox.pack_start(self.aispeed_scale)

        self.propbox.show_all()

# Panel that appears over the game, showing a list of scores.  Can be toggled on and off without pausing the game.
class ScorePanel(gtk.VBox):
    def __init__ (self):
        gtk.VBox.__init__(self)

        # Header bar.
        headerbox = gtk.VBox()
        headerbox.set_spacing(20)
        lbl = gtk.Label()
        lbl.set_markup("<span size='x-large'><b>"+_('History of Games')+"</b></span>")
        headerbox.pack_start(lbl, False)
        headerbox.pack_start(gtk.HSeparator(), False)
        hbox = gtk.HBox()
        hbox.set_homogeneous(True)
        lbl = gtk.Label()
        lbl.set_markup('<b>'+_('Player 1')+'</b>')
        hbox.pack_start(lbl)
        lbl = gtk.Label()
        lbl.set_markup('<b>'+_('Score')+'</b>')
        hbox.pack_start(lbl)
        lbl = gtk.Label()
        lbl.set_markup('<b>'+_('Player 2')+'</b>')
        hbox.pack_end(lbl)
        lbl = gtk.Label()
        lbl.set_markup('<b>'+_('Score')+'</b>')
        hbox.pack_end(lbl)
        headerbox.pack_start(hbox, False)
        headerbox.pack_start(gtk.HSeparator(), False)

        # Score box.
        self.scorebox = gtk.VBox()
        self.scorebox.set_spacing(10)

        vbox = gtk.VBox()
        vbox.set_border_width(20)
        vbox.set_spacing(10)
        vbox.pack_start(headerbox, False)
        vbox.pack_start(self.scorebox, False)
        vbox.pack_start(gtk.HSeparator(), False)

        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.scroll.add_with_viewport(vbox)

        frame = gtk.Frame()
        frame.set_shadow_type(gtk.SHADOW_OUT)
        frame.add(self.scroll)
        self.add(frame)

        self.rebuild()
        self.show_all()

    def rebuild (self):
        for w in self.scorebox.get_children():
            w.destroy()

        for s in game.scores:
            hbox = gtk.HBox()
            hbox.set_homogeneous(True)
            hbox.pack_start(gtk.Label(s['Player1Name']))
            hbox.pack_start(gtk.Label(s['Player1Score']))
            hbox.pack_end(gtk.Label(s['Player2Name']))
            hbox.pack_end(gtk.Label(s['Player2Score']))
            self.scorebox.pack_start(hbox, False)

# This is a fake Presence Service Buddy object that represents computer players.
class ComputerBuddyProps:
    def __init__ (self):
        self.nick = 'Computer'

class ComputerBuddy:
    def __init__ (self):
        self.props = ComputerBuddyProps()

# Activity class for the game.  Defines the game user interface (toolbar, etc), controls loading & saving, interacts
# with the Sugar environment.
class BounceActivity(activity.Activity):

    # Game mode definitions.
    MODE_GAME = 0
    MODE_EDIT = 1

    def __init__ (self, handle):
        activity.Activity.__init__(self, handle)
        self.set_title(_("Bounce"))

        # Build the toolbars.
        self.build_toolbox()

        # Set up the drawing window and context.
        self.build_drawarea()

        # Build the editor.
        self.build_editor()

        # Build the score panel.
        self.build_scorepanel()

        # Turn off double buffering except for the drawarea, which mixes cairo and custom drawing.
        self.set_double_buffered(False)
        self.drawarea.set_double_buffered(True)

        # Initialize the game.
        game.new_game()

        self.paused = False
        self.mode = BounceActivity.MODE_GAME

        # Initialize the FPS counter & limiter.
        self.lastclock = time.time()
        game.fps = 0.0
        self.limitfps = 20.0 # 20fps is what the XO can currently handle.

        # Get current player info for the scores table.
        self.pservice = presenceservice.get_instance()
        self.owner = self.pservice.get_owner()

        # Fill in game players.
        game.player1 = self.owner
        game.player2 = ComputerBuddy()

        # Show everything except the panels.
        self.set_canvas(self.drawarea)
        self.show_interface()
        
        # Get the mainloop ready to run (this should come last).
        gobject.timeout_add(50, self.mainloop)

    #-----------------------------------------------------------------------------------------------------------------
    # User interface building.

    def build_drawarea (self):
        self.drawarea = gtk.Layout()
        #self.drawarea.set_visible_window(True)
        self.drawarea.set_size_request(gtk.gdk.screen_width(), gtk.gdk.screen_height())

        self.vbox = gtk.VBox()
        self.drawarea.put(self.vbox, 0, 0)

        self.drawarea.connect('destroy', self.on_destroy)
        #self.drawarea.connect('configure-event', self.on_drawarea_resize)
        self.drawarea.connect('expose-event', self.on_drawarea_expose)

        self.drawarea.add_events(gtk.gdk.POINTER_MOTION_MASK|gtk.gdk.BUTTON_PRESS_MASK|gtk.gdk.BUTTON_RELEASE_MASK)
        self.drawarea.connect('motion-notify-event', self.on_mouse)
        self.drawarea.connect('button-press-event', self.on_mouse)
        self.drawarea.connect('button-release-event', self.on_mouse)

        self.drawimage = None
        game.drawimage = None

    def build_gamebox (self):
        self.pausebtn = toolbutton.ToolButton('media-playback-pause')
        self.pausebtn.set_tooltip(_("Pause Game"))
        self.pausebtn.connect('clicked', self.on_game_pause)

        self.showscoresbtn = toggletoolbutton.ToggleToolButton('Show-history')
        self.showscoresbtn.set_tooltip(_("Show History"))
        self.showscoresbtn.connect('clicked', self.on_game_showscores)
        self.clearscoresbtn = toolbutton.ToolButton('Reset-history')
        self.clearscoresbtn.set_tooltip(_("Reset History"))
        self.clearscoresbtn.connect('clicked', self.on_game_clearscores)

        sep = gtk.SeparatorToolItem()
        sep.set_expand(True)
        sep.set_draw(False)

        self.editbtn = toolbutton.ToolButton('dialog-ok')
        self.editbtn.set_tooltip(_("Edit"))
        self.editbtn.connect('clicked', self.on_edit)

        self.gamebox = gtk.Toolbar()
        self.gamebox.insert(self.pausebtn, -1)
        self.gamebox.insert(self.showscoresbtn, -1)
        self.gamebox.insert(self.clearscoresbtn, -1)
        self.gamebox.insert(sep, -1)
        self.gamebox.insert(self.editbtn, -1)

    def build_editbox (self):
        self.testbtn = toggletoolbutton.ToggleToolButton('zoom-in')
        self.testbtn.set_tooltip(_("Test Stage"))
        self.testbtn.connect('clicked', self.on_edit_test)

        self.prevstagebtn = toolbutton.ToolButton('go-left')
        self.prevstagebtn.set_tooltip(_("Previous Stage"))
        self.prevstagebtn.connect('clicked', self.on_edit_prevstage)

        self.nextstagebtn = toolbutton.ToolButton('go-right')
        self.nextstagebtn.set_tooltip(_("Next Stage"))
        self.nextstagebtn.connect('clicked', self.on_edit_nextstage)

        self.deletestagebtn = toolbutton.ToolButton('list-remove')
        self.deletestagebtn.set_tooltip(_("Delete Stage"))
        self.deletestagebtn.connect('clicked', self.on_edit_deletestage)

        self.addstagebtn = toolbutton.ToolButton('list-add')
        self.addstagebtn.set_tooltip(_("Add New Stage"))
        self.addstagebtn.connect('clicked', self.on_edit_addstage)

        sep = gtk.SeparatorToolItem()
        sep.set_expand(True)
        sep.set_draw(False)

        self.gamebtn = toolbutton.ToolButton('dialog-ok')
        self.gamebtn.set_tooltip(_("Play"))
        self.gamebtn.connect('clicked', self.on_game)

        self.editbox = gtk.Toolbar()
        self.editbox.insert(self.testbtn, -1)
        self.editbox.insert(gtk.SeparatorToolItem(), -1)
        self.editbox.insert(self.prevstagebtn, -1)
        self.editbox.insert(self.nextstagebtn, -1)
        self.editbox.insert(gtk.SeparatorToolItem(), -1)
        self.editbox.insert(self.deletestagebtn, -1)
        self.editbox.insert(self.addstagebtn, -1)
        self.editbox.insert(sep, -1)
        self.editbox.insert(self.gamebtn, -1)

    def build_toolbox (self):
        self.build_gamebox()

        self.tbox = activity.ActivityToolbox(self)
        self.tbox.add_toolbar(_("Game"), self.gamebox)
        self.tbox.show_all()

        self.set_toolbox(self.tbox)

    def build_editor (self):
        self.editor = EditorPanel(self)
        self.vbox.pack_start(self.editor, False)

    def build_scorepanel (self):
        self.scorepanel = ScorePanel()
        align = gtk.Alignment(0.0, 0.0, 1.0, 1.0)
        align.set_padding(50, 50, 100, 100)
        align.add(self.scorepanel)
        self.vbox.pack_start(align, True, True)

    def show_interface (self):
        self.show_all()

        if self.showscoresbtn.get_active():
            self.scorepanel.show_all()
        else:
            self.scorepanel.hide_all()

        if self.mode == BounceActivity.MODE_EDIT:
            self.editor.show_all()
        else:
            self.editor.hide_all()
        
    #-----------------------------------------------------------------------------------------------------------------
    # Game toolbar

    def on_game_pause (self, button):
        self.pause_game(not self.paused)

    def on_game_showscores (self, button):
        if button.get_active():
            self.scorepanel.rebuild()
            self.scorepanel.show_all()
        else:
            self.scorepanel.hide_all()

    def on_game_clearscores (self, button):
        msg = alert.ConfirmationAlert()
        msg.props.title = _('Reset History?')
        msg.props.msg = _('This will erase the history of games played.')

        def response(alert, response_id, self):
            self.remove_alert(alert)
            if response_id is gtk.RESPONSE_OK:
                game.scores = []
                self.scorepanel.rebuild()

        msg.connect('response', response, self)

        self.add_alert(msg)
        msg.show_all()

    #-----------------------------------------------------------------------------------------------------------------
    # Edit toolbar
    
    def on_edit_test (self, button):
        if button.get_active():
            game.set_sequence(TestSequence())
            self.pause_game(False)
            self.queue_draw()
        else:
            self.pause_game(True)
            game.set_level(game.curlevel)
            game.set_sequence(EditSequence())
            self.queue_draw()

    def edit_stage(self, stage_num):
        game.set_level(stage_num)
        self.editor.copy_from_desc(game.stage_descs[stage_num])
        self.queue_draw()
        self.prevstagebtn.set_sensitive(stage_num > 0)
        self.nextstagebtn.set_sensitive(stage_num < len(game.stage_descs)-1)
        
    def on_edit_prevstage (self, button):
        if game.curlevel > 0:
            self.edit_stage(game.curlevel-1)

    def on_edit_nextstage (self, button):
        if game.curlevel < len(game.stage_descs)-1:
            self.edit_stage(game.curlevel+1)

    def on_edit_addstage (self, button):
        game.stage_descs.append(NEW_STAGE.copy())

        self.edit_stage(len(game.stage_descs)-1)

    def on_edit_deletestage (self, button):
        if len(game.stage_descs) <= 1:
            return

        del game.stage_descs[game.curlevel]

        if game.curlevel > len(game.stage_descs)-1:
            self.edit_stage(len(game.stage_descs)-1)
        else:
            self.edit_stage(game.curlevel)

    #-----------------------------------------------------------------------------------------------------------------
    # DrawArea event handlers - Drawing, resizing, etc.

    def on_drawarea_resize (self):
        rect = self.drawarea.get_allocation()
        #log.debug("drawarea resized to %dx%d", rect[2], rect[3])

        self.vbox.set_size_request(rect[2], rect[3])

        # Set 3D parameters.
        global screen_width
        global screen_height
        screen_width = rect[2]
        screen_height = rect[3]
        set_3d_params(screen_width, screen_height, viewport_scale)

        # Rebuild drawimage.
        self.drawimage = gtk.gdk.Image(gtk.gdk.IMAGE_FASTEST, gtk.gdk.visual_get_system(), rect[2], rect[3])
        game.drawimage = self.drawimage

        return True

    def on_drawarea_expose (self, widget, event):
        if not self.drawarea.bin_window:
            return True

        rect = self.drawarea.get_allocation()
        if self.drawimage is None or (rect[2] != screen_width or rect[3] != screen_height):
            self.on_drawarea_resize()

        # Perform 3D rendering to the offscreen image and draw it to the screen.
        clear_image(self.drawimage)
        game.sequence.draw_3d()
        gc = self.drawarea.get_style().fg_gc[gtk.STATE_NORMAL]
        self.drawarea.bin_window.draw_image(gc, self.drawimage, 0, 0, 0, 0, -1, -1)

        # Perform Cairo rendering over the top.
        game.cairo = self.drawarea.bin_window.cairo_create()
        game.sequence.draw_cairo()
        game.cairo = None

        # Hack to fix toolbox refresh.
        #self.tbox.queue_draw()
    
    #-----------------------------------------------------------------------------------------------------------------
    # Game control - Editor / Game modes, pausing, etc.

    def set_mode (self, mode):
        self.mode = mode

        if self.mode == BounceActivity.MODE_GAME:
            self.tbox.remove_toolbar(1)
            self.build_gamebox()
            self.tbox.add_toolbar(_("Game"), self.gamebox)
            self.gamebox.show_all()
            self.tbox.set_current_toolbar(1)

            self.pause_game(False)

            self.editor.hide_all()
            game.set_sequence(IntroSequence())
            self.queue_draw()

        if self.mode == BounceActivity.MODE_EDIT:
            self.showscoresbtn.set_active(False)
            game.scores = []
            self.scorepanel.rebuild()

            self.tbox.remove_toolbar(1)
            self.build_editbox()
            self.tbox.add_toolbar(_("Edit"), self.editbox)
            self.editbox.show_all()
            self.tbox.set_current_toolbar(1)

            self.edit_stage(game.curlevel)
            self.pause_game(True)

            self.editor.show_all()
            game.set_sequence(EditSequence())
            self.queue_draw()

    def on_edit (self, button):
        msg = alert.ConfirmationAlert()
        msg.props.title = _('Change to Edit Mode?')
        msg.props.msg = _('If you change to edit mode, the history of games will be cleared.')

        def response(alert, response_id, self):
            self.remove_alert(alert)
            if response_id is gtk.RESPONSE_OK:
                self.set_mode(BounceActivity.MODE_EDIT)

        msg.connect('response', response, self)

        self.add_alert(msg)
        msg.show_all()

    def on_game (self, button):
        self.set_mode(BounceActivity.MODE_GAME)

    def pause_game (self, p):
        self.paused = p
        if self.paused:
            self.pausebtn.set_icon('media-playback-start')
        else:
            self.pausebtn.set_icon('media-playback-pause')

    def on_mouse (self, widget, event):
        game.mousex = int(event.x)
        game.mousey = int(event.y)
        if event.type == gtk.gdk.BUTTON_PRESS:
            # Simple cheat for testing.
            #if (game.paddle1.score < 5):
            #    game.paddle1.score += 1
            game.mousedown = 1
        if event.type == gtk.gdk.BUTTON_RELEASE:
            game.mousedown = 0

    #-----------------------------------------------------------------------------------------------------------------
    # Main loop

    def on_destroy (self, widget):
        self.running = False

    def tick (self):
        if self.paused:
            return True

        # Update current game sequence and animate.
        game.sequence.update()
        self.drawarea.queue_draw()

        # Compute framerate.
        diff = float(time.time() - self.lastclock)
        if diff > 0:
            game.fps = 1.0 / diff
        self.lastclock = time.time()

        return True

    def mainloop (self):
        """Runs the game loop.  Note that this doesn't actually return until the activity ends."""
        self.running = True
        clock = pygame.time.Clock()
        while self.running:
            clock.tick(self.limitfps)
            self.tick()
            while gtk.events_pending():
                gtk.main_iteration(False)
        return False

    #-----------------------------------------------------------------------------------------------------------------
    # Journal integration

    def read_file(self, file_path):
        # Load document.
        if self.metadata['mime_type'] == 'text/plain':
            fd = open(file_path, 'r')
            try:
                data = fd.read()
            finally:
                fd.close()

            storage = json.loads(data)

            # Restore stages.
            game.stage_descs = storage['Stages']
            game.scores = storage['Scores']

            # Restore activity state.
            game.set_level(storage.get('curlevel', 0))
            self.set_mode(storage.get('mode', BounceActivity.MODE_GAME))
            self.showscoresbtn.set_active(storage.get('history_visible', False))

            # Always start resumed games paused, with the scores up.
            self.pause_game(True)
            # (not working at the moment, the window comes up but the button stays inactive)
            if self.mode == BounceActivity.MODE_GAME:
                self.showscoresbtn.set_active(True)

    def write_file(self, file_path):
        # Save document.
        if not self.metadata['mime_type']:
            self.metadata['mime_type'] = 'text/plain'

        storage = {}

        # Save stages.
        storage['Stages'] = game.stage_descs
        storage['Scores'] = game.scores

        # Save activity state.
        storage['curlevel'] = game.curlevel
        storage['mode'] = self.mode
        storage['history_visible'] = self.showscoresbtn.get_active()

        fd = open(file_path, 'w')
        try:
            fd.write(json.dumps(storage))
        finally:
            fd.close()

    #def take_screenshot (self):
    #    if self.easelarea and self.drawarea.bin_window:
    #        self._preview.take_screenshot(self.drawarea.bin_window)

