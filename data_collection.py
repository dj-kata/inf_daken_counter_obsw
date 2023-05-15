import os
import json
from PIL import Image

collection_basepath = 'collection_data'

informations_basepath = os.path.join(collection_basepath, 'informations')
details_basepath = os.path.join(collection_basepath, 'details')

label_filepath = os.path.join(collection_basepath, 'label.json')

class Collection():
    def __init__(self, key, informations, details, label):
        self.key = key
        self.informations = informations
        self.details = details
        self.label = label

def load_collections():
    with open(label_filepath) as f:
        labels = json.load(f)

    keys = [*labels.keys()]
    print(f"label count: {len(keys)}")

    collections = []
    for key in keys:
        filename = f'{key}.png'

        i_filepath = os.path.join(informations_basepath, filename)
        if os.path.isfile(i_filepath):
            i_image = Image.open(i_filepath).convert('L')
            if i_image.height == 75:
                i_image = i_image.crop((0, 3, 0, 74))
            if i_image.height == 78:
                i_image = i_image.crop((0, 5, 0, 76))
        else:
            i_image = None

        d_filepath = os.path.join(details_basepath, filename)
        if os.path.isfile(d_filepath):
            d_image = Image.open(d_filepath).convert('L')
        else:
            d_image = None

        collections.append(Collection(filename, i_image, d_image, labels[key]))
    
    return collections

