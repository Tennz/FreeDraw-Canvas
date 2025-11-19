import tkinter as tk
from tkinter import filedialog, colorchooser
import ttkbootstrap as tb
from ttkbootstrap.constants import *

# =============================================================================
# APP WINDOW SETUP
# =============================================================================
# This section initializes the application window using ttkbootstrap's 'darkly'
# theme so the look matches the design you requested. Variables declared here
# are global state used across the functions below (brush size, current color,
# eraser flag, stroke history, etc.).
#
# Important globals and what they represent:
# - brush_color (str): current drawing color used when not erasing.
# - brush_size (int): current brush width in pixels.
# - eraser_size (int): current eraser width in pixels.
# - drawing (bool): True while the left mouse button is down and the user is drawing.
# - using_eraser (bool): True when the Eraser tool is active — draw() uses canvas bg color.
# - last_x, last_y (floats): last canvas coordinates to continue the line from.
# - strokes (list): history stack of strokes. Each stroke is a list of tuples:
#       (obj_id, coords, color, size)
#   This lets undo/redo remove/recreate using stored coords (not relying on deleted ids).
# - redo_strokes (list): stack for redo; popped when user hits Redo.
# - current_stroke (list): the stroke currently being drawn (list of segments).
#
# We keep these as module-level globals so functions bound to UI widgets can
# access and modify them without object-wrapping the entire app.
style = tb.Style(theme="darkly")
root = style.master
root.title("FreeDraw Canvas")
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

# =============================================================================
# CANVAS AREA (layout + scrollbars)
# =============================================================================
# This section creates the canvas and scrollbars and places them in the main
# layout.  The canvas is the drawing surface; canvas.create_line() is used to
# draw freehand strokes. We attach scrollbars via xscrollcommand and yscrollcommand.
#
# Layout connections:
# - main_frame -> a container for the canvas_frame
# - canvas_frame -> hosts the canvas and the scrollbars
# - canvas -> used by all drawing functions (create_line, coords, delete)
#
# The canvas background color ("white") is used as the eraser color when the
# eraser is active (using_eraser==True). This means erasing is implemented by
# drawing lines with the canvas background color.
main_frame = tb.Frame(root, bootstyle="secondary", padding=8)
main_frame.pack(fill=tk.BOTH, expand=True)

canvas_frame = tb.Frame(main_frame, padding=(10, 10), bootstyle="secondary")
canvas_frame.pack(fill=tk.BOTH, expand=True)

h_scroll = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
v_scroll = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL)

canvas = tk.Canvas(
    canvas_frame,
    bg="white",         # canvas background used for eraser color
    width=900,
    height=550,
    xscrollcommand=h_scroll.set,
    yscrollcommand=v_scroll.set,
    highlightthickness=0
)

# Connect scrollbars to the canvas view functions
h_scroll.config(command=canvas.xview)
v_scroll.config(command=canvas.yview)

# Pack scrollbars and canvas into the frame
h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
canvas.pack(fill=tk.BOTH, expand=True)

cursor_circle = None  # will hold the temporary oval id used as a cursor preview

# =============================================================================
# DRAWING FUNCTIONS
# =============================================================================
# The following functions implement drawing behavior. These map directly to
# canvas events (mouse press, motion, release). The toolbar buttons call
# certain of these helper functions (set_color/use_eraser/undo/redo/etc.).
#
# Event → function mapping (at bottom of file in BINDINGS):
# - canvas.bind("<Button-1>", start_draw)       -> calls start_draw when user clicks
# - canvas.bind("<B1-Motion>", draw)            -> calls draw while dragging
# - canvas.bind("<ButtonRelease-1>", stop_draw) -> calls stop_draw when released
# - canvas.bind("<Motion>", draw_cursor_circle) -> updates cursor preview
#
# Data flow while drawing:
# 1. start_draw sets drawing=True and records last_x/last_y.
# 2. draw() is called repeatedly; it creates a short line segment between
#    last and current points, stores the object's id and coords in
#    current_stroke, updates last_x/last_y, and shows the cursor circle.
# 3. stop_draw() finalizes the current_stroke into strokes[] and clears redo stack.
#
# Stroke storage format:
#   current_stroke: [ (line_id, coords, color, size), ... ]
#   strokes: list of current_stroke snapshots
#
# This format allows undo/redo to reconstruct strokes using coords without
# depending on object ids that may have been deleted.
def draw_cursor_circle(event):
    """
    Called on mouse motion to draw a preview circle showing the current
    brush/eraser size. The preview follows the mouse and is removed/updated
    every motion event.
    - Takes the event.x/event.y (widget coords), converts them to canvas coords
      with canvas.canvasx/canvas.canvasy, and draws a small oval.
    - Uses global cursor_circle to track and delete the previous preview.
    """
    global cursor_circle
    if cursor_circle:
        canvas.delete(cursor_circle)

    size = eraser_size if using_eraser else brush_size
    x, y = canvas.canvasx(event.x), canvas.canvasy(event.y)

    cursor_circle = canvas.create_oval(
        x - size / 2, y - size / 2,
        x + size / 2, y + size / 2,
        outline="#777"
    )

