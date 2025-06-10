import collections

import pandas as pd
from sklearn.base import TransformerMixin


class OneHotEncoder(TransformerMixin):
    """Encode categorical columns into one-hot/multi-hot codes."""

    def __init__(self, topk=10):
        self._dummy_dict = {}
        self._dummy_columns = None
        self._categorical_columns = []
        self.topk = topk

    def fit(self, X):
        X = pd.DataFrame(X).copy()
        
        # Track which columns are categorical
        self._categorical_columns = []
        
        for column_name in X.columns:
            if X[column_name].dtype == object:
                self._categorical_columns.append(column_name)
                values = X[column_name].copy()
                
                if values.apply(lambda row: isinstance(row, list)).all():
                    counts = values.apply(collections.Counter).reset_index(drop=True)
                    sub_df = pd.DataFrame.from_records(counts, index=values.index).fillna(0)
                    selected_dummies = sub_df.sum(axis=0) \
                        .sort_values(ascending=False).index[:self.topk]
                    dummies = sub_df[selected_dummies]
                    others = sub_df[[col for col in sub_df.columns if col not in selected_dummies]]
                    dummies['Others'] = others.any(axis=1)
                else:
                    counts = values.value_counts(sort=True, ascending=False)
                    selected_dummies = counts[:self.topk].index
                    mask = values.isin(selected_dummies)
                    values[~mask] = "Others"
                    dummies = pd.get_dummies(values)
                    
                dummies = dummies.add_prefix(column_name + "_")
                X = X.join(dummies)
                self._dummy_dict[column_name] = selected_dummies
        
        # Remove original categorical columns and keep only numeric + dummy columns
        X = X.drop(columns=self._categorical_columns)
        self._dummy_columns = list(X.columns)
        return self

    def transform(self, X):
        X = pd.DataFrame(X).copy()
        
        # Add dummy columns for each categorical feature
        for column_name, selected_dummies in self._dummy_dict.items():
            if column_name in X.columns:
                values = X[column_name].copy()
                
            if values.apply(lambda row: isinstance(row, list)).all():
                counts = values.apply(collections.Counter).reset_index(drop=True)
                sub_df = pd.DataFrame.from_records(counts, index=values.index).fillna(0)
                dummies = sub_df.loc[:, sub_df.columns.isin(selected_dummies)]
                others = sub_df[[col for col in sub_df.columns if col not in selected_dummies]]
                dummies['Others'] = others.any(axis=1)
            else:
                mask = values.isin(selected_dummies)
                values[~mask] = "Others"
                dummies = pd.get_dummies(values)
                    
            dummies = dummies.add_prefix(column_name + "_")
            X = X.join(dummies)
        
        # Remove original categorical columns and return only the expected columns
        X = X.drop(columns=self._categorical_columns, errors='ignore')
        return X.reindex(columns=self.dummy_columns, fill_value=0)

    @property
    def dummy_columns(self):
        return self._dummy_columns

    @property
    def dummy_dict(self):
        return self._dummy_dict
