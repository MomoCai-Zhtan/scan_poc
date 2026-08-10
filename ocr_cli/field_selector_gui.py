# -*- coding: utf-8 -*-
"""Interactive field region selector using tkinter GUI with toolbar.

Usage:
    python field_selector_gui.py [--template small|medium] [--output regions.json]

Features:
    - Toolbar with icons for common actions
    - Click and drag to select regions
    - Side panel lists selected fields
    - Double-click field to rename or delete
    - Undo last selection
    - Export to JSON
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TEMPLATES = {
    'small': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'small_form_blank.png'),
    'medium': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'medium_form_blank.png'),
}


def _make_toolbar_icon(size, color, symbol):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = size // 4
    draw.rectangle([pad, pad, size - pad, size - pad], outline=color, width=max(1, size // 8))
    cx, cy = size // 2, size // 2
    if symbol == 'undo':
        draw.polygon([(cx - size//4, cy + size//6), (cx, cy - size//6), (cx + size//4, cy + size//6)], fill=color)
    elif symbol == 'delete':
        draw.line([(pad, pad), (size-pad, size-pad)], fill=color, width=max(2, size//6))
    elif symbol == 'rename':
        draw.rectangle([pad, cy - size//8, size-pad, cy + size//8], outline=color, width=max(1, size//8))
    elif symbol == 'export':
        draw.polygon([(cx, size-pad), (cx - size//4, cy), (cx + size//4, cy)], fill=color)
        draw.rectangle([cx - size//3, cy, cx + size//3, size-pad], fill=color)
    elif symbol == 'save':
        draw.rectangle([pad, pad, size-pad, size-pad], outline=color, width=max(1, size//8))
        draw.rectangle([cx - size//4, cy - size//4, cx + size//4, cy + size//4], fill=color)
    elif symbol == 'quit':
        draw.line([(pad, pad), (size-pad, size-pad)], fill=color, width=max(2, size//6))
        draw.line([(size-pad, pad), (pad, size-pad)], fill=color, width=max(2, size//6))
    return ImageTk.PhotoImage(img)


class FieldSelector:
    def __init__(self, img_path, output_path):
        self.img_path = img_path
        self.output_path = output_path
        self.fields = {}
        self.current_rect = None
        self.start_pos = None
        
        try:
            from PIL import Image
            pil_img = Image.open(img_path)
            self.img_rgb = np.array(pil_img)
            self.img_bgr = cv2.cvtColor(self.img_rgb, cv2.COLOR_RGB2BGR)
        except Exception as e:
            print('Cannot read', img_path, 'error:', e)
            sys.exit(1)
        
        self.h, self.w = self.img_bgr.shape[:2]
        self._setup_gui()
    
    def _setup_gui(self):
        import tkinter as tk
        from tkinter import ttk, simpledialog, messagebox
        
        self.root = tk.Tk()
        self.root.title('Field Selector - ' + os.path.basename(self.img_path))
        self.root.geometry('1200x700')
        
        # Toolbar
        toolbar = tk.Frame(self.root, relief=tk.RAISED, borderwidth=1)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        
        try:
            from PIL import Image, ImageDraw
            icon_size = 24
            icons = {
                'Undo': ('undo', '#2196F3'),
                'Delete': ('delete', '#f44336'),
                'Rename': ('rename', '#4CAF50'),
                'Export': ('export', '#FF9800'),
                'Save': ('save', '#9C27B0'),
                'Quit': ('quit', '#607D8B'),
            }
            self.toolbar_photos = {}
            for name, (symbol, color) in icons.items():
                icon = _make_toolbar_icon(icon_size, color, symbol)
                self.toolbar_photos[name] = icon
                btn = tk.Button(toolbar, image=icon, text=name, compound=tk.LEFT,
                               command=getattr(self, f'_{name.lower()}'), width=60, height=28)
                btn.pack(side=tk.LEFT, padx=2, pady=2)
        except Exception:
            for text, cmd in [('Undo', '_undo'), ('Delete', '_delete_selected'), ('Rename', '_rename_selected'),
                             ('Export', '_export'), ('Save', '_export'), ('Quit', '_quit')]:
                tk.Button(toolbar, text=text, command=getattr(self, cmd), width=8).pack(side=tk.LEFT, padx=2, pady=2)
        
        # Main area
        main_frame = tk.Frame(self.root)
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Left panel: canvas
        canvas_frame = tk.Frame(main_frame)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        max_w, max_h = 900, 650
        scale = min(max_w / self.w, max_h / self.h, 1.0)
        disp_w, disp_h = int(self.w * scale), int(self.h * scale)
        self.scale = scale
        
        img_disp = cv2.resize(self.img_bgr, (disp_w, disp_h))
        img_rgb = cv2.cvtColor(img_disp, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        self.photo = ImageTk.PhotoImage(pil_img)
        
        self.canvas = tk.Canvas(canvas_frame, width=disp_w, height=disp_h, bg='gray')
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        self.canvas.image = self.photo
        
        self.canvas.bind('<ButtonPress-1>', self._on_mouse_down)
        self.canvas.bind('<B1-Motion>', self._on_mouse_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_mouse_up)
        
        # Right panel
        right_panel = tk.Frame(main_frame, width=280, bg='#f0f0f0')
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
        
        tk.Label(right_panel, text='Selected Fields', font=('Arial', 12, 'bold'), bg='#f0f0f0').pack(pady=5)
        
        list_frame = tk.Frame(right_panel)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.field_listbox = tk.Listbox(list_frame, width=30, height=20, yscrollcommand=scrollbar.set, font=('Consolas', 10))
        self.field_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.field_listbox.yview)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set('Ready')
        status_bar = tk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, bg='#e0e0e0')
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _canvas_to_image(self, cx, cy):
        return int(cx / self.scale), int(cy / self.scale)
    
    def _on_mouse_down(self, event):
        self.start_pos = (event.x, event.y)
    
    def _on_mouse_drag(self, event):
        if self.start_pos:
            self.canvas.delete('current_rect')
            self.canvas.create_rectangle(
                self.start_pos[0], self.start_pos[1], event.x, event.y,
                outline='lime', width=2, tags='current_rect'
            )
    
    def _on_mouse_up(self, event):
        if not self.start_pos:
            return
        x0, y0 = self._canvas_to_image(*self.start_pos)
        x1, y1 = self._canvas_to_image(event.x, event.y)
        self.start_pos = None
        self.canvas.delete('current_rect')
        
        name = tk.simpledialog.askstring('Field Name', 'Enter field name:', parent=self.root)
        if name:
            name = name.strip()
            if name:
                self.fields[name] = {
                    'x': min(x0, x1), 'y': min(y0, y1),
                    'w': abs(x1 - x0), 'h': abs(y1 - y0)
                }
                self._refresh_list()
                self._draw_rect(name, self.fields[name])
                self.status_var.set(f'Added: {name}')
    
    def _draw_rect(self, name, rect):
        x, y, w, h = rect['x'], rect['y'], rect['w'], rect['h']
        cx, cy = x * self.scale, y * self.scale
        cw, ch = w * self.scale, h * self.scale
        self.canvas.create_rectangle(cx, cy, cx + cw, cy + ch, outline='cyan', width=2, tags=name)
        self.canvas.create_text(cx + 5, cy + 5, text=name, anchor=tk.NW, fill='yellow', font=('Arial', 9), tags=name)
    
    def _refresh_list(self):
        self.field_listbox.delete(0, tk.END)
        for name in self.fields:
            r = self.fields[name]
            self.field_listbox.insert(tk.END, f"{name:15s} x={r['x']:4d} y={r['y']:4d} w={r['w']:3d} h={r['h']:3d}")
    
    def _undo(self):
        if self.fields:
            name = list(self.fields.keys())[-1]
            del self.fields[name]
            self.canvas.delete(name)
            self._refresh_list()
            self.status_var.set(f'Undo: {name}')
    
    def _delete_selected(self):
        sel = self.field_listbox.curselection()
        if sel:
            idx = sel[0]
            name = list(self.fields.keys())[idx]
            self.canvas.delete(name)
            del self.fields[name]
            self._refresh_list()
            self.status_var.set(f'Deleted: {name}')
    
    def _rename_selected(self):
        sel = self.field_listbox.curselection()
        if sel:
            idx = sel[0]
            name = list(self.fields.keys())[idx]
            new_name = tk.simpledialog.askstring('Rename', 'New name:', initialvalue=name, parent=self.root)
            if new_name and new_name.strip() and new_name != name:
                self.fields[new_name.strip()] = self.fields.pop(name)
                self.canvas.itemconfig(name, tags=new_name.strip())
                self._refresh_list()
                self.status_var.set(f'Renamed: {name} -> {new_name}')
    
    def _export(self):
        if not self.fields:
            tk.messagebox.showwarning('Export', 'No fields to export')
            return
        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(self.fields, f, indent=2, ensure_ascii=False)
        self.status_var.set(f'Exported {len(self.fields)} fields')
        tk.messagebox.showinfo('Export', f'Saved {len(self.fields)} fields to\n{self.output_path}')
    
    def _save(self):
        self._export()
    
    def _quit(self):
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
    
    selector = FieldSelector(img_path, output_path)
    result = selector.run()
    print('Selected fields:', json.dumps(result, indent=2, ensure_ascii=False))
