import streamlit as st

st.title('Counter Example')
if 'count' not in st.session_state:
    st.session_state.count = [1]

increment = st.button('Increment')
if increment:
    st.session_state.count.append(st.session_state.count[-1] + 1)

for i in st.session_state.count:
    st.markdown(i)