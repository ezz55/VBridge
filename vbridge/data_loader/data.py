import os

import featuretools as ft
import pandas as pd
import woodwork as ww

from vbridge.utils.directory_helpers import exist_entityset, load_entityset, save_entityset
from vbridge.utils.entityset_helpers import remove_nan_entries


def create_entityset(dataset_id, entity_configs, relationships, table_dir, load_exist=True,
                     save=True, verbose=True):
    """Create a featuretools EntitySet from the dataset configuration.
    
    Args:
        dataset_id (str): Unique identifier for the dataset
        entity_configs (dict): Configuration for each entity in the dataset
        relationships (list): List of relationships between entities
        table_dir (str): Directory containing the CSV files
        load_exist (bool): Whether to load existing entityset
        save (bool): Whether to save the created entityset
        verbose (bool): Whether to print progress information
    """
    if load_exist and exist_entityset(dataset_id):
        es = load_entityset(dataset_id)
    else:
        es = ft.EntitySet(id=dataset_id)
        
        # Add the entities to the entityset
        for table_name, info in entity_configs.items():
            # Safely get date columns for parsing
            time_index = info.get('time_index')
            secondary_index = info.get('secondary_index', [])
            
            # Ensure we have lists for concatenation
            date_columns = []
            if time_index:
                if isinstance(time_index, str):
                    date_columns.append(time_index)
            
            # Handle secondary_index - can be list, dict, or string
            if secondary_index:
                if isinstance(secondary_index, dict):
                    # If it's a dict, get the keys (which are the date columns)
                    date_columns.extend(secondary_index.keys())
                elif isinstance(secondary_index, (list, tuple)):
                    date_columns.extend(secondary_index)
                elif isinstance(secondary_index, str):
                    date_columns.append(secondary_index)
            
            # For mimic-demo, convert date column names to lowercase first, 
            # since the CSV files might have lowercase column names
            if dataset_id == 'mimic-demo':
                date_columns_lower = [col.lower() for col in date_columns]
            else:
                date_columns_lower = date_columns
                
            # Read CSV with explicit datetime parsing - try lowercase first for mimic-demo
            try:
                table_df = pd.read_csv(
                    os.path.join(table_dir, f'{table_name}.csv'),
                    parse_dates=date_columns_lower if dataset_id == 'mimic-demo' else date_columns,
                    low_memory=False  # Added for better memory handling
                )
            except ValueError as e:
                if "Missing column provided to 'parse_dates'" in str(e):
                    # If parsing with lowercase fails, try without date parsing and handle it later
                    table_df = pd.read_csv(
                        os.path.join(table_dir, f'{table_name}.csv'),
                        low_memory=False
                    )
                else:
                    raise e
            
            if dataset_id == 'mimic-demo':
                table_df.columns = [col.upper() for col in table_df.columns]
                
                # Now try to convert the date columns to datetime after uppercase conversion
                for date_col in date_columns:
                    if date_col in table_df.columns:
                        try:
                            table_df[date_col] = pd.to_datetime(table_df[date_col], errors='coerce')
                        except Exception:
                            pass  # Skip if conversion fails
            
            # Remove entries with missing identifiers
            index = info.get('index', table_df.columns[0])
            identifiers = info.get('identifiers', [])
            
            # Ensure identifiers is a list
            if isinstance(identifiers, str):
                identifiers = [identifiers]
            elif not isinstance(identifiers, (list, tuple)):
                identifiers = []
            
            index_columns = identifiers + [index]
            table_df = remove_nan_entries(table_df, index_columns, verbose=verbose)

            # Convert identifiers to strings
            for col in index_columns:
                if col in table_df.columns:
                    table_df[col] = table_df[col].astype('str')

            # Prepare logical types for Woodwork
            logical_types = {}
            for col, dtype in table_df.dtypes.items():
                if pd.api.types.is_datetime64_any_dtype(dtype):
                    logical_types[col] = ww.logical_types.Datetime
                elif pd.api.types.is_numeric_dtype(dtype):
                    if pd.api.types.is_integer_dtype(dtype):
                        logical_types[col] = ww.logical_types.Integer
                    else:
                        logical_types[col] = ww.logical_types.Double
                elif pd.api.types.is_object_dtype(dtype):
                    # Use Categorical for meaningful categorical columns, but avoid auto-interesting values
                    # Special handling for known categorical columns in ADMISSIONS table
                    categorical_cols = ['ADMISSION_TYPE', 'ADMISSION_LOCATION', 'DISCHARGE_LOCATION', 
                                      'INSURANCE', 'RELIGION', 'MARITAL_STATUS', 'ETHNICITY', 'GENDER']
                    if col in categorical_cols:
                        logical_types[col] = ww.logical_types.Categorical
                    else:
                        # Use NaturalLanguage for other text columns to avoid issues
                        logical_types[col] = ww.logical_types.NaturalLanguage

            es.add_dataframe(
                                     dataframe=table_df,
                dataframe_name=table_name,
                                     index=index,
                time_index=time_index if isinstance(time_index, str) else None,
                logical_types=logical_types
            )

        # Add the relationships to the entityset
        for parent, primary_key, child, foreign_key in relationships:
            es.add_relationship(
                parent_dataframe_name=parent,
                parent_column_name=primary_key,
                child_dataframe_name=child,
                child_column_name=foreign_key
            )

        # Add interesting values for categorical columns
        # Re-enabled with proper pandas compatibility handling
        for table_name, info in entity_configs.items():
            if 'interesting_values' in info:
                item_index = info['item_index']
                interesting_values_config = info['interesting_values']
                
                try:
                    # Use string comparison with explicit type checking to avoid pandas ambiguity
                    if isinstance(interesting_values_config, str) and interesting_values_config == 'ALL':
                        # Access dataframe directly (modern featuretools 1.0+ API)
                        unique_values = es[table_name][item_index].unique()
                        # Convert to regular python list to avoid pandas index issues
                        interesting_values = [val for val in unique_values if pd.notna(val)]
                    elif isinstance(interesting_values_config, int):
                        # Access dataframe directly (modern featuretools 1.0+ API)
                        value_counts_result = es[table_name][item_index].value_counts()[:interesting_values_config]
                        # Convert to regular python list to avoid pandas index issues
                        interesting_values = [val for val in value_counts_result.index if pd.notna(val)]
                    else:
                        # Use the configured values directly, but ensure it's a plain list
                        if hasattr(interesting_values_config, '__iter__') and not isinstance(interesting_values_config, str):
                            interesting_values = list(interesting_values_config)
                        else:
                            interesting_values = [interesting_values_config]
                    
                    # Only add if we have values to add and skip if all are None/NaN
                    if (interesting_values is not None 
                        and hasattr(interesting_values, '__len__') 
                        and len(interesting_values) > 0):
                        # Double-check we're not passing any pandas objects that could cause issues
                        clean_values = []
                        for val in interesting_values:
                            if pd.notna(val):
                                # Convert pandas objects to native Python types
                                if hasattr(val, 'item'):
                                    clean_values.append(val.item())
                                else:
                                    clean_values.append(val)
                        
                        if clean_values:  # Only add if we have clean values
                            # Convert values to strings for ITEMID columns to match data type
                            if item_index == 'ITEMID':
                                try:
                                    clean_values = [str(val) for val in clean_values if pd.notna(val)]
                                except (ValueError, TypeError):
                                    pass  # Keep original values if conversion fails
                            
                            es.add_interesting_values(
                                dataframe_name=table_name,
                                values={item_index: clean_values}
                            )
                            
                            if verbose:
                                print(f"Added {len(clean_values)} interesting values for {table_name}.{item_index}")
                                
                except Exception as e:
                    if verbose:
                        print(f"Warning: Could not add interesting values for {table_name}.{item_index}: {str(e)}")
                    continue

        if save:
            save_entityset(es, dataset_id)

    return es