def start_draw(event):
    """
    Bound to <Button-1> (left mouse down).
    Sets drawing flag True, records the start coordinates (last_x, last_y),
    and initializes current_stroke list which collects all segments of the
    stroke until mouse release.
    """
    global drawing, last_x, last_y, current_stroke
    drawing = True
    last_x = canvas.canvasx(event.x)
    last_y = canvas.canvasy(event.y)
    current_stroke = []

def draw(event):
    """
    Bound to <B1-Motion> (mouse dragged with left button down).
    Creates a short line segment between last_x,last_y and current mouse
    position and appends its id + metadata to current_stroke.
    Also updates last_x,last_y, and refreshes the cursor circle preview.

    Important: If drawing == False, draw() only updates cursor preview and
    returns (no accidental drawing when not pressing button).
    """
    global last_x, last_y, current_stroke
    if not drawing:
        draw_cursor_circle(event)
        return

    x = canvas.canvasx(event.x)
    y = canvas.canvasy(event.y)
    size = eraser_size if using_eraser else brush_size
    # When using eraser, color is canvas background -> simulate erasing by over-drawing
    color = canvas["bg"] if using_eraser else brush_color

    # Create the visible line segment on the canvas
    line_id = canvas.create_line(
        last_x, last_y, x, y,
        width=size, fill=color,
        capstyle=tk.ROUND, smooth=True
    )

    # Immediately capture its coords (so redos can later re-create it)
    coords = canvas.coords(line_id)
    # Append metadata to current_stroke
    current_stroke.append((line_id, coords, color, size))

    # Update last positions for the next segment
    last_x, last_y = x, y
    # Update cursor preview as well
    draw_cursor_circle(event)

def stop_draw(event):
    """
    Bound to <ButtonRelease-1>. Finalizes a stroke:
    - Sets drawing flag False
    - If current_stroke contains segments, append it to strokes stack
      and reset current_stroke.
    - Clears redo_strokes because a new action invalidates the redo history.
    """
    global drawing, strokes, redo_strokes, current_stroke
    if drawing:
        drawing = False
        if current_stroke:
            strokes.append(current_stroke)
            current_stroke = []
        redo_strokes.clear()

def undo():
    """
    Triggered by the Undo toolbar button.
    Behavior:
    - Pops the last stroke from strokes (if any).
    - Deletes each canvas object that belongs to that stroke.
    - Appends the stroke to redo_strokes so Redo can restore it later.
    Note: We delete using stored object ids. The objects are removed from canvas
    so their ids are no longer valid after deletion — that is why we store coords
    too: redo uses coords to recreate shapes.
    """
    if strokes:
        stroke = strokes.pop()
        for obj_id, *_ in stroke:
            canvas.delete(obj_id)
        redo_strokes.append(stroke)

def redo():
    """
    Triggered by the Redo toolbar button.
    Behavior:
    - Pops a stroke from redo_strokes.
    - Recreates each segment using stored coords, color, and size.
    - Appends the recreated stroke to strokes stack.
    Implementation note:
    - We do not rely on old object ids (they were deleted on undo).
    - We use stored coords to create new objects and capture their new ids.
    """
    if redo_strokes:
        stroke = redo_strokes.pop()
        new_objs = []
        for _, coords, color, size in stroke:
            new_id = canvas.create_line(*coords, width=size, fill=color, capstyle=tk.ROUND, smooth=True)
            # store the new id + its coords (canvas.coords(new_id) ensures we have accurate coords)
            new_objs.append((new_id, canvas.coords(new_id), color, size))
        strokes.append(new_objs)

