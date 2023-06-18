import io
import PySimpleGUI as sg
from PIL import Image

from .static import icon_path,background_color

icon_image = Image.open(icon_path)
resized_icon = icon_image.resize((32, 32))
icon_bytes = io.BytesIO()
resized_icon.save(icon_bytes, format='PNG')

def get_imagevalue(image):
    bytes = io.BytesIO()
    image.save(bytes, format='PNG')
    return bytes.getvalue()

def message(title, message):
    sg.popup(
        '\n'.join([
            message,
        ]),
        title=title,
        icon=icon_path,
        background_color=background_color
    )
