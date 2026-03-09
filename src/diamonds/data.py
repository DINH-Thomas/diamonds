import pandas as pd
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer, make_column_selector
from sklearn.impute import SimpleImputer, KNNImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
# Import other necessary libraries here


def load_data(cache = True) -> pd.DataFrame:
    """
    Load the diamonds dataset.

    Parameters
    ----------
    cache : bool, optional
        Whether to cache the dataset, by default True

    Returns
    -------
    pd.DataFrame
        The diamonds dataset
    """
    df_diamonds = sns.load_dataset('diamonds')
    return df_diamonds
    pass

def keep_not_null(row) :
    if 0 in row.values : return False
    return True

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the diamonds dataset.

    Parameters
    ----------
    df : pd.DataFrame
        The diamonds dataset

    Returns
    -------
    pd.DataFrame
        The cleaned diamonds dataset
    """
    df_diamonds = df.dropna()
    df_clean = df_diamonds[df_diamonds.apply(keep_not_null,axis=1)]
    return df_clean

def create_X_y(df: pd.DataFrame) ->tuple[pd.DataFrame, pd.Series]:
    """
    Create the feature matrix X and target vector y from the diamonds dataset.

    Parameters
    ----------
    df : pd.DataFrame
        The preprocessed diamonds dataset

    Returns
    -------
    (pd.DataFrame, pd.Series)
        The feature matrix X and target vector y
    """
    X = df.drop(columns=["price"])
    y = df["price"]
    return X, y

def split_data(X: pd.DataFrame, y: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """
    Split the feature matrix X and target vector y into training and testing sets.

    Parameters
    ----------
    X : pd.DataFrame
        The feature matrix
    y : pd.Series
        The target vector

    Returns
    -------
    (pd.DataFrame, pd.DataFrame, pd.Series, pd.Series)
        The training and testing sets for X and y
    """
    X_train, X_test, y_train, y_test  = train_test_split(X,y, random_state=42)
    return X_train, X_test, y_train, y_test


def preprocess_data(df: pd.DataFrame, fit: bool = True) -> pd.DataFrame:
    """
    Preprocess the diamonds dataset.

    Parameters
    ----------
    df : pd.DataFrame
        The cleaned diamonds dataset

    Returns
    -------
    pd.DataFrame
        The preprocessed diamonds dataset
    """
    cat_pipe = Pipeline(
    [  ("cat_imp",SimpleImputer(strategy="most_frequent"))
      ,("ohe",OneHotEncoder(drop="first",sparse_output=False))
        ])
    num_pipe = Pipeline(
    [("knn_imp", KNNImputer(n_neighbors=5))
     ,("scaler", StandardScaler())
      ])
    preprocessor = ColumnTransformer(
    [("numeric",num_pipe, make_column_selector(dtype_include="number"))
    ,("categorical", cat_pipe, make_column_selector(dtype_exclude="number"))
      ]).set_output(transform="pandas")
    if fit :
        df_preprocessed = preprocessor.fit_transform(df)
    else :
        df_preprocessed = preprocessor.transform(df)
    return df_preprocessed
    





if __name__ == "__main__":
    df = load_data()
    # df_clean = clean_data(df)
    # df_preprocessed = preprocess_data(df_clean)
    # X, y = create_X_y(df_preprocessed)