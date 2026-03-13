import contextlib
from collections.abc import Mapping
from typing import Any, Iterator

import mlflow

from diamonds.params import MLFLOW_TRACKING_URI


_CONFIGURED = False


def configure_mlflow(
    experiment_name: str = "diamonds") -> None:
    """
    Idempotently configure MLflow for this process.

    Parameters
    ----------
    experiment_name :
        Name of the MLflow experiment to use.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    if MLFLOW_TRACKING_URI:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(experiment_name)
    _CONFIGURED = True


@contextlib.contextmanager
def mlflow_run(run_name: str | None = None) -> Iterator[mlflow.ActiveRun]:
    """
    Context manager that ensures MLflow is configured and starts a run.

    Parameters
    ----------
    run_name :
        Optional name for the run.
    """
    configure_mlflow()
    with mlflow.start_run(run_name=run_name) as run:
        yield run


def log_metrics(metrics: Mapping[str, float]) -> None:
    """
    Log a dictionary of metrics to the current MLflow run.

    Parameters
    ----------
    metrics :
        Mapping from metric name to value.
    """
    # mlflow.log_metrics accepts a dict but we keep a simple wrapper
    # so callers do not depend on mlflow directly.
    mlflow.log_metrics(dict(metrics))


def log_params(params: Mapping[str, Any]) -> None:
    """
    Log a dictionary of parameters to the current MLflow run.

    Parameters
    ----------
    params :
        Mapping from parameter name to value.
    """
    mlflow.log_params(dict(params))


def get_registered_version_for_model_info(registered_name: str, model_info) -> str:
    client = mlflow.MlflowClient()
    versions = client.search_model_versions(
        f"name = '{registered_name}' and run_id = '{model_info.run_id}'"
    )
    if not versions:
        raise RuntimeError(f"No registry versions found for model '{name}' and run_id {model_info.run_id}")
    # In practice there should be only one; max is a safe guard
    latest_for_run = max(versions, key=lambda mv: int(mv.version))
    return latest_for_run.version