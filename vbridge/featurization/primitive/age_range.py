import featuretools as ft
import woodwork as ww
from woodwork.column_schema import ColumnSchema


class AgeRange(ft.primitives.TransformPrimitive):
    """Transform age in days to categorical age ranges."""
    
    name = 'age_range'
    input_types = [ColumnSchema(logical_type=ww.logical_types.Integer, semantic_tags={'numeric'})]
    return_type = ColumnSchema(logical_type=ww.logical_types.Ordinal)
    description_template = "the age range category based on days"

    def __init__(self):
        super().__init__()
        self.age_ranges = {
            (0, 4 * 7): "newborn (0–4 weeks)",
            (4 * 7, 365): "infant (4 weeks - 1 year)",
            (365, 365 * 2): "toddler (1-2 years)",
            (365 * 2, float('inf')): "preschooler or above(>2 years)"
        }

    def get_function(self):
        def age_range(day):
            for (lower, upper), category in self.age_ranges.items():
                if lower <= day < upper:
                    return category
            return "unknown"

        def age(column):
            if column is None:
                return None
            return column.apply(age_range)
        return age
