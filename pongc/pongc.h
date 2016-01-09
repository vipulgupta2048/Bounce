/*
    Copyright 2008 by Wade Brainerd.  
    This file is part of 3D Pong.

    3D Pong is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    3D Pong is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with 3D Pong.  If not, see <http://www.gnu.org/licenses/>.
*/
#ifndef _PONGC_H_
#define _PONGC_H_

#include <Python.h>

#include <gdk/gdkimage.h>
#include <gst/gstbuffer.h>

// 2D primitives
void clear_image(GdkImage* img);

void draw_line_2x(GdkImage* img, int x0, int y0, int x1, int y1, int color);

void draw_ellipse_2x(GdkImage* img, int x, int y, int rx, int ry, int color);
void fill_ellipse_2x(GdkImage* img, int x, int y, int rx, int ry, int color);

// 3D primitives
void set_3d_params(int actual_screen_width, int actual_screen_height, int viewport_scale);

int to_fixed(int x);
int project_x(int x, int y, int z);
int project_y(int x, int y, int z);
void draw_line_3d(GdkImage* img, int x0, int y0, int z0, int x1, int y1, int z1, float c);
void draw_rect_3d(GdkImage* img, int x0, int y0, int x1, int y1, int depth, float c);
void draw_circle_3d(GdkImage* img, int x, int y, int z, int radius, float c);
void fill_circle_3d(GdkImage* img, int x, int y, int z, int radius, float c);
void draw_ellipse_3d(GdkImage* img, int x, int y, int z, int rx, int ry, float c);

#endif

