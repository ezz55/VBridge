import datetime
import numpy as np
import pandas as pd

import featuretools as ft
import woodwork as ww
from woodwork.column_schema import ColumnSchema


class Date(ft.primitives.TransformPrimitive):
    """Transform datetime to numeric days since reference date."""
    
    name = 'date'
    input_types = [ColumnSchema(logical_type=ww.logical_types.Datetime)]
    return_type = ColumnSchema(logical_type=ww.logical_types.Integer, semantic_tags={'numeric'})
    description_template = "the number of days since 1997-01-01"

    def __init__(self):
        super().__init__()
        self.reference_date = datetime.date(1997, 1, 1)

    def get_function(self):
        def date(column):
            if column is None:
                return None
            return column.apply(lambda row: (row.date() - self.reference_date).days)
        return date
