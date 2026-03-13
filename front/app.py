from __future__ import annotations

from time import perf_counter
from typing import Any

import requests
import streamlit as st


API_BASE_URL = "https://diamonds-861302064365.europe-west1.run.app"
PREDICT_ENDPOINT = f"{API_BASE_URL}/predict_one"
ROOT_ENDPOINT = f"{API_BASE_URL}/"

CUT_OPTIONS = ["Fair", "Good", "Very Good", "Premium", "Ideal"]
COLOR_OPTIONS = ["D", "E", "F", "G", "H", "I", "J"]
CLARITY_OPTIONS = ["I1", "SI2", "SI1", "VS2", "VS1", "VVS2", "VVS1", "IF"]

DEFAULT_PAYLOAD = {
    "carat": 0.7,
    "cut": "Ideal",
    "color": "E",
    "clarity": "VS2",
    "depth": 61.7,
    "table": 56.0,
    "x": 5.7,
    "y": 5.73,
    "z": 3.53,
}


def call_api(method: str, url: str, payload: dict[str, Any] | None = None) -> tuple[bool, Any, float, str | None]:
    start = perf_counter()
    try:
        response = requests.request(method=method, url=url, json=payload, timeout=20)
        elapsed_ms = (perf_counter() - start) * 1000
    except requests.RequestException as exc:
        return False, None, 0.0, str(exc)

    try:
        body: Any = response.json()
    except ValueError:
        body = response.text

    if response.ok:
        return True, body, elapsed_ms, None

    error_message = f"HTTP {response.status_code}"
    if body:
        error_message = f"{error_message}: {body}"
    return False, body, elapsed_ms, error_message


def extract_prediction_value(data: Any) -> float | None:
    if isinstance(data, (int, float)):
        return float(data)

    if isinstance(data, str):
        try:
            return float(data)
        except ValueError:
            return None

    if isinstance(data, dict):
        for key in ("prediction", "predicted_price", "price", "estimated_price", "result"):
            value = data.get(key)
            if isinstance(value, (int, float)):
                return float(value)

        for value in data.values():
            prediction = extract_prediction_value(value)
            if prediction is not None:
                return prediction

    if isinstance(data, list):
        for item in data:
            prediction = extract_prediction_value(item)
            if prediction is not None:
                return prediction

    return None


def reset_form() -> None:
    for key, value in DEFAULT_PAYLOAD.items():
        st.session_state[key] = value


st.set_page_config(page_title="Diamonds Predictor", layout="wide")

if "prediction_history" not in st.session_state:
    st.session_state.prediction_history = []

for field_name, default_value in DEFAULT_PAYLOAD.items():
    st.session_state.setdefault(field_name, default_value)

st.title("Diamonds Price Predictor")
st.caption("Interface Streamlit connectee a l'API de prediction de prix des diamants.")

with st.sidebar:
    st.subheader("API distante")
    st.write(PREDICT_ENDPOINT)
    if st.button("Tester la connexion", use_container_width=True):
        api_ok, api_response, latency_ms, api_error = call_api("GET", ROOT_ENDPOINT)
        if api_ok:
            st.success(f"API joignable en {latency_ms:.0f} ms")
            if api_response not in (None, ""):
                st.json(api_response)
        else:
            st.error(api_error or "Impossible de joindre l'API.")

    st.divider()
    st.write("Valeurs de reference")
    st.caption("Les listes reprennent les categories standard du jeu de donnees diamonds.")

intro_col, status_col = st.columns([1.6, 1])

with intro_col:
    st.markdown(
        """
        Renseignez les caracteristiques du diamant puis lancez une prediction.
        Le formulaire envoie directement le JSON attendu par l'endpoint `POST /predict_one`.
        """
    )

with status_col:
    st.info(
        "Champs envoyes : carat, color, clarity, cut, depth, table, x, y, z."
    )

with st.form("diamond_prediction_form"):
    left_col, middle_col, right_col = st.columns(3)

    with left_col:
        carat = st.number_input("Carat", min_value=0.1, max_value=10.0, step=0.01, key="carat")
        cut = st.selectbox("Cut", CUT_OPTIONS, key="cut")
        color = st.selectbox("Color", COLOR_OPTIONS, key="color")

    with middle_col:
        clarity = st.selectbox("Clarity", CLARITY_OPTIONS, key="clarity")
        depth = st.number_input("Depth", min_value=30.0, max_value=90.0, step=0.1, key="depth")
        table = st.number_input("Table", min_value=30.0, max_value=90.0, step=0.1, key="table")

    with right_col:
        x_value = st.number_input("x", min_value=0.1, max_value=15.0, step=0.01, key="x")
        y_value = st.number_input("y", min_value=0.1, max_value=15.0, step=0.01, key="y")
        z_value = st.number_input("z", min_value=0.1, max_value=15.0, step=0.01, key="z")

    payload = {
        "carat": float(carat),
        "cut": cut,
        "color": color,
        "clarity": clarity,
        "depth": float(depth),
        "table": float(table),
        "x": float(x_value),
        "y": float(y_value),
        "z": float(z_value),
    }

    submit_col, preview_col, reset_col = st.columns([1, 1, 1])
    submitted = submit_col.form_submit_button("Predire le prix", use_container_width=True)
    show_preview = preview_col.form_submit_button("Voir le JSON", use_container_width=True)
    reset_clicked = reset_col.form_submit_button("Reinitialiser", use_container_width=True)

if reset_clicked:
    reset_form()
    st.rerun()

if show_preview:
    st.subheader("Payload envoye")
    st.json(payload)

if submitted:
    success, response_body, elapsed_ms, error_message = call_api("POST", PREDICT_ENDPOINT, payload)
    if success:
        prediction_value = extract_prediction_value(response_body)
        st.success(f"Prediction recue en {elapsed_ms:.0f} ms")

        if prediction_value is not None:
            st.metric("Prix estime", f"${prediction_value:,.2f}")
        else:
            st.warning("La reponse ne contient pas de prix numerique identifiable.")

        st.session_state.prediction_history.insert(
            0,
            {
                "payload": payload,
                "response": response_body,
                "latency_ms": round(elapsed_ms, 1),
            },
        )

        st.subheader("Reponse brute")
        if isinstance(response_body, (dict, list)):
            st.json(response_body)
        else:
            st.write(response_body)
    else:
        st.error(error_message or "La prediction a echoue.")
        if response_body not in (None, ""):
            st.subheader("Detail de l'erreur")
            if isinstance(response_body, (dict, list)):
                st.json(response_body)
            else:
                st.write(response_body)

if st.session_state.prediction_history:
    st.divider()
    st.subheader("Dernieres predictions")
    for index, item in enumerate(st.session_state.prediction_history[:5], start=1):
        with st.expander(f"Prediction {index} - {item['latency_ms']:.0f} ms"):
            st.write("Payload")
            st.json(item["payload"])
            st.write("Reponse")
            if isinstance(item["response"], (dict, list)):
                st.json(item["response"])
            else:
                st.write(item["response"])