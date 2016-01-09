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
#include "pongc.h"

typedef guint16 depth16_t;
typedef guint32 depth24_t;

template <typename pixel_t> inline
void _clear_image(GdkImage* img)
{
	pixel_t* pixels = (pixel_t*)img->mem;
	int pitch = img->bpl/sizeof(pixel_t);
	for (int y = 0; y < img->height; y++)
		memset(pixels + pitch*y, 0, img->bpl);
}

void clear_image(GdkImage* img)
{
    if (img->depth == 16)
        _clear_image<depth16_t>(img);
    else
        _clear_image<depth24_t>(img);
}

inline
void to_pixel(depth16_t *pixel, uint16_t c)
{
	*pixel = (c>>3) | (c>>2)<<5 | (c>>3)<<11;
}

inline
void to_pixel(depth24_t *pixel, uint16_t c)
{
    depth24_t p = 0xff & c;
	*pixel = p | p<<8 | p<<16;
}

template <typename pixel_t> inline
void _draw_point_2x(GdkImage* img, int x, int y, uint16_t c)
{
	if (x < 0 || y < 0 || x >= img->width/2-1 || y >= img->height/2-1)
		return;

	pixel_t* pixels = (pixel_t*)img->mem;
	int pitch = img->bpl/sizeof(pixel_t);
	int ofs = pitch*y*2+x*2;

	pixel_t pix;
    to_pixel(&pix, c);

	pixels[ofs] = pix;
	pixels[ofs+1] = pix;
	pixels[ofs+pitch] = pix;
	pixels[ofs+pitch+1] = pix;
}

void draw_point_2x(GdkImage* img, int x, int y, uint16_t c)
{
    if (img->depth == 16)
        _draw_point_2x<depth16_t>(img, x, y, c);
    else
        _draw_point_2x<depth24_t>(img, x, y, c);
}

void draw_line_2x(GdkImage* img, int x0, int y0, int x1, int y1, int color)
{
	// Make sure the line runs top to bottom.
	if (y0 > y1) 
	{
		int ty = y0; y0 = y1; y1 = ty;
		int tx = x0; x0 = x1; x1 = tx;
	}

	// Draw the initial pixel, which is always exactly intersected by the line and so needs no weighting.
	draw_point_2x(img, x0, y0, color);
	
	int dx = x1 - x0;
	int xdir;
	if (dx >= 0)
		xdir = 1;
	else 
	{
		xdir = -1;
		dx = -dx; // make dx positive.
	}
	
	int dy = y1 - y0;
	if (dy == 0) // Horizontal line
	{
		while (dx-- != 0) 
		{
			x0 += xdir;
			draw_point_2x(img, x0, y0, color);
		}
	}
	else if (dx == 0) // Vertical line
	{
		do 
		{
			y0++;
			draw_point_2x(img, x0, y0, color);
		} while (--dy != 0);
	}
	else if (dx == dy) // Diagonal line
	{
		do 
		{
			x0 += xdir;
			y0++;
			draw_point_2x(img, x0, y0, color);
		} while (--dy != 0);
	}
	else // Line is not horizontal, diagonal, or vertical.
	{
		// Initialize the line error accumulator to 0 
		uint16_t ErrorAcc = 0;  
		
		// # of bits by which to shift ErrorAcc to get intensity level 
		uint16_t IntensityShift = 16 - 8;
		
		// Mask used to flip all bits in an intensity weighting, producing the result (1 - intensity weighting) 
		uint16_t WeightingComplementMask = 256 - 1;
		
		// Is this an X-major or Y-major line?
		if (dy > dx) 
		{
			// Y-major line; calculate 16-bit fixed-point fractional part of a pixel that X advances each time Y advances 
			// 1 pixel, truncating the result so that we won't overrun the endpoint along the X axis
			uint16_t ErrorAdj = ((unsigned long) dx << 16) / (unsigned long) dy;
			// Draw all pixels other than the first and last
			while (--dy) 
			{
				uint16_t ErrorAccTemp = ErrorAcc;   /* remember currrent accumulated error */
				ErrorAcc += ErrorAdj;      /* calculate error for next pixel */
				if (ErrorAcc <= ErrorAccTemp) 
				{
					// The error accumulator turned over, so advance the X coord
					x0 += xdir;
				}
				y0++; // Y-major, so always advance Y
				// The IntensityBits most significant bits of ErrorAcc give us the intensity weighting for this pixel, and the 
				// complement of the weighting for the paired pixel
				uint16_t Weighting = ErrorAcc >> IntensityShift;
				//draw_point_2x(img, x0, y0, (color * Weighting) >> 8);
				//draw_point_2x(img, x0 + xdir, y0, (color * (Weighting ^ WeightingComplementMask)) >> 8);
				draw_point_2x(img, x0, y0, color);
			}
			// Draw the final pixel, which is always exactly intersected by the line and so needs no weighting
			draw_point_2x(img, x1, y1, color);
		}
		else
		{
			// It's an X-major line; calculate 16-bit fixed-point fractional part of a pixel that Y advances each time X 
			// advances 1 pixel, truncating the result to avoid overrunning the endpoint along the X axis
			uint16_t ErrorAdj = ((unsigned long) dy << 16) / (unsigned long) dx;
			// Draw all pixels other than the first and last
			while (--dx) 
			{
				uint16_t ErrorAccTemp = ErrorAcc;   // remember currrent accumulated error
				ErrorAcc += ErrorAdj;      // calculate error for next pixel
				if (ErrorAcc <= ErrorAccTemp) 
				{
					// The error accumulator turned over, so advance the Y coord
					y0++;
				}
				x0 += xdir; // X-major, so always advance X 
				// The IntensityBits most significant bits of ErrorAcc give us the intensity weighting for this pixel, and the 
				// complement of the weighting for the paired pixel
				uint16_t Weighting = ErrorAcc >> IntensityShift;
				//draw_point_2x(img, x0, y0, (color * Weighting) >> 8);
				//draw_point_2x(img, x0, y0 + 1, (color * (Weighting ^ WeightingComplementMask)) >> 8);
				draw_point_2x(img, x0, y0, color);
			}
			// Draw the final pixel, which is always exactly intersected by the line and so needs no weighting
			draw_point_2x(img, x1, y1, color);
		}
	}
}

