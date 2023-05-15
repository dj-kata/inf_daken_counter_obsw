from PIL import ImageFilter

from define import define

def blur(image, area):
    cropped = image.crop(area)
    blured = cropped.filter(ImageFilter.GaussianBlur(10))
    image.paste(blured, (area[:2]))
    return image

def filter(result):
    ret = result.image.copy()

    if result.play_side != '':
        ret = blur(ret, define.filter_areas['ranking'][result.play_side])
        if result.details.graphtarget == 'rival':
            ret = blur(ret, define.filter_areas['graphtarget_name'][result.play_side])

    if result.rival:
        ret = blur(ret, define.filter_areas['loveletter'])
    
    return ret
