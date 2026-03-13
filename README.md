## Diamonds: from notebook to package

This repository is a teaching project where you refactor a Jupyter notebook into a reusable Python package (`diamonds`).

## Prerequisites

- **Python**: installed and managed with `pyenv`
- **Virtual environments**: managed with `pyenv-virtualenv`
- **direnv**: installed and enabled in your shell

## 1. Clone the repository

1. Clone this repository and move into the project directory.  

    ```bash
    git clone git@github.com:vivadata/diamonds.git
    cd diamonds
    ```


## 2. Create and activate a virtual environment (pyenv-virtualenv)

1. Create a new virtual environment for this project.  

    ```bash
    pyenv virtualenv 3.11.10 diamonds
    ```


1. Tell this directory to use that virtual environment.  

    ```bash
    pyenv local diamonds
    ```


1. Check that Python now points to the virtualenv.  

    ```bash
    which python
    python --version
    ```


## 3. Configure direnv

1. Allow direnv in this directory (only once).  

    ```bash
    direnv allow
    ```


1. Create an `.envrc` file at the root of the project so the virtualenv is activated automatically when you `cd` into the directory.  

    ```bash
    'echo 'dotenv' > .envrc
    direnv allow
    ```


1. Leave and re-enter the project directory and confirm that the virtualenv is automatically activated.  

    ```bash
    cd ..
    cd Pengouins-demo
    which python
    ```


## 4. Next steps 

- **Explore the notebook**: open `notebooks/Exploration.ipynb`.
- **Identify responsibilities**:
  - data loading and cleaning,
  - feature engineering,
  - model training and evaluation,
  - prediction.
- **Refactor into the package**:
  - move data-related code into `src/diamonds/data.py`,
  - move model-related code into `src/diamonds/model.py`,
  - centralize constants/paths in `src/diamonds/params.py`,
  - implement model saving/loading in `src/diamonds/registry.py`.
- **Train the model**:
  - Udpate   new script `src/diamonds/train.py` to train the model and save it in the `models` directory.
  - run `python -m src.diamonds.train` to train the model and save it in the `models` directory.

## 5. Streamlit apps

- Launch the existing diamonds demo:

    ```bash
    streamlit run front/app.py
    ```

- Launch the "Devinez le nombre" game:

    ```bash
    streamlit run front/app2.py
    ```

