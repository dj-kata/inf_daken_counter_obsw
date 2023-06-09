import os
import numpy as np
import pickle

from data_collection import load_collections
from define import define
from resources import resources_dirname

area_score = define.details_areas['score']['best']
area_miss_count = define.details_areas['miss_count']['best']

color_best = define.number_pick_color_best

filepath = os.path.join(resources_dirname, 'number_best.res')
if os.path.exists(filepath):
    with open(filepath, 'rb') as f:
        table = pickle.load(f)
else:
    table = {}

def get(cropped_image):
    ret = 0
    is_number = False
    for trimarea in define.number_best_trimareas:
        cropped_number = cropped_image.crop(trimarea)
        np_value = np.array(cropped_number)
        segment_values = np.array([np_value[x,y] for x, y in define.number_best_segments])
        picked = np.where(segment_values==color_best)
        squared = np.power(2, picked)
        sum_value = np.sum(squared)

        if sum_value in table.keys():
            ret = ret * 10 + table[sum_value]
            is_number = True
    
    return ret if is_number else None

def get_best_score(image_details):
    return get(image_details.crop(area_score))

def get_best_miss_count(image_details):
    return get(image_details.crop(area_miss_count))

def larning_number_best(targets):
    global table

    print('larning best number')

    table = {}
    keys = {}
    for key, target in targets.items():
        value = target['value']
        np_value = target['np']
        segment_values = np.array([np_value[x,y] for x, y in define.number_best_segments])
        picked = np.where(segment_values==color_best)
        squared = np.power(2, picked)
        sum_value = np.sum(squared)

        if sum_value in table.keys():
            if table[sum_value] != value:
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

            for key in ['score', 'miss_count']:
                if f'{key}_best' in label['details'].keys() and label['details'][f'{key}_current'] != '':
                    cropped_value = image.crop(define.details_areas[key]['best'])
                    value = int(label['details'][f'{key}_best'])
                    digit = 1
                    while int(value) > 0 or digit == 1:
                        number = int(value % 10)
                        cropped_number = cropped_value.crop(define.number_best_trimareas[4-digit])
                        targets[f'{collection.key}_{key}_{digit}_{number}'] = {
                            'value': number,
                            'np': np.array(cropped_number)
                        }
                        value /= 10
                        digit += 1

    larning_number_best(targets)
