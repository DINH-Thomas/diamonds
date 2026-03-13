import streamlit as st

import diamonds.data
import pandas as pd
import numpy as np
import plotly.express as px

from diamonds.data import load_data

st.title("Diamonds Streamlit!")
st.markdown("# Diamonds")

df_diamonds = load_data()

st.markdown("## Data")
st.slider("Depth", min_value=0.0, max_value=60.0, value=(0.0, 60.0), step=5.0, key="depth_slider")
#Plot le prix en histogramme
fig = px.histogram(df_diamonds, x="price", nbins=50, title="Distribution des prix des diamants")
st.plotly_chart(fig)

st.dataframe(df_diamonds)

if st.button("Ne pas cliquer"):
    st.write("Oh non il neige !")
    st.snow()