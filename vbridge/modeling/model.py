import os
import pickle
import numpy as np

import pandas as pd
import shap
import sklearn
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split, StratifiedShuffleSplit
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder as SklearnOneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.utils.class_weight import compute_class_weight
from xgboost import XGBClassifier

from vbridge.utils.directory_helpers import output_workspace

classification_metrics = {
    'Accuracy': sklearn.metrics.accuracy_score,
    'F1 Macro': lambda y_true, y_pred: sklearn.metrics.f1_score(y_true, y_pred, average="macro", zero_division=0),
    'Precision': lambda y_true, y_pred: sklearn.metrics.precision_score(y_true, y_pred, average="macro", zero_division=0),
    'Recall': lambda y_true, y_pred: sklearn.metrics.recall_score(y_true, y_pred, average="macro", zero_division=0),
    'Confusion Matrix': sklearn.metrics.confusion_matrix,
    'AUROC': lambda y_true, y_pred: sklearn.metrics.roc_auc_score(y_true, y_pred, average="macro"),
}


def test(model, X, y):
    y_pred_proba = model.predict_proba(X)
    y_pred = model.predict(X)
    scores = {}
    for name, func in classification_metrics.items():
        if name == 'AUROC':
            scores[name] = func(y, y_pred_proba[:, 1])
        else:
            scores[name] = func(y, y_pred)
    return scores


class Model:
    def __init__(self, topk=10):
        self._preprocessor = None
        self._feature_names = None
        self._model = XGBClassifier(
            eval_metric='logloss',
            enable_categorical=True,
            random_state=42  # Add for reproducibility
        )
        self._explainer = None

    @property
    def model(self):
        return self._model

    def fit(self, X, y):
        y_train = y.values

        # Identify categorical and numerical columns
        categorical_features = X.select_dtypes(include=['object']).columns.tolist()
        numerical_features = X.select_dtypes(include=['int64', 'float64', 'bool']).columns.tolist()
        
        # Create preprocessing pipeline
        preprocessor = ColumnTransformer(
            transformers=[
                ('num', SimpleImputer(strategy='mean'), numerical_features),
                ('cat', SklearnOneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_features)
            ],
            remainder='drop'  # Drop any remaining columns instead of passthrough
        )
        
        # Fit and transform the data
        X_train = preprocessor.fit_transform(X)
        
        # Scale the features
        scaler = MinMaxScaler()
        X_train = scaler.fit_transform(X_train)

        # Store the preprocessing pipeline
        self._preprocessor = preprocessor
        self._scaler = scaler
        
        # Get feature names for later use
        num_feature_names = numerical_features
        cat_feature_names = []
        if categorical_features:
            cat_feature_names = preprocessor.named_transformers_['cat'].get_feature_names_out(categorical_features).tolist()
        self._feature_names = num_feature_names + cat_feature_names

        weights = compute_class_weight(
            class_weight='balanced',
            classes=np.unique(y_train),
            y=y_train
        )
        sample_weight = np.array([weights[np.where(np.unique(y_train) == instance)[0][0]] for instance in y_train])
        
        self._model.fit(
            X_train, 
            y_train, 
            sample_weight=sample_weight,
            verbose=False
        )

    def transform(self, X):
        X = self._preprocessor.transform(X)
        X = self._scaler.transform(X)
        return self._model.predict_proba(X)

    def test(self, X, y):
        y_test = y.values
        X_test = self._preprocessor.transform(X)
        X_test = self._scaler.transform(X_test)
        return test(self.model, X_test, y_test)

    def SHAP(self, X):
        if self._explainer is None:
            self._explainer = shap.TreeExplainer(
                self._model,
                feature_names=self._feature_names
            )
        
        # Store original columns for reference
        original_columns = X.columns
        
        # Transform the data through the preprocessing pipeline
        X_transformed = self._preprocessor.transform(X)
        X_transformed = self._scaler.transform(X_transformed)

        # Get SHAP values
        shap_values = self._explainer.shap_values(X_transformed)
        
        # Handle both binary and multiclass cases
        if isinstance(shap_values, list):
            # Binary classification - use positive class
            shap_values = shap_values[1]
        
        # Ensure feature names match the actual SHAP output dimensions
        if shap_values.shape[1] != len(self._feature_names):
            # This shouldn't happen, but handle it gracefully
            feature_names_adjusted = self._feature_names[:shap_values.shape[1]]
        else:
            feature_names_adjusted = self._feature_names
        
        shap_values = pd.DataFrame(
            shap_values,
            columns=feature_names_adjusted,
            index=X.index
        )
        
        return shap_values
    
    def get_transformed_data(self, X):
        """Get the transformed data that matches SHAP dimensions."""
        X_transformed = self._preprocessor.transform(X)
        X_transformed = self._scaler.transform(X_transformed)
        return pd.DataFrame(
            X_transformed, 
            columns=self._feature_names[:X_transformed.shape[1]],
            index=X.index
        )


