import os
from datetime import timedelta

from vbridge.task.task import Task
from vbridge.utils.directory_helpers import ROOT

from ..schema import entity_configs, ignore_variables, relationships
from ..selector_variable import mimic_cohort_selector

mimic_demo_dir = os.path.join(ROOT, 'data/physionet.org/files/mimiciii-demo/1.4/')


def mimic_48h_in_admission_mortality_task():
    target_entity = 'ADMISSIONS'

    def get_cutoff_times(es):
        # Access dataframe directly (modern featuretools 1.0+ API)
        entity_df = es[target_entity]
        
        # Get the index and time_index column names from the entity configuration
        index_col = entity_configs[target_entity]['index']
        time_col = entity_configs[target_entity]['time_index']
        
        cutoff_time = entity_df.loc[:, [index_col, time_col]]
        cutoff_time.columns = ['instance_id', 'time']
        cutoff_time['time'] += timedelta(hours=72)  # Extended to 72h to capture CHARTEVENTS data
        return cutoff_time

    return Task(
        dataset_id='mimic-demo',
        table_dir=mimic_demo_dir,
        entity_configs=entity_configs,
        relationships=relationships,
        ignore_variables=ignore_variables,

        target_entity=target_entity,
        cutoff_times_fn=get_cutoff_times,
        backward_entities=['CHARTEVENTS'],
        forward_entities=['PATIENTS', 'ADMISSIONS'],

        task_id='in-admission mortality',
        short_desc='Whether the patient will die or survive within this admission.',
        label_fns={
            'mortality': {
                'label_values': lambda es: es['ADMISSIONS']['HOSPITAL_EXPIRE_FLAG'],
                'label_type': 'boolean',
                'label_extent': ['low-risk', 'high-risk']
            }
        },
        selector_fn=mimic_cohort_selector
    )