# =============================================================================
# TOOL FUNCTIONS (buttons / sliders)
# =============================================================================
# These functions are called by toolbar widgets defined later in the file.
# They mutate the global state used by the drawing functions above.
#
# Connections:
# - set_color() -> Color button (opens colorchooser)
# - use_eraser() -> Eraser button (sets using_eraser True)
# - set_brush_size() -> brush_slider (Scale widget). The Scale calls this
#       function repeatedly and passes string/float-like values, so we convert.
# - set_eraser_size() -> eraser_slider (Scale widget)
#
# Note on sliders: Tkinter Scale sometimes passes float-like strings; calling
# int(float(val)) prevents errors like "invalid literal for int()".
def set_color():
    """
    Opens a color chooser and sets the brush_color variable. Also ensures
    we exit eraser mode (using_eraser=False) so new lines will be colored.
    """
    global brush_color, using_eraser
    using_eraser = False
    color = colorchooser.askcolor()[1]
    if color:
        brush_color = color

def use_eraser():
    """
    Sets the eraser mode. Drawing uses canvas background color when this flag
    is True. This function is bound to the Eraser toolbar button.
    """
    global using_eraser
    using_eraser = True

def set_brush_size(val):
    """
    Called by the Brush Size Scale widget when the slider moves.
    Converts the incoming value safely to an integer and stores it to brush_size.
    The incoming 'val' can be a float-like string (depending on platform),
    so int(float(val)) is more robust than int(val).
    """
    global brush_size
    brush_size = int(float(val))   # FIXED ERROR: prevents ValueError on float-like strings

def set_eraser_size(val):
    """
    Called by the Eraser Size Scale widget. Works the same as set_brush_size,
    storing the integer eraser size used during drawing when using_eraser is True.
    """
    global eraser_size
    eraser_size = int(float(val))  # FIXED ERROR

def clear_canvas():
    """
    Clears all drawn content by deleting every object created for every stroke.
    Resets the strokes and redo_strokes stacks.
    """
    for stroke in strokes:
        for obj_id, *_ in stroke:
            try:
                canvas.delete(obj_id)
            except Exception:
                pass
    strokes.clear()
    redo_strokes.clear()

def save_canvas():
    """
    Opens a file dialog and saves the canvas contents. Implementation:
    - We call canvas.postscript(file=...), which writes a PostScript file.
    - The dialog allows choosing .png or .ps; here we always write PS using
      the provided filename. Converting PS -> PNG without external libraries
      is platform-dependent; previously we offered PIL-based conversion,
      but this function currently writes the PS output.
    """
    file = filedialog.asksaveasfilename(
        defaultextension=".png",
        filetypes=[("PNG files", "*.png"), ("PostScript", "*.ps")]
    )
    if not file:
        return

    canvas.postscript(file=file, colormode='color')

# =============================================================================
# ZOOM (Windows-only implementation)
# =============================================================================
# This section implements Ctrl+MouseWheel zoom behavior for Windows/macOS via
# the <MouseWheel> event. The event.delta value is positive (wheel up) or
# negative (wheel down), generally in multiples of 120 on Windows. We check
# for the Ctrl key being held via event.state & 0x0004, then apply a scaling
# transform to everything on the canvas via canvas.scale(...).
#
# The code updates the canvas scrollregion so the scrollbar track reflects the
# new scaled extents.
def zoom_windows(event):
    """
    Bound to <MouseWheel> (via canvas.bind_all below).
    When Ctrl is held (event.state & 0x0004), compute scale and apply zoom.
    The zoom pivot is at the current mouse location (event.x/event.y).
    """
    if event.state & 0x0004:  # Ctrl key
        scale = zoom_factor if event.delta > 0 else 1 / zoom_factor
        canvas.scale("all", canvas.canvasx(event.x), canvas.canvasy(event.y), scale, scale)
        canvas.configure(scrollregion=canvas.bbox("all"))

