import os
import numpy as np
import pickle

from data_collection import load_collections
from define import define
from resources import resources_dirname

area = define.details_areas['graphtarget']['label']

filepath = os.path.join(resources_dirname, 'graphtarget.res')
if os.path.exists(filepath):
    with open(filepath, 'rb') as f:
        table = pickle.load(f)
else:
    table = {}

def get_graphtarget(image_details):
    if image_details.height != define.details_trimsize[1]:
        return None
    
    np_value = np.array(image_details.crop(area))
    flattend = np_value.flatten()

    unique, counts = np.unique(flattend, return_counts=True)
    dark_count = np.count_nonzero(unique < 100)
    mode = unique[np.argmax(counts[dark_count:])+dark_count]

    if not mode in table.keys():
        return None

    count = np.count_nonzero(flattend==mode)
    if not count in table[mode].keys():
        return None

    return table[mode][count]

def larning_graphtarget(targets):
    global table

    print('larning graphtarget')
    print(f'count: {len(targets)}')

    table = {}
    keys = {}
    values = []
    for key, target in targets.items():
        value = target['value']
        np_value = target['np']
        flattend = np_value.flatten()
        
        unique, counts = np.unique(flattend, return_counts=True)
        dark_count = np.count_nonzero(unique < 100)
        mode = unique[np.argmax(counts[dark_count:])+dark_count]
        if not mode in table.keys():
            table[mode] = {}
            keys[mode] = {}
        
        count = np.count_nonzero(flattend==mode)
        if count in table[mode].keys():
            if table[mode][count] != value:
                print(f'mode: {mode}')
                print(f'count: {count}')
                print(f'value: {value}')
                print(f'key: {key}')
                print(f'duplicate: {table[mode][count]}, {keys[mode][count]}')
                print("NG")
                return
        else:
            table[mode][count] = value
            keys[mode][count] = key
            values.append(value)

    uniques, counts = np.unique(np.array(values), return_counts=True)
    multicount_values = [value for value in np.where(counts>=2,uniques,None) if value is not None]
    if len(multicount_values) != 0:
        print(multicount_values)
        print('NG')
        return

    with open(filepath, 'wb') as f:
        pickle.dump(table, f)
    
    return table

if __name__ == '__main__':
    collections = load_collections()

    targets = {}
    for collection in collections:
        label = collection.label
        if collection.details is not None:
            image = collection.details

            if 'graphtarget' in label['details'].keys() and label['details']['graphtarget'] != '':
                targets[collection.key] = {
                    'value': label['details']['graphtarget'],
                    'np': np.array(image.crop(area))
                }

    larning_graphtarget(targets)

    print(table)
