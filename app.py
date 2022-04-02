# data analysis
import pandas as pd
from numpy import nan
pd.options.plotting.backend = "plotly"

# string processing
import re
from io import StringIO
from thefuzz import process

# web app
import streamlit as st

# FUNCTION: convert txt to dataframe
def convert_to_df(file):
    chats = []

    regex_time = r'\d{2}:\d{2}:\d{2}'
    regex_author = r'\bFrom \s(.*?:)'
    regex_comment = r'(?:\: )(.*$)'

    for line in file.split('\n'):
        
        info = re.search(regex_time, line)
        if info is not None:
            time = info.group()
            author = re.search(regex_author, line).group()
            sender = author.split(' to ')[0].replace('From', '').strip()
            receiver = author.split(' to ')[1].replace(':', '').replace('(Direct Message)', '').strip()
        else:
            message = line.strip()

            chat = {
                'time': time,
                'from': sender,
                'to': receiver,
                'message': message
            }

            chats.append(chat)

    return pd.DataFrame(chats)

# FUNCTION: match students' real and zoom name
def matching_name(students_name, freq_by_name):
    matching = []
    for name in students_name.strip().split('\n'):
        zoom_name, sim_score, sim_idx = process.extractOne(name, freq_by_name['Zoom Name'])
        chat_freq = freq_by_name.set_index('Zoom Name').loc[zoom_name].values[0]
        
        if sim_score < 75:
            zoom_name = nan
            chat_freq = 0
            
        student = {
            'Real Name': name,
            'Zoom Name': zoom_name,
            'Chat Frequency': chat_freq
        }
        matching.append(student)
    
    return pd.DataFrame(matching).sort_values('Chat Frequency', ascending=False).reset_index(drop=True)

# FUNCTION: higlight dataframe row
def highlight(s):
    if s['Chat Frequency'] == 0:
        return ['background-color: #FF7F7F'] * len(s)
    else:
        return [''] * len(s)

# FUNCTION: convert dataframe to csv
@st.cache
def convert_to_csv(df):
    # IMPORTANT: Cache the conversion to prevent computation on every rerun
    return df.to_csv(index=False)

# PAGE CONFIGURATION
st.set_page_config(
    page_title="Zoom Chat Analyzer",
    page_icon="assets/zoom.png",
)
st.markdown("""
            <style>            
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}            
            </style>            
            """, unsafe_allow_html=True)

# TITLE
st.markdown("<h1 style='text-align: center;'>Zoom Chat Analyzer</h1>", unsafe_allow_html=True)

# SIDEBAR
include_private = st.sidebar.checkbox("Include Private Messages")
uploaded_file = st.sidebar.file_uploader("Upload .txt file", type=['txt'])
students_name = st.sidebar.text_area("Copy Paste Students Name Here:", height=250)

# MAIN CONTENT
viz_content = st.container()
placeholder = st.empty()
placeholder.info("Please upload a txt file to be analyzed!")

if uploaded_file is not None:
    placeholder.empty()
    # read uploaded txt file and convert to dataframe
    stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
    string_data = stringio.read()
    chats_df = convert_to_df(string_data)
    
    # concate the row if a chat is still belong to one participant
    chats_df = chats_df.groupby(['time', 'from', 'to'])['message'].apply(' '.join).reset_index()

    # extract period based on user input (interval)
    interval = st.select_slider("Interval (mins):", options=[1, 5, 10, 15, 20, 30, 60])
    freq = f'{interval}min'

    chats_df['period'] = pd.to_datetime(chats_df['time'], format='%H:%M:%S').dt.floor(freq)
    
    # filter row, whether or not to include private chat
    analyze_chat = chats_df[chats_df['to'] == 'Everyone'].copy() if not include_private else chats_df

    # LINE PLOT VISUALIZATION
    # create frequency table for each period
    freq_by_time = analyze_chat['period'].value_counts().sort_index()

    # time series padding
    pad = pd.date_range(start=freq_by_time.index.min(), end=freq_by_time.index.max(), freq=freq)
    freq_table = freq_by_time.reindex(pad).fillna(0)

    # only extract hour and minute component (as string)
    freq_by_time.index = freq_by_time.index.to_series().astype('str').apply(lambda x: x[-8:-3])
    freq_by_time.name = "Chat Frequency"

    # plotly
    fig = freq_by_time.plot(
        title=f"Chat Frequency per {interval} Minute(s) Interval",
        template="simple_white",
        labels=dict(index="Time", value="Frequency")
    )
    fig.update_xaxes(tickangle=-45)
    fig.update_traces(showlegend=False)

    # output
    viz_content.markdown("## Visualization")
    viz_content.plotly_chart(fig, use_container_width=True)
    
    # BAR PLOT VISUALIZATION
    freq_by_name = analyze_chat['from'].value_counts().reset_index().rename(columns={
        'index': 'Zoom Name',
        'from': 'Chat Frequency'
    })

    fig2 = freq_by_name.set_index('Zoom Name').sort_values(by='Chat Frequency', ascending=True).plot(
        kind='barh',
        title=f"Chat Frequency by Zoom Name",
        template="simple_white",
        labels=dict(value="Frequency")
        )
    fig2.update_traces(showlegend=False)
    fig2.update_layout(height=600)
    st.plotly_chart(fig2, use_container_width=True)

    # MATCHING TABLE
    st.markdown("## Matching Real and Zoom Name")

    if students_name:
        match_df = matching_name(students_name, freq_by_name)
        st.dataframe(match_df.style.apply(highlight, axis=1))
    else:
        st.warning("Please input students name based on [Algoritma: Active Student](https://docs.google.com/spreadsheets/d/12FB9410fhRhZp9jl5qLe7x-LGw0QTSfLujA-dE867JE)")

    # RAW CHATS TABLE
    st.markdown("## Raw Chats")
    filter_zoom_name = st.selectbox("Filter by Zoom Name:", options=['All'] + freq_by_name['Zoom Name'].sort_values().to_list())
    
    df = analyze_chat.copy()
    df.drop(columns='period', inplace=True)
    df = df[df['from'] == filter_zoom_name] if filter_zoom_name != 'All' else df

    st.download_button(
        label='📥 Download as CSV',
        data=convert_to_csv(df),
        file_name=f"{uploaded_file.name.split('.')[0]}_{filter_zoom_name}.csv"
    )
    st.dataframe(df)