# =============================================================================
# TOOLBAR UI (placement + widget to function connections)
# =============================================================================
# The toolbar layout replicates the appearance in your screenshot:
# - toolbar_container -> bottom full-width rounded bar
# - inner -> the inner area that holds button group and slider box
# - btn_group -> left-aligned group of dark rounded buttons
# - slider_box -> right-aligned vertical group for Brush and Eraser sliders
#
# Each Button maps to a function defined above:
# - Color -> set_color
# - Eraser -> use_eraser
# - Undo -> undo
# - Redo -> redo
# - Clear -> clear_canvas
# - Save -> save_canvas
#
# Slider connections:
# - brush_slider command -> set_brush_size(val)
# - eraser_slider command -> set_eraser_size(val)
#
# Important UI wiring: moving a slider triggers set_brush_size or set_eraser_size,
# which updates brush_size/eraser_size used in draw() immediately.
toolbar_container = tb.Frame(root, bootstyle="secondary", padding=8)
toolbar_container.pack(fill=tk.X, side=tk.BOTTOM, padx=12, pady=(6, 12))

inner = tb.Frame(toolbar_container, bootstyle="light", padding=6)
inner.pack(fill=tk.X, padx=6)

btn_group = tb.Frame(inner)
btn_group.pack(side=tk.LEFT, padx=10, pady=6)

btn_opts = {"bootstyle": "dark", "width": 12}

# Buttons (each button calls the function named in 'command=')
tb.Button(btn_group, text="Color", command=set_color, **btn_opts).grid(row=0, column=0, padx=4)
tb.Button(btn_group, text="Eraser", command=use_eraser, **btn_opts).grid(row=0, column=1, padx=4)
tb.Button(btn_group, text="Undo", command=undo, **btn_opts).grid(row=0, column=2, padx=4)
tb.Button(btn_group, text="Redo", command=redo, **btn_opts).grid(row=0, column=3, padx=4)
tb.Button(btn_group, text="Clear", command=clear_canvas, **btn_opts).grid(row=0, column=4, padx=4)
tb.Button(btn_group, text="Save", command=save_canvas, **btn_opts).grid(row=0, column=5, padx=4)

# Slider box on the right holds the two Scale widgets bound to set_* functions
slider_box = tb.Frame(inner, bootstyle="secondary")
slider_box.pack(side=tk.RIGHT, padx=8)

tb.Label(slider_box, text="Brush Size", bootstyle="inverse").pack(anchor="e")
brush_slider = tb.Scale(
    slider_box,
    from_=1,
    to=20,
    orient=tk.HORIZONTAL,
    command=set_brush_size,   # when slider moves, set_brush_size(val) is called
    bootstyle='info',
    length=180
)
brush_slider.set(brush_size)
brush_slider.pack(pady=4)

tb.Label(slider_box, text="Eraser Size", bootstyle="inverse").pack(anchor="e")
eraser_slider = tb.Scale(
    slider_box,
    from_=1,
    to=50,
    orient=tk.HORIZONTAL,
    command=set_eraser_size,   # when slider moves, set_eraser_size(val) is called
    bootstyle='info',
    length=180
)
eraser_slider.set(eraser_size)
eraser_slider.pack(pady=4)

# =============================================================================
# BINDINGS (connect canvas events to functions)
# =============================================================================
# This block wires the canvas events to the functions described above.
# Event mapping summary (repeated here for clarity):
# - <Button-1>         -> start_draw   (start a stroke)
# - <B1-Motion>        -> draw         (append segments to stroke)
# - <ButtonRelease-1>  -> stop_draw    (finalize the stroke)
# - <Motion>           -> draw_cursor_circle (update preview circle)
# - <MouseWheel>       -> zoom_windows (Ctrl+scroll zoom on Windows)
#
# Note: canvas.bind_all("<MouseWheel>", zoom_windows) uses a global binding so
# that the Ctrl+scroll is captured even if the mouse momentarily leaves the
# canvas widget (this is conventional for canvas zoom behavior).
canvas.bind("<Button-1>", start_draw)
canvas.bind("<B1-Motion>", draw)
canvas.bind("<ButtonRelease-1>", stop_draw)
canvas.bind("<Motion>", draw_cursor_circle)

# Windows scroll zoom only (captures mouse wheel + Ctrl for zoom)
canvas.bind_all("<MouseWheel>", zoom_windows)

# initialize scroll region of the canvas so scrollbars know the extents initially
canvas.configure(scrollregion=(0, 0, 1000, 700))

# =============================================================================
# START THE TKINTER MAIN LOOP
# =============================================================================
# The application will run until the user closes the window. All event-driven
# behavior described above will be invoked through user actions (mouse, slider,
# and button interactions).
if __name__ == "__main__":
    root.mainloop()
