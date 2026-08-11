# -*- coding: utf-8 -*-
"""Auto-detect table cells, let user select/merge/name fields.

Usage:
    python field_selector_cells.py [--template small|medium] [--output regions.json]

Features:
    - Auto-detect table grid lines from blank template
    - Extract ALL cells (not just blank ones)
    - User clicks to select cells
    - Merge selected cells into larger regions
    - Name each merged region
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
import detect_lib

TEMPLATES = {
    'small': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'small_form_blank.png'),
    'medium': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'medium_form_blank.png'),
}


def detect_grid_lines(img_bgr):
    """Detect table cells (including merged/rowspan cells). See detect_lib.detect_table_cells."""
    return detect_lib.detect_table_cells(img_bgr)


class CellSelector:
    def __init__(self, img_path, output_path):
        self.img_path = img_path
        self.output_path = output_path
        self.fields = {}
        self.selected_cells = set()
        self.cells = []
        self.h_lines = []
        self.v_lines = []
        
        try:
            from PIL import Image
            pil_img = Image.open(img_path)
            self.img_rgb = np.array(pil_img)
            self.img_bgr = cv2.cvtColor(self.img_rgb, cv2.COLOR_RGB2BGR)
        except Exception as e:
            print('Cannot read', img_path, 'error:', e)
            sys.exit(1)
        
        self.h, self.w = self.img_bgr.shape[:2]
        
        # Auto-detect cells
        print('Detecting table cells...')
        self.cells, self.h_lines, self.v_lines = detect_grid_lines(self.img_bgr)
        print(f'Detected {len(self.cells)} cells ({len(self.h_lines)-1} rows x {len(self.v_lines)-1} cols)')
        
        self._setup_gui()
    
    def _setup_gui(self):
        import tkinter as tk
        from tkinter import simpledialog, messagebox
        
        self.root = tk.Tk()
        self.root.title('Cell Selector - ' + os.path.basename(self.img_path))
        self.root.geometry('1400x800')
        
        # Toolbar
        toolbar = tk.Frame(self.root, relief=tk.RAISED, borderwidth=1)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        
        tk.Label(toolbar, text=f'{len(self.cells)} cells. Click to select, Shift+click for multi-select.', padx=10).pack(side=tk.LEFT)
        tk.Button(toolbar, text='Merge Selected', command=self._merge_selected, width=15).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text='Clear Selection', command=self._clear_selection, width=15).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text='Name Selected', command=self._name_selected, width=15).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text='Save Session', command=self._save_session, width=12).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text='Load Session', command=self._load_session, width=12).pack(side=tk.LEFT, padx=2)
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
        
        self.canvas.bind('<ButtonPress-1>', self._on_cell_click)
        
        # Right panel
        right_panel = tk.Frame(main_frame, width=320, bg='#f0f0f0')
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
        
        tk.Label(right_panel, text='Merged Fields', font=('Arial', 11, 'bold'), bg='#f0f0f0').pack(pady=(5, 2), anchor=tk.W)
        
        self.field_listbox = tk.Listbox(right_panel, width=32, height=20, font=('Consolas', 9))
        self.field_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set(f'Ready - {len(self.cells)} cells. Click to select, Shift+click for multi-select.')
        status_bar = tk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, bg='#e0e0e0')
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Draw grid
        self._draw_grid()
        self._refresh_field_list()
    
    def _draw_grid(self):
        self.canvas.delete('grid', 'cell_rect', 'cell_text')
        for y in self.h_lines:
            cy = int(y * self.scale)
            self.canvas.create_line(0, cy, self.canvas.winfo_width(), cy, fill='lightgray', width=1, tags='grid')
        for x in self.v_lines:
            cx = int(x * self.scale)
            self.canvas.create_line(cx, 0, cx, self.canvas.winfo_height(), fill='lightgray', width=1, tags='grid')
        
        # Draw all cells with faint borders
        for i, cell in enumerate(self.cells):
            x, y, w, h = cell['x'], cell['y'], cell['w'], cell['h']
            cx, cy = x * self.scale, y * self.scale
            cw, ch = w * self.scale, h * self.scale
            self.canvas.create_rectangle(cx, cy, cx + cw, cy + ch, outline='#dddddd', width=1, tags='grid')
    
    def _refresh_field_list(self):
        import tkinter as tk
        self.field_listbox.delete(0, tk.END)
        for name, rect in self.fields.items():
            merged = rect.get('merged_from', [])
            merge_info = ' (%d cells)' % len(merged) if merged else ''
            self.field_listbox.insert(tk.END, '%s: (%d,%d) %dx%d%s' % (name, rect['x'], rect['y'], rect['w'], rect['h'], merge_info))
    
    def _on_cell_click(self, event):
        x, y = self._canvas_to_image(event.x, event.y)
        
        # Find clicked cell
        clicked_idx = None
        for i, cell in enumerate(self.cells):
            if (cell['x'] <= x <= cell['x'] + cell['w'] and
                cell['y'] <= y <= cell['y'] + cell['h']):
                clicked_idx = i
                break
        
        if clicked_idx is None:
            return
        
        # Check for multi-select modifier (Shift or Control)
        modifiers = event.state
        is_shift = modifiers & 0x0001 != 0  # Shift
        is_ctrl = modifiers & 0x0004 != 0   # Control
        
        if is_shift or is_ctrl:
            if clicked_idx in self.selected_cells:
                self.selected_cells.discard(clicked_idx)
            else:
                self.selected_cells.add(clicked_idx)
        else:
            self.selected_cells = {clicked_idx}
        
        self._draw_cell_selection()
        self.status_var.set('Selected %d cells: %s' % (len(self.selected_cells), sorted(self.selected_cells)))
    
    def _canvas_to_image(self, cx, cy):
        return int(cx / self.scale), int(cy / self.scale)
    
    def _draw_cell_selection(self):
        self.canvas.delete('selection')
        for idx in self.selected_cells:
            cell = self.cells[idx]
            x, y, w, h = cell['x'], cell['y'], cell['w'], cell['h']
            cx, cy = x * self.scale, y * self.scale
            cw, ch = w * self.scale, h * self.scale
            self.canvas.create_rectangle(cx, cy, cx + cw, cy + ch, outline='gold', width=3, tags='selection')
            self.canvas.create_text(cx + 3, cy + 3, text=str(idx), anchor='nw', fill='gold', font=('Arial', 9, 'bold'), tags='selection')
    
    def _merge_selected(self):
        import tkinter as tk
        from tkinter import messagebox
        
        if not self.selected_cells:
            tk.messagebox.showwarning('Merge', 'No cells selected. Click on cells to select them.')
            return
        
        # Merge selected cells into bounding box
        cells = [self.cells[i] for i in sorted(self.selected_cells)]
        x0 = min(c['x'] for c in cells)
        y0 = min(c['y'] for c in cells)
        x1 = max(c['x'] + c['w'] for c in cells)
        y1 = max(c['y'] + c['h'] for c in cells)
        
        name = tk.simpledialog.askstring(
            'Merge Cells',
            f'Merging {len(self.selected_cells)} cells into ({x0},{y0}) -> ({x1},{y1})\nField name:',
            parent=self.root
        )
        
        if name and name.strip():
            name = name.strip()
            self.fields[name] = {
                'x': x0, 'y': y0,
                'w': x1 - x0, 'h': y1 - y0,
                'merged_from': sorted(self.selected_cells)
            }
            self._refresh_field_list()
            self.status_var.set(f'Merged {len(self.selected_cells)} cells into: {name}')
        
        self.selected_cells.clear()
        self._draw_cell_selection()
    
    def _name_selected(self):
        import tkinter as tk
        from tkinter import simpledialog
        
        if not self.selected_cells:
            tk.messagebox.showwarning('Name', 'No cells selected')
            return
        
        for idx in sorted(self.selected_cells):
            cell = self.cells[idx]
            name = tk.simpledialog.askstring(
                'Name Cell',
                f'Cell [{idx}] at ({cell["x"]},{cell["y"]}) size {cell["w"]}x{cell["h"]}\nField name:',
                parent=self.root
            )
            if name and name.strip():
                self.fields[name.strip()] = {
                    'x': cell['x'], 'y': cell['y'],
                    'w': cell['w'], 'h': cell['h']
                }
        
        self._refresh_field_list()
        self.selected_cells.clear()
        self._draw_cell_selection()
    
    def _clear_selection(self):
        self.selected_cells.clear()
        self._draw_cell_selection()
        self.status_var.set('Selection cleared')
    
    def _save_session(self):
        import tkinter as tk
        from tkinter import filedialog, messagebox
        
        session = {
            'selected_cells': list(self.selected_cells),
            'fields': self.fields,
            'h_lines': self.h_lines,
            'v_lines': self.v_lines,
            'template': os.path.basename(self.img_path)
        }
        
        path = filedialog.asksaveasfilename(
            defaultextension='.json',
            filetypes=[('JSON files', '*.json'), ('All files', '*.*')],
            initialfile='field_selector_session.json'
        )
        
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(session, f, indent=2, ensure_ascii=False)
            self.status_var.set(f'Session saved to {path}')
            messagebox.showinfo('Save Session', f'Saved session to\n{path}')
    
    def _load_session(self):
        import tkinter as tk
        from tkinter import filedialog, messagebox
        
        path = filedialog.askopenfilename(
            filetypes=[('JSON files', '*.json'), ('All files', '*.*')]
        )
        
        if not path:
            return
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                session = json.load(f)
            
            # Validate session data
            if 'fields' not in session or 'selected_cells' not in session:
                raise ValueError('Invalid session file')
            
            # Restore state
            self.fields = session.get('fields', {})
            self.selected_cells = set(session.get('selected_cells', []))
            if 'h_lines' in session:
                self.h_lines = session['h_lines']
            if 'v_lines' in session:
                self.v_lines = session['v_lines']
            
            # Update UI
            self._draw_grid()
            self._draw_cell_selection()
            self._refresh_field_list()
            self.status_var.set(f'Loaded session from {path}')
            messagebox.showinfo('Load Session', f'Loaded {len(self.fields)} fields from\n{path}')
            
        except Exception as e:
            messagebox.showerror('Load Session', f'Failed to load session:\n{e}')
    
    def _export(self):
        import tkinter as tk
        from tkinter import messagebox
        if not self.fields:
            tk.messagebox.showwarning('Export', 'No fields defined. Merge and name some cells first.')
            return
        
        # Convert to simple format
        output = {}
        for name, rect in self.fields.items():
            output[name] = {
                'x': rect['x'], 'y': rect['y'],
                'w': rect['w'], 'h': rect['h']
            }
        
        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        self.status_var.set(f'Exported {len(self.fields)} fields')
        tk.messagebox.showinfo('Export', f'Saved {len(self.fields)} fields to\n{self.output_path}')
    
    def _quit(self):
        import tkinter as tk
        from tkinter import messagebox
        if self.fields and tk.messagebox.askyesno('Quit', 'Export before quitting?'):
            self._export()
        
        # Auto-save session
        session_path = os.path.splitext(self.output_path)[0] + '_session.json'
        session = {
            'selected_cells': list(self.selected_cells),
            'fields': self.fields,
            'h_lines': self.h_lines,
            'v_lines': self.v_lines,
            'template': os.path.basename(self.img_path)
        }
        with open(session_path, 'w', encoding='utf-8') as f:
            json.dump(session, f, indent=2, ensure_ascii=False)
        print('Auto-saved session to', session_path)
        
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
    
    selector = CellSelector(img_path, output_path)
    result = selector.run()
    print('Named cells:', json.dumps(result, indent=2, ensure_ascii=False))
