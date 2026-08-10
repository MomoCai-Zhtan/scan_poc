# -*- coding: utf-8 -*-
"""Interactive field region selector for blank form templates.

Usage:
    python field_selector.py [--template small|medium] [--output regions.json]

Left-click and drag to select a region. After each selection, enter the
field name in the console. Press 'q' to quit and save.
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TEMPLATES = {
    'small': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'small_form_blank.png'),
    'medium': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'medium_form_blank.png'),
}


def select_fields(img_path, output_path):
    try:
        from PIL import Image
        pil_img = Image.open(img_path)
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    except Exception as e:
        print('Cannot read', img_path, 'error:', e)
        return {}
    fields = {}
    current = {'start': None, 'end': None, 'drawing': False}
    temp_img = img.copy()

    def mouse_cb(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            current['drawing'] = True
            current['start'] = (x, y)
            current['end'] = (x, y)
        elif event == cv2.EVENT_MOUSEMOVE and current['drawing']:
            current['end'] = (x, y)
            disp = temp_img.copy()
            cv2.rectangle(disp, current['start'], current['end'], (0, 255, 0), 2)
            cv2.imshow('Select Field', disp)
        elif event == cv2.EVENT_LBUTTONUP:
            current['drawing'] = False
            current['end'] = (x, y)
            x0 = min(current['start'][0], x)
            y0 = min(current['start'][1], y)
            x1 = max(current['start'][0], x)
            y1 = max(current['start'][1], y)
            name = input('Field name (empty to skip): ').strip()
            if name:
                fields[name] = {'x': x0, 'y': y0, 'w': x1 - x0, 'h': y1 - y0}
                print('  Saved:', name, fields[name])
            cv2.imshow('Select Field', temp_img)

    cv2.namedWindow('Select Field')
    cv2.setMouseCallback('Select Field', mouse_cb)
    cv2.imshow('Select Field', img)
    print('Drag to select region. Enter field name. Press q to quit.')
    while True:
        k = cv2.waitKey(1) & 0xFF
        if k == ord('q'):
            break
    cv2.destroyAllWindows()
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(fields, f, indent=2, ensure_ascii=False)
    print('Saved', len(fields), 'fields to', output_path)
    return fields


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--template', choices=['small', 'medium'], default='small')
    parser.add_argument('--output', default=None)
    args = parser.parse_args()
    img_path = TEMPLATES[args.template]
    output_path = args.output or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'template_regions',
        args.template + '_form_v1.json')
    select_fields(img_path, output_path)
