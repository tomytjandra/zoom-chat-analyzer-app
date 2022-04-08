# data analysis
import pandas as pd
from numpy import nan
from datetime import datetime, timedelta
pd.options.plotting.backend = "plotly"

# string processing
import re
from io import StringIO
from thefuzz import process, fuzz

# web app
import streamlit as st
import pyperclip

# FUNCTION: convert txt to dataframe
def convert_local_chat_to_df(file):
    chats = []

    regex_time = r'\d{2}:\d{2}:\d{2}'
    # regex_author = r'\bFrom \s(.*?:)'

    for line in file.split('\n'):
        
        info = re.search(regex_time, line)
        if info is not None:
            time = info.group()

            author = re.split(' to ', line.strip()[14:], flags=re.IGNORECASE)
            sender = author[0].strip()
            receiver = author[1].strip().replace(':', '').replace('(Direct Message)', '')

            # author = re.search(regex_author, line).group()
            # sender = author.split(' to ')[0].replace('From', '').strip()
            # receiver = author.split(' to ')[1].replace(':', '').replace('(Direct Message)', '').strip()
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

def convert_cloud_chat_to_df(file, start_datetime):
    chats = []

    regex_time = r'\d{2}:\d{2}:\d{2}'

    for line in file.split('\n'):
        line = line.split('\t')
        info = re.search(regex_time, line[0])

        if info is not None:
            chat_time = datetime.strptime(info.group(), '%H:%M:%S')
            chat_timedelta = timedelta(hours=chat_time.hour, minutes=chat_time.minute, seconds=chat_time.second)
            time = start_datetime + chat_timedelta
            sender = line[1].replace(':', '')
            message = line[2].strip()
        else:
            message = line[0].strip()
        
        chat = {
            'time': time,
            'from': sender,
            'to': "Everyone",
            'message': message
        }

        chats.append(chat)

    return pd.DataFrame(chats)

# FUNCTION: match participants' real and zoom name
def matching_name(participants_name, freq_by_name):
    matching = []
    zoom_name_list = freq_by_name['Zoom Name']
    participants_name_list = participants_name.strip().split('\n')
    SCORE_CUTOFF = 80

    # Real Name MATCH TO Zoom Name
    for name in participants_name_list:
        # try several approaches
        result_list = [
            process.extractOne(name, zoom_name_list, score_cutoff=SCORE_CUTOFF),
            process.extractOne(name, zoom_name_list, scorer=fuzz.partial_ratio, score_cutoff=SCORE_CUTOFF),
            process.extractOne(name, zoom_name_list, scorer=fuzz.token_sort_ratio, score_cutoff=SCORE_CUTOFF)
        ]
        # get best match
        result = max(result_list, key=lambda x: x[1] if x is not None else 0)
        if result is not None:
            zoom_name, sim_score, sim_idx = result
            chat_freq = freq_by_name.iloc[sim_idx]['Chat Frequency']
        else:
            # if the result is not good enough (below score_cutoff)
            zoom_name = None
            chat_freq = 0

        matching.append({
            'Real Name': name,
            'Zoom Name': zoom_name,
            'Chat Frequency': chat_freq
        })

    # list to dataframe
    match_df = pd.DataFrame(matching).sort_values(
        by=['Chat Frequency', 'Real Name'],
        ascending=[False, True]).reset_index(drop=True)

    # Remaining Zoom Name MATCH TO Real Name
    remaining = []
    remaining_set = set(zoom_name_list.values) - set(match_df['Zoom Name'].unique())
    for zoom_name in remaining_set:
        remaining.append({
            'Zoom Name': zoom_name,
            'Chat Frequency': freq_by_name[freq_by_name['Zoom Name'] == zoom_name]['Chat Frequency'].values[0]
        })

    # list to dataframe
    remaining_df = pd.DataFrame(remaining).sort_values(
        by=['Chat Frequency', 'Zoom Name'],
        ascending=[False, True]).reset_index(drop=True)

    return match_df, remaining_df

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
st.markdown(
    """
    <style>            
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .footer {
        position: fixed;
        display: block;
        width: 100%;
        bottom: 0;
        color: rgba(49, 51, 63, 0.4);
    }
    a:link , a:visited{
        color: rgba(49, 51, 63, 0.4);
        background-color: transparent;
        text-decoration: underline;
    }
    </style>
    <div class="footer">
        <p>
            Developed with ❤ by 
            <a href="https://github.com/tomytjandra" target="_blank">
            Tomy Tjandra
            </a>
        </p>
    </div>
    """, unsafe_allow_html=True)

# TITLE
st.markdown("<h1 style='text-align: center;'>Zoom Chat Analyzer</h1>", unsafe_allow_html=True)

# SIDEBAR
txt_source = st.sidebar.selectbox("Choose the source of txt file", options=["Cloud", "Local"])
if txt_source == "Local":
    include_private = st.sidebar.checkbox("Include Private Messages")
else:
    include_private = False
uploaded_file = st.sidebar.file_uploader("Upload chat (txt file)", type=['txt'])
participants_name = st.sidebar.text_area("Copy Paste Real Participants' Name Here:", height=250)

# MAIN CONTENT
viz_content = st.container()
placeholder = st.empty()
placeholder.info("Please upload a txt file to be analyzed!")

if uploaded_file is not None:
    placeholder.empty()
    # read uploaded txt file and convert to dataframe
    stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
    string_data = stringio.read()
    
    if txt_source == "Local":
        chats_df = convert_local_chat_to_df(string_data)
    else:
        date, time = re.findall(r'\d{6,}', uploaded_file.name)
        start_datetime = datetime.strptime(date+time, '%Y%m%d%H%M%S') + timedelta(hours=7)
        # start_time = start_datetime.time()
        # start_timedelta = timedelta(hours=start_time.hour, minutes=start_time.minute, seconds=start_time.second)
        chats_df = convert_cloud_chat_to_df(string_data, start_datetime)
    
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

    if participants_name:
        match_df, remaining_df = matching_name(participants_name, freq_by_name)
        st.button("Copy DataFrame to Clipboard", on_click=match_df.to_clipboard())
        st.dataframe(match_df.style.apply(highlight, axis=1))
        st.markdown("### Un-match Zoom Name")
        st.dataframe(remaining_df)
    else:
        st.warning("Please input participants' name based on [Algoritma: Active Student](https://docs.google.com/spreadsheets/d/12FB9410fhRhZp9jl5qLe7x-LGw0QTSfLujA-dE867JE)")

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