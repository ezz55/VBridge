import warnings
import featuretools as ft
import numpy as np
import pandas as pd
from featuretools.selection import (
    remove_highly_correlated_features, remove_highly_null_features,
    remove_low_information_features,)

from vbridge.utils.directory_helpers import exist_fm, load_fm, save_fm
from vbridge.utils.entityset_helpers import find_path

# Suppress pandas FutureWarnings that come from featuretools internal operations
warnings.filterwarnings('ignore', category=FutureWarning, module='pandas')
warnings.filterwarnings('ignore', category=FutureWarning, module='featuretools')

class Featurization:

    def __init__(self, es, task):
        self.es = es
        self.task = task
        self.target_entity = task.target_entity
        self.entity_ids = task.forward_entities + task.backward_entities
        self.es.add_last_time_indexes()

    @staticmethod
    def select_features(fm, fl=None):
        if fl is None:
            # Use less aggressive feature selection to preserve more features
            fm = remove_highly_null_features(fm, pct_null_threshold=0.95)  # Allow more nulls
            fm = remove_low_information_features(fm)
            fm = remove_highly_correlated_features(fm, pct_corr_threshold=0.95)
            return fm
        else:
            # Use less aggressive feature selection to preserve more features  
            fm, fl = remove_highly_null_features(fm, fl, pct_null_threshold=0.95)  # Allow more nulls
            fm, fl = remove_low_information_features(fm, fl)
            fm, fl = remove_highly_correlated_features(fm, fl, pct_corr_threshold=0.95)
            return fm, fl

    @staticmethod
    def select_features_permissive(fm, fl=None):
        """Very permissive feature selection for medical data that preserves important WHERE clause features"""
        if fl is None:
            # Only remove features that are completely null (100% null)
            fm = remove_highly_null_features(fm, pct_null_threshold=0.99)
            # Skip low information filtering for medical data
            # Skip correlation filtering to preserve related medical measurements
            return fm
        else:
            # Only remove features that are completely null (100% null)
            fm, fl = remove_highly_null_features(fm, fl, pct_null_threshold=0.99)
            # Skip low information filtering for medical data
            # Skip correlation filtering to preserve related medical measurements
            return fm, fl

    @staticmethod
    def remove_uninterpretable_features(fm, fl):
        where_prefix = set([f.split(' WHERE ')[0] for f in fm.columns if ' WHERE ' in f])
        uninterpretable_cols = []
        for column in fm.columns:
            if np.array([prefix in column for prefix in where_prefix]).any() \
                    and ' WHERE ' not in column:
                uninterpretable_cols.append(column)
        for column in uninterpretable_cols:
            fm.pop(column)
        fl = [f for f in fl if f.get_name() in fm.columns]
        return fm, fl

    @staticmethod
    def merge_features(fm_list, fl_list):
        index = fm_list[0].index
        feature_matrix = pd.DataFrame(fm_list[0])
        feature_list = [f for f in fl_list[0]]
        for fm, fl in zip(fm_list, fl_list):
            for f in fl:
                col = f.get_name()
                if col in feature_matrix.columns:
                    continue
                feature_matrix[col] = fm[col]
                feature_list.append(f)
        return feature_matrix.loc[index], feature_list

    def generate_features(self, save=True, load_exist=False, verbose=True):
        if load_exist and exist_fm(self.task.dataset_id, self.task.task_id):
            fm, fl = load_fm(self.task.dataset_id, self.task.task_id)
        else:
            fp = []
            cutoff_time = self.task.get_cutoff_times(self.es)
            if 'PATIENTS' in self.entity_ids:
                fp.append(self._patients(cutoff_time=cutoff_time, verbose=verbose))
            if 'CHARTEVENTS' in self.entity_ids:
                fp.append(self._chart_events(cutoff_time=cutoff_time, verbose=verbose))
            if 'SURGERY_VITAL_SIGNS' in self.entity_ids:
                fp.append(self._vital_signs(cutoff_time=cutoff_time, verbose=verbose))
            if 'LABEVENTS' in self.entity_ids:
                fp.append(self._lab_tests(cutoff_time=cutoff_time, verbose=verbose))

            fm, fl = Featurization.merge_features([f[0] for f in fp], [f[1] for f in fp])
            fm, fl = Featurization.remove_uninterpretable_features(fm, fl)
            # Apply feature selection
            fm, fl = Featurization.select_features(fm, fl)

        fm.index = fm.index.astype('str')
        if save:
            save_fm(fm, fl, self.task.dataset_id, self.task.task_id)
        return fm, fl

    def _generate_features(self, target_entity=None, cutoff_time=None, **kwargs):
        if cutoff_time is None:
            target_df = self.es[self.target_entity]
            
            index_col = self.task.entity_configs[self.target_entity]['index']
            time_col = self.task.entity_configs[self.target_entity]['time_index']
            
            cutoff_time = target_df.loc[:, [index_col, time_col]]
            cutoff_time.columns = ['instance_id', 'time']

        fm, fl = ft.dfs(
            entityset=self.es,
            target_dataframe_name=self.target_entity,
                        allowed_paths=find_path(self.es, self.target_entity, target_entity),
            ignore_columns=self.task.ignore_variables,
                        cutoff_time=cutoff_time,
            max_depth=2,
            include_cutoff_time=True,
            **kwargs
        )

        return fm, fl

    def _patients(self, **kwargs):
        return self._generate_features(
            target_entity='PATIENTS',
            trans_primitives=[],
            max_features=100,
            **kwargs
        )

    def _vital_signs(self, **kwargs):
        return self._generate_features(
            target_entity='SURGERY_VITAL_SIGNS',
            agg_primitives=["mean", "std", "trend"],
            where_primitives=["mean", "std", "trend"],
            trans_primitives=[],
            max_features=100,
            **kwargs
        )

    def _chart_events(self, **kwargs):
        return self._generate_features(
            target_entity='CHARTEVENTS',
            agg_primitives=["mean", "std", "trend"],
            where_primitives=["mean", "std", "trend"],
            trans_primitives=[],
            max_features=100,
            **kwargs
        )

    def _lab_tests(self, **kwargs):
        return self._generate_features(
            target_entity='LABEVENTS',
            agg_primitives=["mean"],
            where_primitives=["mean"],
            trans_primitives=[],
            max_features=100,
            **kwargs
        )
