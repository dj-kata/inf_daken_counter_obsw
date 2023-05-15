import os
import numpy as np
import pickle

from data_collection import load_collections
from define import define
from resources import resources_dirname

area_best = define.details_areas['dj_level']['best']
area_current = define.details_areas['dj_level']['current']
color = define.dj_level_pick_color

filepath = os.path.join(resources_dirname, 'dj_level.res')
if os.path.exists(filepath):
    with open(filepath, 'rb') as f:
        table = pickle.load(f)
else:
    table = {}

def get_dj_level_best(image_details):
    np_value = np.array(image_details.crop(area_best))
    flattend = np_value.flatten()

    picked = np.where(flattend==color, flattend, 0)
    sum_value = np.sum(picked)

    if not sum_value in table.keys():
        return None

    return table[sum_value]

def get_dj_level_current(image_details):
    np_value = np.array(image_details.crop(area_current))
    flattend = np_value.flatten()

    picked = np.where(flattend==color, flattend, 0)
    sum_value = np.sum(picked)

    if not sum_value in table.keys():
        return None

    return table[sum_value]

def larning_dj_level(targets):
    global table

    print('larning dj level')

    table = {}
    keys = {}
    for key, target in targets.items():
        value = target['value']
        np_value = target['np']
        flattend = np_value.flatten()

        picked = np.where(flattend==color, flattend, 0)
        sum_value = np.sum(picked)

        if sum_value in table.keys() and table[sum_value] != value:
            print(sum_value)
            print(f'{key}: {value}')
            print(f'{keys[sum_value]}: {table[sum_value]}')
            print("NG")
            return
        else:
            table[sum_value] = value
            keys[sum_value] = key

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
        if collection.details is not None:
            image = collection.details

            if label['details']['dj_level_best'] != '':
                targets[f'{collection.key}_best'] = {
                    'value': label['details']['dj_level_best'],
                    'np': np.array(image.crop(area_best))
                }
            if label['details']['dj_level_current'] != '':
                targets[f'{collection.key}_current'] = {
                    'value': label['details']['dj_level_current'],
                    'np': np.array(image.crop(area_current))
                }

    larning_dj_level(targets)
