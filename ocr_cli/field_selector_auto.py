# -*- coding: utf-8 -*-
"""Interactive field region selector with auto-detected table lines.

Usage:
    python field_selector_auto.py [--template small|medium] [--output regions.json]

Features:
    - Auto-detect table lines from blank template using OpenCV
    - User confirms/adjusts detected lines
    - Name regions from line intersections
    - Export to JSON
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageTk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TEMPLATES = {
    'small': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'small_form_blank.png'),
    'medium': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'medium_form_blank.png'),
}


def detect_table_lines(img_bgr):
    """Detect horizontal and vertical lines in table image."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY_INV, 11, 5)
    
    h, w = bw.shape
    
    # Detect horizontal lines
    horiz = bw.copy()
    horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (w // 30, 1))
    horiz = cv2.morphologyEx(horiz, cv2.MORPH_OPEN, horiz_kernel, iterations=1)
    
    # Detect vertical lines
    vert = bw.copy()
    vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, h // 30))
    vert = cv2.morphologyEx(vert, cv2.MORPH_OPEN, vert_kernel, iterations=1)
    
    # Extract line positions
    h_lines = []
    for y in range(h):
        if np.sum(horiz[y, :]) > w * 0.3 * 255:
            h_lines.append(y)
    
    v_lines = []
    for x in range(w):
        if np.sum(vert[:, x]) > h * 0.3 * 255:
            v_lines.append(x)
    
    # Cluster nearby lines
    h_lines = cluster_lines(h_lines, 10)
    v_lines = cluster_lines(v_lines, 10)
    
    return h_lines, v_lines


def cluster_lines(lines, threshold):
    """Cluster nearby lines into single positions."""
    if not lines:
        return []
    
    clusters = [[lines[0]]]
    for x in lines[1:]:
        if x - clusters[-1][-1] <= threshold:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    
    return [int(np.mean(c)) for c in clusters]


class LineSelector:
    def __init__(self, img_path, output_path):
        self.img_path = img_path
        self.output_path = output_path
        self.fields = {}
        self.v_lines = []
        self.h_lines = []
        
        try:
            from PIL import Image
            pil_img = Image.open(img_path)
            self.img_rgb = np.array(pil_img)
            self.img_bgr = cv2.cvtColor(self.img_rgb, cv2.COLOR_RGB2BGR)
        except Exception as e:
            print('Cannot read', img_path, 'error:', e)
            sys.exit(1)
        
        self.h, self.w = self.img_bgr.shape[:2]
        
        # Auto-detect lines
        print('Detecting table lines...')
        self.h_lines, self.v_lines = detect_table_lines(self.img_bgr)
        print(f'Detected {len(self.h_lines)} horizontal lines, {len(self.v_lines)} vertical lines')
        
        self._setup_gui()
    
    def _setup_gui(self):
        import tkinter as tk
        from tkinter import simpledialog, messagebox
        
        self.root = tk.Tk()
        self.root.title('Table Line Selector - ' + os.path.basename(self.img_path))
        self.root.geometry('1400x800')
        
        # Toolbar
        toolbar = tk.Frame(self.root, relief=tk.RAISED, borderwidth=1)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        
        tk.Label(toolbar, text='Auto-detected table lines. Adjust if needed, then name regions.', padx=10).pack(side=tk.LEFT)
        tk.Button(toolbar, text='Add V Line', command=self._add_v_line, width=12).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text='Add H Line', command=self._add_h_line, width=12).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text='Delete Selected', command=self._delete_selected_line, width=12).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text='Name Regions', command=self._name_regions, width=12).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text='Export JSON', command=self._export, width=12).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text='Quit', command=self._quit, width=12, bg='#ffcccc').pack(side=tk.LEFT, padx=2)
        
        # Main area
        main_frame = tk.Frame(self.root)
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Canvas
        canvas_frame = tk.Frame(main_frame)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        max_w, max_h = 1000, 700
        scale = min(max_w / self.w, max_h / self.h, 1.0)
        disp_w, disp_h = int(self.w * scale), int(self.h * scale)
        self.scale = scale
        
        img_disp = cv2.resize(self.img_bgr, (disp_w, disp_h))
        img_rgb = cv2.cvtColor(img_disp, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        self.photo = ImageTk.PhotoImage(pil_img)
        
        self.canvas = tk.Canvas(canvas_frame, width=disp_w, height=disp_h, bg='gray', cursor='crosshair')
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        self.canvas.image = self.photo
        
        self.canvas.bind('<ButtonPress-1>', self._on_mouse_down)
        self.canvas.bind('<B1-Motion>', self._on_mouse_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_mouse_up)
        
        # Right panel
        right_panel = tk.Frame(main_frame, width=300, bg='#f0f0f0')
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
        
        tk.Label(right_panel, text='Vertical Lines (columns)', font=('Arial', 11, 'bold'), bg='#f0f0f0').pack(pady=(5, 2), anchor=tk.W)
        self.v_listbox = tk.Listbox(right_panel, width=28, height=10, font=('Consolas', 9), selectmode=tk.SINGLE)
        self.v_listbox.pack(fill=tk.X, padx=5, pady=2)
        
        tk.Label(right_panel, text='Horizontal Lines (rows)', font=('Arial', 11, 'bold'), bg='#f0f0f0').pack(pady=(10, 2), anchor=tk.W)
        self.h_listbox = tk.Listbox(right_panel, width=28, height=10, font=('Consolas', 9), selectmode=tk.SINGLE)
        self.h_listbox.pack(fill=tk.X, padx=5, pady=2)
        
        tk.Label(right_panel, text='Regions', font=('Arial', 11, 'bold'), bg='#f0f0f0').pack(pady=(10, 2), anchor=tk.W)
        self.region_listbox = tk.Listbox(right_panel, width=28, height=10, font=('Consolas', 9))
        self.region_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set(f'Ready - Detected {len(self.v_lines)} V lines, {len(self.h_lines)} H lines')
        status_bar = tk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, bg='#e0e0e0')
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Draw initial lines
        self._draw_all_lines()
    
    def _draw_all_lines(self):
        self.canvas.delete('v_line', 'h_line')
        for x in self.v_lines:
            self._draw_v_line(x)
        for y in self.h_lines:
            self._draw_h_line(y)
        self._refresh_line_lists()
    
    def _draw_v_line(self, x):
        cx = int(x * self.scale)
        self.canvas.create_line(cx, 0, cx, self.canvas.winfo_height(), fill='red', width=2, tags='v_line')
        self.canvas.create_text(cx + 3, 5, text=f'x={x}', anchor=tk.NW, fill='red', font=('Arial', 8), tags='v_line')
    
    def _draw_h_line(self, y):
        cy = int(y * self.scale)
        self.canvas.create_line(0, cy, self.canvas.winfo_width(), cy, fill='blue', width=2, tags='h_line')
        self.canvas.create_text(5, cy + 3, text=f'y={y}', anchor=tk.NW, fill='blue', font=('Arial', 8), tags='h_line')
    
    def _refresh_line_lists(self):
        self.v_listbox.delete(0, tk.END)
        for i, x in enumerate(self.v_lines):
            self.v_listbox.insert(tk.END, f'Col {i}: x={x}')
        
        self.h_listbox.delete(0, tk.END)
        for i, y in enumerate(self.h_lines):
            self.h_listbox.insert(tk.END, f'Row {i}: y={y}')
    
    def _canvas_to_image(self, cx, cy):
        return int(cx / self.scale), int(cy / self.scale)
    
    def _on_mouse_down(self, event):
        self.current_start = (event.x, event.y)
    
    def _on_mouse_drag(self, event):
        pass  # No drag preview needed for line addition
    
    def _on_mouse_up(self, event):
        pass  # Lines are added via buttons, not mouse drag
    
    def _add_v_line(self):
        import tkinter as tk
        from tkinter import simpledialog
        x = tk.simpledialog.askinteger('Add Vertical Line', 'X coordinate:', parent=self.root, minvalue=0, maxvalue=self.w)
        if x is not None:
            self.v_lines.append(x)
            self.v_lines.sort()
            self._draw_all_lines()
            self.status_var.set(f'Added vertical line at x={x}')
    
    def _add_h_line(self):
        import tkinter as tk
        from tkinter import simpledialog
        y = tk.simpledialog.askinteger('Add Horizontal Line', 'Y coordinate:', parent=self.root, minvalue=0, maxvalue=self.h)
        if y is not None:
            self.h_lines.append(y)
            self.h_lines.sort()
            self._draw_all_lines()
            self.status_var.set(f'Added horizontal line at y={y}')
    
    def _delete_selected_line(self):
        import tkinter as tk
        from tkinter import messagebox
        
        # Check which listbox has selection
        v_sel = self.v_listbox.curselection()
        h_sel = self.h_listbox.curselection()
        
        if v_sel:
            idx = v_sel[0]
            del self.v_lines[idx]
            self._draw_all_lines()
            self.status_var.set(f'Deleted vertical line {idx}')
        elif h_sel:
            idx = h_sel[0]
            del self.h_lines[idx]
            self._draw_all_lines()
            self.status_var.set(f'Deleted horizontal line {idx}')
        else:
            tk.messagebox.showwarning('Delete', 'Select a line from the list first')
    
    def _name_regions(self):
        import tkinter as tk
        from tkinter import simpledialog
        
        if len(self.v_lines) < 2 or len(self.h_lines) < 2:
            tk.messagebox.showwarning('Name Regions', 'Need at least 2 vertical and 2 horizontal lines')
            return
        
        self.region_listbox.delete(0, tk.END)
        self.fields = {}
        
        v_sorted = sorted(self.v_lines)
        h_sorted = sorted(self.h_lines)
        
        for row_idx in range(len(h_sorted) - 1):
            for col_idx in range(len(v_sorted) - 1):
                x0 = v_sorted[col_idx]
                y0 = h_sorted[row_idx]
                x1 = v_sorted[col_idx + 1]
                y1 = h_sorted[row_idx + 1]
                
                default_name = f'field_r{row_idx}_c{col_idx}'
                name = simpledialog.askstring(
                    'Name Region',
                    f'Region [{row_idx},{col_idx}]: ({x0},{y0}) -> ({x1},{y1})\nField name:',
                    initialvalue=default_name,
                    parent=self.root
                )
                
                if name and name.strip():
                    name = name.strip()
                    self.fields[name] = {
                        'x': x0, 'y': y0,
                        'w': x1 - x0, 'h': y1 - y0
                    }
                    self.region_listbox.insert(tk.END, f'{name}: ({x0},{y0}) {x1-x0}x{y1-y0}')
        
        self.status_var.set(f'Created {len(self.fields)} regions')
    
    def _export(self):
        import tkinter as tk
        from tkinter import messagebox
        if not self.fields:
            tk.messagebox.showwarning('Export', 'No regions to export. Draw lines and name regions first.')
            return
        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(self.fields, f, indent=2, ensure_ascii=False)
        self.status_var.set(f'Exported {len(self.fields)} regions')
        tk.messagebox.showinfo('Export', f'Saved {len(self.fields)} regions to\n{self.output_path}')
    
    def _quit(self):
        import tkinter as tk
        from tkinter import messagebox
        if self.fields and tk.messagebox.askyesno('Quit', 'Export before quitting?'):
            self._export()
        self.root.destroy()
    
    def run(self):
        self.root.mainloop()
        return self.fields


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--template', choices=['small', 'medium'], default='small')
    parser.add_argument('--output', default=None)
    args = parser.parse_args()
    img_path = TEMPLATES[args.template]
    output_path = args.output or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'template_regions',
        args.template + '_form_v1.json')
    
    selector = LineSelector(img_path, output_path)
    result = selector.run()
    print('Selected regions:', json.dumps(result, indent=2, ensure_ascii=False))