void draw_ellipse_2x(GdkImage* img, int x, int y, int rx, int ry, int color)
{
	if (rx==0 && ry==0) // Special case - draw a single pixel 
	{  
		draw_point_2x(img, x, y, color);
		return;
	}
	if (rx==0)  // Special case for rx=0 - draw a vline
	{ 
		draw_line_2x(img, x, y-ry, x, y+ry, color);
		return;
	}
	if (ry==0) // Special case for ry=0 - draw a hline
	{ 
		draw_line_2x(img, x-rx, y, x+rx, y, color);
		return;
	}

	// Draw
	int oh = 0xffff;
	int oi = 0xffff;
	int oj = 0xffff;
	int ok = 0xffff;

	if (rx >= ry) 
	{
		int ix = 0;
		int iy = rx * 64;
		int i, h;
		do 
		{
			h = (ix + 8) >> 6;
			i = (iy + 8) >> 6;
			int j = (h * ry) / rx;
			int k = (i * ry) / rx;
			if (((ok != k) && (oj != k)) || ((oj != j) && (ok != j)) || (k != j)) 
			{
				int xph = x+h-1;
				int xmh = x-h;
				if (k > 0) 
				{
					int ypk=y+k-1;
					int ymk=y-k;
					if (h > 0) 
					{
						draw_point_2x(img, xmh, ypk, color);
						draw_point_2x(img, xmh, ymk, color);
					}
					draw_point_2x(img, xph, ypk, color);
					draw_point_2x(img, xph, ymk, color);
				}
				ok = k;
				int xpi = x+i-1;
				int xmi = x-i;
				if (j > 0) 
				{
					int ypj = y+j-1;
					int ymj = y-j;
					draw_point_2x(img, xmi, ypj, color);
					draw_point_2x(img, xpi, ypj, color);
					draw_point_2x(img, xmi, ymj, color);
					draw_point_2x(img, xpi, ymj, color);
				}
				oj = j;
			}
			ix = ix + iy / rx;
			iy = iy - ix / rx;
		} while (i > h);
	} 
	else 
	{
		int ix = 0;
		int iy = ry * 64;
		int i, h;
		do 
		{
			h = (ix + 8) >> 6;
			i = (iy + 8) >> 6;
			int j = (h * rx) / ry;
			int k = (i * rx) / ry;
			if (((oi != i) && (oh != i)) || ((oh != h) && (oi != h) && (i != h))) 
			{
				int xmj = x-j;
				int xpj = x+j-1;
				if (i > 0) 
				{
					int ypi = y+i-1;
					int ymi = y-i;
					if (j > 0) 
					{
						draw_point_2x(img, xmj, ypi, color);
						draw_point_2x(img, xmj, ymi, color);
					}
					draw_point_2x(img, xpj, ypi, color);
					draw_point_2x(img, xpj, ymi, color);
				}
				oi = i;
				int xmk = x-k;
				int xpk = x+k-1;
				if (h > 0) 
				{
					int yph = y+h-1;
					int ymh = y-h;
					draw_point_2x(img, xmk, yph, color);
					draw_point_2x(img, xpk, yph, color);
					draw_point_2x(img, xmk, ymh, color);
					draw_point_2x(img, xpk, ymh, color);
				}
				oh = h;
			}
			ix = ix + iy / ry;
			iy = iy - ix / ry;
		} while (i > h);
	}
}

