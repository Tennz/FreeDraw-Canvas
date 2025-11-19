import tkinter as tk
from tkinter import filedialog, colorchooser
import ttkbootstrap as tb
from ttkbootstrap.constants import *

style = tb.Style(theme="darkly")
root = style.master
root.title("DrawPad")
root.geometry("1000x900")
root.configure(bg="#1f1f1f")

brush_color = "black"
brush_size = 5
eraser_size = 10
drawing = False
using_eraser = False
last_x, last_y = None, None

strokes = []
redo_strokes = []
current_stroke = []

zoom_level = 1.0
zoom_factor = 1.1

main_frame = tb.Frame(root, bootstyle="secondary", padding=8)
main_frame.pack(fill=tk.BOTH, expand=True)

canvas_frame = tb.Frame(main_frame, padding=(10, 10), bootstyle="secondary")
canvas_frame.pack(fill=tk.BOTH, expand=True)

h_scroll = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
v_scroll = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL)

canvas = tk.Canvas(
    canvas_frame,
    bg="white",
    width=900,
    height=550,
    xscrollcommand=h_scroll.set,
    yscrollcommand=v_scroll.set,
    highlightthickness=0
)

h_scroll.config(command=canvas.xview)
v_scroll.config(command=canvas.yview)

h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
canvas.pack(fill=tk.BOTH, expand=True)

cursor_circle = None

def draw_cursor_circle(event):
    global cursor_circle
    if cursor_circle:
        canvas.delete(cursor_circle)

    size = eraser_size if using_eraser else brush_size
    x, y = canvas.canvasx(event.x), canvas.canvasy(event.y)

    cursor_circle = canvas.create_oval(
        x - size/2, y - size/2,
        x + size/2, y + size/2,
        outline="#777"
    )

def start_draw(event):
    global drawing, last_x, last_y, current_stroke
    drawing = True
    last_x = canvas.canvasx(event.x)
    last_y = canvas.canvasy(event.y)
    current_stroke = []

def draw(event):
    global last_x, last_y, current_stroke
    if not drawing:
        draw_cursor_circle(event)
        return

    x = canvas.canvasx(event.x)
    y = canvas.canvasy(event.y)
    size = eraser_size if using_eraser else brush_size
    color = canvas["bg"] if using_eraser else brush_color

    line_id = canvas.create_line(
        last_x, last_y, x, y,
        width=size, fill=color,
        capstyle=tk.ROUND, smooth=True
    )

    coords = canvas.coords(line_id)
    current_stroke.append((line_id, coords, color, size))

    last_x, last_y = x, y
    draw_cursor_circle(event)

def stop_draw(event):
    global drawing, strokes, redo_strokes, current_stroke
    if drawing:
        drawing = False
        if current_stroke:
            strokes.append(current_stroke)
            current_stroke = []
        redo_strokes.clear()

def undo():
    if strokes:
        stroke = strokes.pop()
        for obj_id, *_ in stroke:
            canvas.delete(obj_id)
        redo_strokes.append(stroke)

def redo():
    if redo_strokes:
        stroke = redo_strokes.pop()
        new_objs = []
        for _, coords, color, size in stroke:
            new_id = canvas.create_line(*coords, width=size, fill=color, capstyle=tk.ROUND, smooth=True)
            new_objs.append((new_id, canvas.coords(new_id), color, size))
        strokes.append(new_objs)
def set_color():
    global brush_color, using_eraser
    using_eraser = False
    color = colorchooser.askcolor()[1]
    if color:
        brush_color = color

def use_eraser():
    global using_eraser
    using_eraser = True

def set_brush_size(val):
    global brush_size
    brush_size = int(float(val))   

def set_eraser_size(val):
    global eraser_size
    eraser_size = int(float(val))  

def clear_canvas():
    for stroke in strokes:
        for obj_id, *_ in stroke:
            canvas.delete(obj_id)
    strokes.clear()
    redo_strokes.clear()

def save_canvas():
    file = filedialog.asksaveasfilename(
        defaultextension=".png",
        filetypes=[("PNG files", "*.png"), ("PostScript", "*.ps")]
    )
    if not file:
        return

    canvas.postscript(file=file, colormode='color')
def zoom_windows(event):
    if event.state & 0x0004:  # Ctrl key
        scale = zoom_factor if event.delta > 0 else 1 / zoom_factor
        canvas.scale("all", canvas.canvasx(event.x), canvas.canvasy(event.y), scale, scale)
        canvas.configure(scrollregion=canvas.bbox("all"))

toolbar_container = tb.Frame(root, bootstyle="secondary", padding=8)
toolbar_container.pack(fill=tk.X, side=tk.BOTTOM, padx=12, pady=(6, 12))

inner = tb.Frame(toolbar_container, bootstyle="light", padding=6)
inner.pack(fill=tk.X, padx=6)

btn_group = tb.Frame(inner)
btn_group.pack(side=tk.LEFT, padx=10, pady=6)

btn_opts = {"bootstyle": "dark", "width": 12}

tb.Button(btn_group, text="Color", command=set_color, **btn_opts).grid(row=0, column=0, padx=4)
tb.Button(btn_group, text="Eraser", command=use_eraser, **btn_opts).grid(row=0, column=1, padx=4)
tb.Button(btn_group, text="Undo", command=undo, **btn_opts).grid(row=0, column=2, padx=4)
tb.Button(btn_group, text="Redo", command=redo, **btn_opts).grid(row=0, column=3, padx=4)
tb.Button(btn_group, text="Clear", command=clear_canvas, **btn_opts).grid(row=0, column=4, padx=4)
tb.Button(btn_group, text="Save", command=save_canvas, **btn_opts).grid(row=0, column=5, padx=4)

slider_box = tb.Frame(inner, bootstyle="secondary")
slider_box.pack(side=tk.RIGHT, padx=8)

tb.Label(slider_box, text="Brush Size", bootstyle="inverse").pack(anchor="e")
brush_slider = tb.Scale(slider_box, from_=1, to=20, orient=tk.HORIZONTAL, command=set_brush_size, bootstyle="info", length=180)
brush_slider.set(brush_size)
brush_slider.pack(pady=4)

tb.Label(slider_box, text="Eraser Size", bootstyle="inverse").pack(anchor="e")
eraser_slider = tb.Scale(slider_box, from_=1, to=50, orient=tk.HORIZONTAL, command=set_eraser_size, bootstyle="info", length=180)
eraser_slider.set(eraser_size)
eraser_slider.pack(pady=4)

canvas.bind("<Button-1>", start_draw)
canvas.bind("<B1-Motion>", draw)
canvas.bind("<ButtonRelease-1>", stop_draw)
canvas.bind("<Motion>", draw_cursor_circle)

canvas.bind_all("<MouseWheel>", zoom_windows)

canvas.configure(scrollregion=(0, 0, 1000, 700))
root.mainloop()