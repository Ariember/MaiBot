from PIL import Image

import io
import pytest

from src.common.utils.utils_image import ImageUtils


@pytest.mark.parametrize("colors,frame_count", [([0, 255], 2), ([255, 0], 2), ([0, 10], 1)])
def test_gif_frame_selection_uses_full_pixel_difference(colors, frame_count):
    frames = [Image.new("RGB", (4, 4), (value, value, value)) for value in colors]
    gif = io.BytesIO()
    frames[0].save(gif, format="GIF", save_all=True, append_images=frames[1:], duration=100, loop=0)

    result = ImageUtils.gif_2_static_image(gif.getvalue())

    with Image.open(io.BytesIO(result)) as image:
        assert image.size == (200 * frame_count, 200)
