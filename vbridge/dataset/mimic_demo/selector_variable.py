import featuretools as ft


def mimic_cohort_selector(es=None):
    selector_vars = [{
        'name': 'Gender',
        'type': 'categorical',
        'feature': None,
        'extent': ['F', 'M']
    }]
    if es is not None:
        # Build gender selector (feature) using modern featuretools API
        # Create the identity feature for GENDER column in PATIENTS dataframe
        gender_identity = ft.IdentityFeature(es['PATIENTS'].ww['GENDER'])
        
        # Create direct feature from PATIENTS to ADMISSIONS using dataframe names as strings
        gender = ft.DirectFeature(gender_identity, 'ADMISSIONS')
        selector_vars[0]['feature'] = gender

    return selector_vars
