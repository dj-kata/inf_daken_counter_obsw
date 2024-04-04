from PIL import ImageFilter

from define import define

def blur(image, area):
    cropped = image.crop(area)
    blured = cropped.filter(ImageFilter.GaussianBlur(10))
    image.paste(blured, (area[:2]))

    return image

def filter(image, play_side, loveletter, rivalname, compact):
    """適切な位置にぼかしを入れる

    ライバル順位と、必要があれば挑戦状・グラフターゲットのライバル名にぼかしを入れる。

    Args:
        result (Result): 対象のリザルト(result.py)
        image (Image): 対象の画像(PIL)
        play_side (str): 1P or 2P
        loveletter (bool): ライバル挑戦状の有無
        rivalname (bool): グラフターゲットのライバル名の有無
        compact (bool): ぼかしの範囲を最小限にする

    Returns:
        Image: ぼかしを入れた画像
    """
    ret = image.copy()

    if play_side != '':
        if not compact:
            ret = blur(ret, define.filter_areas['ranking'][play_side])
        else:
            for area in define.filter_areas['ranking_compact'][play_side]:
                ret = blur(ret, area)
        
        if rivalname:
            ret = blur(ret, define.filter_areas['graphtarget_name'][play_side])

    if loveletter:
        if not compact:
            ret = blur(ret, define.filter_areas['loveletter'])
        else:
            ret = blur(ret, define.filter_areas['loveletter_compact'])
    
    return ret
