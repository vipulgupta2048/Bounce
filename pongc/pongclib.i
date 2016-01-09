/*
    Copyright 2008 by  Wade Brainerd.  
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
%module pongclib

%{
#include <pygobject.h>
#include "pongc.h"
%}

// Testing facility.
%typemap(in) void* {
        $1 = $input;
}

// Pass a gst.Buffer as a GstBuffer*.
%typemap(in) GstBuffer* {
        // todo- Error checking would be nice.
        PyGObject* pygo = (PyGObject*)$input;
        GstBuffer* buf = (GstBuffer*)pygo->obj;
        $1 = buf;
}

// Pass a gtk.gdk.Image as a GdkImage*.
%typemap(in) GdkImage* {
        // todo- Error checking would be nice.
        PyGObject* pygo = (PyGObject*)$input;
        GdkImage* img = (GdkImage*)pygo->obj;
        $1 = img;
}

%include "pongc.h"

