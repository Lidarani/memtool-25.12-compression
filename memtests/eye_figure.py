# Copyright 2023 NXP
"""TODO:summary line."""
from matplotlib.figure import Figure


class EyeFigure(Figure):
    """Figure containing Eye graphics."""

    def __init__(self, figure_size, horizontal_margin_inch, vertical_margin_inch,  # type: ignore
                 width_padding_ratio, height_padding_ratio):
        """Constructor of EyeFigure.

        @param figure_size: Tuple of width and height of figure.
        @param horizontal_margin_inch: Value in inch of horizontal left/right margin of the figure.
        @param vertical_margin_inch: Value in inch of vertical up/bottom margin of the figure.
        @param width_padding_ratio: Ratio of the width padding between Eye graphic and vertical axes.
        @param height_padding_ratio: Ratio of the height padding between Eye graphic and horizontal axes.
        """
        super().__init__(figure_size)
        (figure_wide, figure_height) = figure_size
        _left = horizontal_margin_inch / figure_wide
        _bottom = vertical_margin_inch / figure_height
        _right = 1 - _left
        _top = 1 - _bottom
        super().subplots_adjust(left=_left, bottom=_bottom, right=_right, top=_top,
                                wspace=width_padding_ratio, hspace=height_padding_ratio)


class EyeMatrixFigure(EyeFigure):
    """Figure where Eye graphics are disposed on columns and rows."""
    width_eye_inch = 0  # Width in inches of a single Eye graphic.
    height_eye_inch = 0  # Height in inches of a single Eye graphic.
    horizontal_margin_inch = 0.0  # Value in inch of horizontal left/right margin of the figure.
    vertical_margin_inch = 0.0  # Value in inch of vertical up/bottom margin of the figure.
    width_padding_ratio = 0.0  # Ratio of the width padding between Eye graphic and vertical axes.
    height_padding_ratio = 0.0  # Ratio of the height padding between Eye graphic and horizontal axes.

    def __init__(self, no_eye_columns: int, number_eye_rows: int):
        """Constructor of EyeMatrixFigure.

        @param no_eye_columns: Number of columns of Eye graphics.
        @param number_eye_rows: Number of rows of Eye graphics.
        """
        figure_size = (no_eye_columns * self.width_eye_inch, number_eye_rows * self.height_eye_inch)
        super().__init__(figure_size, self.horizontal_margin_inch, self.vertical_margin_inch,
                         self.width_padding_ratio, self.height_padding_ratio)


class BarEyeFigure(EyeMatrixFigure):
    """Figure where Eye graphics are disposed on columns and rows and an Eye graphic is built from bars."""

    # Override of attributes before calling super constructor.
    width_eye_inch = 5  # Width in inches of a single Eye graphic.
    height_eye_inch = 2  # Height in inches of a single Eye graphic.
    horizontal_margin_inch = 0.5  # Value in inch of horizontal left/right margin of the figure.
    vertical_margin_inch = 0.5  # Value in inch of vertical up/bottom margin of the figure.
    width_padding_ratio = 0.2  # Ratio of the width padding between Eye graphic and vertical axes.
    height_padding_ratio = 0.5  # Ratio of the height padding between Eye graphic and horizontal axes.

    def __init__(self, no_eye_columns: int, number_eye_rows: int):
        """Constructor of BarEyeFigure.

        @param no_eye_columns: Number of columns of Eye graphics.
        @param number_eye_rows: Number of rows of Eye graphics.
        """
        super().__init__(no_eye_columns, number_eye_rows)


class HeatMapEyeFigure(EyeMatrixFigure):
    """Figure where Eye graphics are disposed on columns and rows and an Eye graphic is a heat map."""

    # Override of attributes before calling super constructor.
    width_eye_inch = 4  # Width in inches of a single Eye graphic.
    height_eye_inch = 2.25  # type: ignore  # Height in inches of a single Eye graphic.
    horizontal_margin_inch = 0.5  # Value in inches of horizontal left/right margin of the figure.
    vertical_margin_inch = 0.5  # Value in inches of vertical up/bottom margin of the figure.
    width_padding_ratio = 0.3  # Ratio of the width padding between Eye graphic and vertical axes.
    height_padding_ratio = 0.95  # Ratio of the height padding between Eye graphic and horizontal axes.

    def __init__(self, no_eye_columns: int, number_eye_rows: int):
        """Constructor of HeatMapEyeFigure.

        @param no_eye_columns: Number of columns of Eye graphics.
        @param number_eye_rows: Number of rows of Eye graphics.
        """
        super().__init__(no_eye_columns, number_eye_rows)


class CABusEyeFigure(BarEyeFigure):
    """Figure for CA Bus Eye graphics."""

    # Override of attributes before calling super constructor.
    horizontal_margin_inch = 0.55
    vertical_margin_inch = 0.5

    def __init__(self, no_eye_columns: int, number_eye_rows: int):
        """Constructor of CABusEyeFigure.

        @param no_eye_columns: Number of columns of Eye graphics.
        @param number_eye_rows: Number of rows of Eye graphics.
        """
        super().__init__(no_eye_columns, number_eye_rows)


class CAEyeFigure(BarEyeFigure):
    """Figure for CA Eye graphics."""

    # Override of attributes before calling super constructor.
    horizontal_margin_inch = 0.8
    vertical_margin_inch = 0.5

    def __init__(self, no_eye_columns: int, number_eye_rows: int):
        """Constructor of CAEyeFigure.

        @param no_eye_columns: Number of columns of Eye graphics.
        @param number_eye_rows: Number of rows of Eye graphics.
        """
        super().__init__(no_eye_columns, number_eye_rows)


class DiagEyeFigure(HeatMapEyeFigure):
    """Figure for DiagTx/Rx Eye graphics."""

    # Override of attributes before calling super constructor.
    horizontal_margin_inch = 0.9
    vertical_margin_inch = 0.6

    def __init__(self, no_eye_columns: int, number_eye_rows: int):
        """Constructor of DiagEyeFigure.

        @param no_eye_columns: Number of columns of Eye graphics.
        @param number_eye_rows: Number of rows of Eye graphics.
        """
        super().__init__(no_eye_columns, number_eye_rows)
