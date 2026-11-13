"""麦日常测试使用宿主安装的真实插件 SDK。"""

import pytest

from src.plugins.built_in.mylife import plugin


@pytest.fixture(scope="session")
def plugin_module():

    return plugin
