import os
import numpy as np
import pickle

from data_collection import load_collections
from define import define
from resources import resources_dirname

area = define.informations_areas['notes']
color = define.notes_color

filepath = os.path.join(resources_dirname, 'notes.res')
if os.path.exists(filepath):
    with open(filepath, 'rb') as f:
        table = pickle.load(f)
else:
    table = {}

def get_notes(image_informations):
    cropped_image = image_informations.crop(area)
    ret = 0
    is_number = False
    for trimarea in define.notes_trimareas:
        cropped_number = cropped_image.crop(trimarea)
        np_value = np.array(cropped_number).flatten()
        bins = np.where(np_value==define.notes_color,1,0)
        hexs = bins[::4]*8+bins[1::4]*4+bins[2::4]*2+bins[3::4]
        tablekey = ''.join([format(v, '0x') for v in hexs])

        if tablekey in table.keys():
            ret = ret * 10 + table[tablekey]
            is_number = True
    
    return ret if is_number else None

def larning_notes(targets):
    global table

    print('larning notes')

    table = {}
    keys = {}
    for key, target in targets.items():
        value = target['value']
        np_value = target['np']
        bins = np.where(np_value==define.notes_color,1,0)
        hexs = bins[::4]*8+bins[1::4]*4+bins[2::4]*2+bins[3::4]
        tablekey = ''.join([format(v, '0x') for v in hexs])

        if tablekey in table.keys():
            if table[tablekey] != value:
                print(tablekey)
                print(f'{key}: {value}')
                print(f'{keys[tablekey]}: {table[tablekey]}')
                print("NG")
                return
        else:
            table[tablekey] = value
            keys[tablekey] = key

    values = [*table.values()]
    uniques, counts = np.unique(np.array(values), return_counts=True)
    multicount_values = [value for value in np.where(counts>=2,uniques,None) if value is not None]
    if len(multicount_values) != 0:
        print(multicount_values)
        print('NG')
        return
    
    for key, value in table.items():
        print(key, value)
    
    with open(filepath, 'wb') as f:
        pickle.dump(table, f)

if __name__ == '__main__':
    collections = load_collections()

    targets = {}
    for collection in collections:
        label = collection.label
        if collection.informations is not None:
            image = collection.informations

            if 'notes' in label['informations'].keys() and label['informations']['notes'] != '':
                cropped_value = image.crop(area)
                value = int(label['informations']['notes'])
                digit = 1
                while int(value) > 0 or digit == 1:
                    number = int(value % 10)
                    cropped_number = cropped_value.crop(define.notes_trimareas[4-digit])
                    targets[f'{collection.key}_{digit}_{number}'] = {
                        'value': number,
                        'np': np.array(cropped_number).flatten()
                    }
                    value /= 10
                    digit += 1

    larning_notes(targets)
