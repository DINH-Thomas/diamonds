import random

import streamlit as st


def initialize_game() -> None:
    if "target_number" not in st.session_state:
        reset_game()


def reset_game() -> None:
    st.session_state.target_number = random.randint(1, 100)
    st.session_state.attempts = 0
    st.session_state.feedback = "Faites votre premiere proposition."
    st.session_state.history = []
    st.session_state.game_won = False


def handle_guess(guess: int) -> None:
    if st.session_state.game_won:
        return

    st.session_state.attempts += 1
    st.session_state.history.append(guess)

    if guess < st.session_state.target_number:
        st.session_state.feedback = "C'est plus grand."
        return

    if guess > st.session_state.target_number:
        st.session_state.feedback = "C'est plus petit."
        return

    st.session_state.game_won = True
    st.session_state.feedback = (
        f"Bravo ! Vous avez trouve le nombre en {st.session_state.attempts} essai(s)."
    )


st.set_page_config(page_title="Devinez le nombre")

initialize_game()

st.title("Devinez le nombre")
st.markdown("Je pense a un nombre entre 1 et 100. A vous de le retrouver.")

with st.form("guess_form"):
    guess = st.number_input(
        "Votre proposition",
        min_value=1,
        max_value=100,
        value=50,
        step=1,
        disabled=st.session_state.game_won,
    )
    submitted = st.form_submit_button("Valider")

if submitted:
    handle_guess(int(guess))

if st.session_state.game_won:
    st.success(st.session_state.feedback)
else:
    st.info(st.session_state.feedback)

st.write(f"Nombre d'essais : {st.session_state.attempts}")

if st.session_state.history:
    st.write("Tentatives precedentes : " + ", ".join(map(str, st.session_state.history)))

if st.button("Rejouer"):
    reset_game()
    st.rerun()