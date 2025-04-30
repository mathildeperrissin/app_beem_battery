import streamlit as st

st.title("Hello Streamlit 👋")
st.write("Bienvenue sur mon app déployée avec Streamlit Cloud !")

name = st.text_input("Quel est ton prénom ?")
if name:
    st.success(f"Bonjour {name} !")

