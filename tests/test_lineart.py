# -*- coding: utf-8 -*-
"""白描底稿的 Sobel 算子。

纯数学，用合成数组验证，不碰任何图片文件。
这条测试的价值：Sobel 是"白描锁构图"的第一步，它偏一个像素，后面整条
重绘链路都建立在错误的线稿上。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402

support.add_tools_path()
import numpy as np  # noqa: E402

import lineart as LA  # noqa: E402


class TestSobel(unittest.TestCase):
    def setUp(self):
        # 垂直阶跃：左半 0，右半 1，边界在 x=4
        self.g = np.zeros((8, 8), dtype=float)
        self.g[:, 4:] = 1.0

    def test_shape_is_preserved(self):
        e = LA.sobel(self.g)
        self.assertEqual(e.shape, self.g.shape)

    def test_output_is_float(self):
        e = LA.sobel(self.g)
        self.assertTrue(np.issubdtype(e.dtype, np.floating))

    def test_edge_is_located_at_the_step(self):
        """梯度峰值必须落在阶跃那一列。"""
        e = LA.sobel(self.g)
        self.assertEqual(int(e.max(axis=0).argmax()), 4)

    def test_flat_region_has_no_response(self):
        e = LA.sobel(self.g)
        self.assertLess(float(e[:, :2].max()), 0.05, "平坦区出现了虚假边缘")

    def test_uniform_image_is_silent_inside(self):
        """均匀图像内部不该有梯度。

        注意：`_shift()` 是**边界补零**，所以图像最外一圈会有伪边缘
        （实测均匀 0.5 图的最大值 0.53 出现在边框）。这里只断言内部，
        边框行为由下一条测试单独钉住，避免把已知行为当成 bug 或藏起来。
        """
        e = LA.sobel(np.full((8, 8), 0.5))
        interior = e[2:-2, 2:-2]
        self.assertLess(float(interior.max()), 1e-9, "均匀图像内部不该有梯度")

    def test_zero_padding_leaves_a_border_response(self):
        """记录既有行为：边界补零 → 最外圈一定有响应。

        这条不是"期望如此"，而是把行为钉住。若将来改成镜像/复制填充，
        这条会失败，届时需要连同 lineart 的调用方一起复核。
        """
        e = LA.sobel(np.full((16, 16), 0.5))
        self.assertGreater(float(e[0, :].max()), 0.0, "边界补零应产生边框响应")
        self.assertLess(float(e[4:-4, 4:-4].max()), 1e-9, "内部仍应无响应")

    def test_horizontal_step_also_detected(self):
        g = np.zeros((8, 8), dtype=float)
        g[4:, :] = 1.0
        e = LA.sobel(g)
        self.assertEqual(int(e.max(axis=1).argmax()), 4)


if __name__ == "__main__":
    unittest.main()
