from PIL import ImageFilter

from define import define

def blur(image, area):
    cropped = image.crop(area)
    blured = cropped.filter(ImageFilter.GaussianBlur(10))
    image.paste(blured, (area[:2]))

    return image

def filter(image, play_side, loveletter, rivalname):
    """適切な位置にぼかしを入れる

    ライバル順位と、必要があれば挑戦状・グラフターゲットのライバル名にぼかしを入れる。

    Args:
        result (Result): 対象のリザルト(result.py)
        image (Image): 対象の画像(PIL)
        play_side (str): 1P or 2P
        loveletter (bool): ライバル挑戦状の有無
        rivalname (bool): グラフターゲットのライバル名の有無

    Returns:
        Image: ぼかしを入れた画像
    """
    ret = image.copy()

    if play_side != '':
        ret = blur(ret, define.filter_areas['ranking'][play_side])
        if rivalname:
            ret = blur(ret, define.filter_areas['graphtarget_name'][play_side])

    if loveletter:
        ret = blur(ret, define.filter_areas['loveletter'])
    
    return ret