class ModelManager:
    def __init__(self, fm, labels=None, task=None):
        self._models = {}
        self.dataset_id = task.dataset_id
        self.task_id = task.task_id
        
        # Use stratified split to ensure balanced classes in train/test
        # Also use a larger test size for more robust evaluation
        if labels and len(labels) == 1:
            # Single label - use stratified split
            label_name = list(labels.keys())[0]
            label_values = labels[label_name]
            
            # Create stratified split with 30% test size for more robust evaluation
            splitter = StratifiedShuffleSplit(n_splits=1, test_size=0.3, random_state=42)
            train_idx, test_idx = next(splitter.split(fm, label_values))
            
            self.X_train = fm.iloc[train_idx]
            self.X_test = fm.iloc[test_idx]
        else:
            # Fallback to regular split if multiple labels or other issues
            self.X_train, self.X_test = train_test_split(fm, test_size=0.3, random_state=42)
        
        self.y_train = pd.DataFrame(index=self.X_train.index)
        self.y_test = pd.DataFrame(index=self.X_test.index)
        for name, label in labels.items():
            self.add_model(label, name=name)

    def add_model(self, label, model=None, name=None):
        if name is None:
            name = "model-{}".format(len(self._models))
        if model is None:
            model = Model()
        self._models[name] = model
        self.y_train[name] = label.loc[self.y_train.index]
        self.y_test[name] = label.loc[self.y_test.index]

    @property
    def models(self):
        return self._models

    def fit_all(self):
        for target_name, model in self._models.items():
            model.fit(self.X_train, self.y_train[target_name])

    def evaluate(self):
        scores = {target_name: model.test(self.X_test, self.y_test[target_name])
                  for target_name, model in self._models.items()}
        return pd.DataFrame(scores).T

    def predict_proba(self, X):
        scores = {}
        for target_name, model in self._models.items():
            scores[target_name] = model.transform(X)[:, 1]
        return scores

    def explain(self, id=None, X=None, target=None):
        if id is not None:
            if id in self.X_train.index:
                X = self.X_train.loc[id]
            elif id in self.X_test.index:
                X = self.X_test.loc[id]
            else:
                raise ValueError("Invalid id.")
            X = X.to_frame().T
        elif X is not None:
            X = X
        else:
            X = pd.concat([self.X_train, self.X_test])
        if target is None:
            return {target: model.SHAP(X) for target, model in self.models.items()}
        else:
            return self.models[target].SHAP(X)
    
    def get_transformed_data(self, target=None, dataset='test'):
        """Get the transformed data that matches SHAP dimensions.
        
        Args:
            target (str): Target model name. If None, uses first available model.
            dataset (str): 'train', 'test', or 'all' for which dataset to transform.
        
        Returns:
            pd.DataFrame: Transformed data matching SHAP dimensions.
        """
        if target is None:
            target = list(self.models.keys())[0]
        
        model = self.models[target]
        
        if dataset == 'train':
            return model.get_transformed_data(self.X_train)
        elif dataset == 'test':
            return model.get_transformed_data(self.X_test)
        elif dataset == 'all':
            X_all = pd.concat([self.X_train, self.X_test])
            return model.get_transformed_data(X_all)
        else:
            raise ValueError("dataset must be 'train', 'test', or 'all'")

    def save(self):
        path = os.path.join(output_workspace, self.dataset_id, self.task_id, 'model.pkl')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as pickle_file:
            pickle.dump(self, pickle_file)

    @staticmethod
    def exist(task):
        path = os.path.join(output_workspace, task.dataset_id, task.task_id, 'model.pkl')
        return os.path.exists(path)

    @staticmethod
    def load(task):
        path = os.path.join(output_workspace, task.dataset_id, task.task_id, 'model.pkl')
        with open(path, 'rb') as pickle_file:
            obj = pickle.load(pickle_file)
        if not isinstance(obj, ModelManager):
            raise ValueError('Serialized object is not a Modeler instance')
        return obj