void fill_ellipse_2x(GdkImage* img, int x, int y, int rx, int ry, int color)
{
	if (rx==0 && ry==0) // Special case - draw a single pixel 
	{  
		draw_point_2x(img, x, y, color);
		return;
	}
	if (rx==0)  // Special case for rx=0 - draw a vline
	{ 
		draw_line_2x(img, x, y-ry, x, y+ry, color);
		return;
	}
	if (ry==0) // Special case for ry=0 - draw a hline
	{ 
		draw_line_2x(img, x-rx, y, x+rx, y, color);
		return;
	}

	// Draw
	int oh = 0xffff;
	int oi = 0xffff;
	int oj = 0xffff;
	int ok = 0xffff;

	if (rx >= ry) 
	{
		int ix = 0;
		int iy = rx * 64;
		int i, h;
		do 
		{
			h = (ix + 8) >> 6;
			i = (iy + 8) >> 6;
			int j = (h * ry) / rx;
			int k = (i * ry) / rx;
			if ((ok != k) && (oj != k) && (k < ry)) 
			{
				draw_line_2x(img, x-h, y-k-1, x+h-1, y-k-1, color);
				draw_line_2x(img, x-h, y+k, x+h-1, y+k, color);
				ok = k;
			}
			if ((oj != j) && (ok != j) && (k != j))  
			{
				draw_line_2x(img, x-i, y+j, x+i-1, y+j, color);
				draw_line_2x(img, x-i, y-j-1, x+i-1, y-j-1, color);
				oj = j;
			}
			ix = ix + iy / rx;
			iy = iy - ix / rx;
		} while (i > h);
	} 
	else 
	{
		int ix = 0;
		int iy = ry * 64;
		int i, h;
		do 
		{
			h = (ix + 8) >> 6;
			i = (iy + 8) >> 6;
			int j = (h * rx) / ry;
			int k = (i * rx) / ry;
			if ((oi != i) && (oh != i) && (i < ry)) 
			{
				draw_line_2x(img, x-j, y+i, x+j-1, y+i, color);
				draw_line_2x(img, x-j, y-i-1, x+j-1, y-i-1, color);
				oi = i;
			}
			if ((oh != h) && (oi != h) && (i != h)) 
			{
				draw_line_2x(img, x-k, y+h, x+k-1, y+h, color);
				draw_line_2x(img, x-k, y-h-1, x+k-1, y-h-1, color);
				oh = h;
			}
			ix = ix + iy / ry;
			iy = iy - ix / ry;
		} while (i > h);
	}
}

int actual_screen_width = 1200;
int actual_screen_height = 825;

int viewport_scale = to_fixed(100);

void set_3d_params(int w, int h, int s)
{
	actual_screen_width = w;
	actual_screen_height = h;
	viewport_scale = s;
}

int to_fixed(int x)
{
	return x<<8;
}

int project_x(int x, int y, int z)
{
    return (to_fixed(50) + ( x - to_fixed(50) ) * viewport_scale / ( z + viewport_scale )) * actual_screen_width/100 / 256;
}

int project_y(int x, int y, int z)
{
    return (to_fixed(50) + ( y - to_fixed(50) ) * viewport_scale / ( z + viewport_scale )) * actual_screen_height/100 / 256;
}

void draw_line_3d(GdkImage* img, int x0, int y0, int z0, int x1, int y1, int z1, float c)
{
    x0 = project_x(x0, y0, z0)/2;
    y0 = project_y(x0, y0, z0)/2;
    x1 = project_x(x1, y1, z1)/2;
    y1 = project_y(x1, y1, z1)/2;

    draw_line_2x(img, x0, y0, x1, y1, int(c*255.0));
}

void draw_rect_3d(GdkImage* img, int x0, int y0, int x1, int y1, int depth, float c)
{
    x0 = (project_x(x0, y0, depth) + 1)/2;
    y0 = (project_y(x0, y0, depth) + 1)/2;
    x1 = (project_x(x1, y1, depth) - 1)/2;
    y1 = (project_y(x1, y1, depth) - 1)/2;

    draw_line_2x(img, x0, y0, x1, y0, int(c*255.0));
    draw_line_2x(img, x1, y0, x1, y1, int(c*255.0));
    draw_line_2x(img, x1, y1, x0, y1, int(c*255.0));
    draw_line_2x(img, x0, y1, x0, y0, int(c*255.0));
}

void draw_circle_3d(GdkImage* img, int x, int y, int z, int radius, float c)
{
    int r = (project_x(x+radius, y, z)-project_x(x, y, z))/2;
    if (r < 1) return;

    x = project_x(x, y, z)/2;
    y = project_y(x, y, z)/2;

    draw_ellipse_2x(img, x, y, r, r, int(c*255.0));
}

void fill_circle_3d(GdkImage* img, int x, int y, int z, int radius, float c)
{
    int r = (project_x(x+radius, y, z)-project_x(x, y, z))/2;
	if (r < 1) return;

    x = project_x(x, y, z)/2;
    y = project_y(x, y, z)/2;

    fill_ellipse_2x(img, x, y, r, r, int(c*255.0));
}

void draw_ellipse_3d(GdkImage* img, int x, int y, int z, int rx, int ry, float c)
{
    rx = (project_x(x+rx, y, z)-project_x(x, y, z))/2;
    ry = (project_y(x, y+ry, z)-project_y(x, y, z))/2;
    if (rx < 1 || ry < 1) return;

    x = project_x(x, y, z)/2;
    y = project_y(x, y, z)/2;

    draw_ellipse_2x(img, x, y, rx, ry, int(c*255.0));
}

