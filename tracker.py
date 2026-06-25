import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import datetime
import calendar
import requests
import io

# --- PAGE SETUP ---
st.set_page_config(layout="wide", page_title="Daily Habit Tracker", page_icon="💖")

# --- CLOUD STORAGE SYSTEM (JSONBin) ---
# We pull these securely from Streamlit's secret vault
API_KEY = st.secrets["JSONBIN_KEY"]
BIN_ID = st.secrets["JSONBIN_ID"]
HEADERS = {
    'Content-Type': 'application/json',
    'X-Master-Key': API_KEY
}
URL = f"https://api.jsonbin.io/v3/b/{BIN_ID}"

def save_data():
    """Pushes the current session state to the JSONBin cloud."""
    # Convert DataFrames to JSON strings so they can be transmitted
    data_to_save = {
        'habit_list': st.session_state.habit_list,
        'memory': {k: v.to_json() for k, v in st.session_state.memory.items()},
        'deadlines_df': st.session_state.deadlines_df.to_json(date_format='iso')
    }
    # Send the PUT request to overwrite the bin with new data
    requests.put(URL, json=data_to_save, headers=HEADERS)

# --- CORE ALGORITHM: STREAK CALCULATOR ---
def calculate_longest_streak(df):
    streaks = []
    for index, row in df.iterrows():
        current_max = 0
        current_streak = 0
        for val in row:
            if val:
                current_streak += 1
                current_max = max(current_max, current_streak)
            else:
                current_streak = 0
        streaks.append(current_max)
    return streaks

# --- 1. INITIALIZE DATABASE & LOAD FROM CLOUD ---
if 'data_loaded' not in st.session_state:
    try:
        # Try to fetch existing data from the cloud
        response = requests.get(URL, headers=HEADERS)
        if response.status_code == 200:
            cloud_data = response.json()['record']
            
            st.session_state.habit_list = cloud_data['habit_list']
            
            # Reconstruct the memory dictionaries back into Pandas DataFrames
            st.session_state.memory = {
                k: pd.read_json(io.StringIO(v)) for k, v in cloud_data['memory'].items()
            }
            
            # Reconstruct deadlines and ensure the date format is correct
            deadlines = pd.read_json(io.StringIO(cloud_data['deadlines_df']))
            deadlines['Deadline'] = pd.to_datetime(deadlines['Deadline']).dt.date
            st.session_state.deadlines_df = deadlines
        else:
            raise ValueError("Bin empty or not found")
            
    except Exception as e:
        # If it fails (or first time running), load the defaults
        st.session_state.habit_list = [
            "Habit 1", 
            "Habit 2", 
            "Habit 3", 
            "Habit 4",
            "Habit 5"
        ]
        st.session_state.memory = {}
        st.session_state.deadlines_df = pd.DataFrame(
            columns=["Done", "Task", "Deadline"],
            data=[[False, "Submit Microeconomics Assignment", datetime.date.today() + datetime.timedelta(days=3)]]
        )
        save_data() # Instantly save defaults to the cloud
        
    st.session_state.data_loaded = True

# --- 2. COMPRESSED HEADER & TIME MACHINE ---
col_title, col_year, col_month = st.columns([2, 1, 1], vertical_alignment="bottom")

with col_title:
    st.title("Daily Habit Tracker Website ⚡")
with col_year:
    selected_year = st.selectbox("Year", range(2024, 2030), index=2) 
with col_month:
    months = list(calendar.month_name)[1:]
    current_month_index = datetime.date.today().month - 1
    selected_month_name = st.selectbox("Month", months, index=current_month_index)
    selected_month_num = months.index(selected_month_name) + 1

# Generate the data for the selected month automatically
month_key = f"{selected_year}-{selected_month_num:02d}"
if month_key not in st.session_state.memory:
    num_days = calendar.monthrange(selected_year, selected_month_num)[1]
    cols = [f"{calendar.month_abbr[selected_month_num]} {str(d).zfill(2)}" for d in range(1, num_days + 1)]
    st.session_state.memory[month_key] = pd.DataFrame(False, index=st.session_state.habit_list, columns=cols)
    save_data()

active_df = st.session_state.memory[month_key]

# --- 3. MODERN TAB NAVIGATION ---
tab1, tab2, tab3 = st.tabs(["📋 The Master Grid", "📈 Analytics & Streaks", "📚 Educational Deadlines"])

# ==========================================
# TAB 1: THE MASTER GRID (Dynamic Row Engine)
# ==========================================
with tab1:
    grid_df = active_df.reset_index(names=["Habit"])
    
    edited_grid = st.data_editor(
        grid_df, 
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic" 
    )
    
    if not grid_df.equals(edited_grid):
        edited_grid["Habit"] = edited_grid["Habit"].fillna("New Habit 📝")
        for col in edited_grid.columns:
            if col != "Habit":
                edited_grid[col] = edited_grid[col].fillna(False).astype(bool)
        
        new_active = edited_grid.set_index("Habit")
        st.session_state.memory[month_key] = new_active
        st.session_state.habit_list = list(dict.fromkeys(new_active.index.tolist()))
        save_data()
        st.rerun()

# ==========================================
# TAB 2: ANALYTICS & STREAKS
# ==========================================
with tab2:
    if not active_df.empty:
        st.subheader("Weekly Averages")
        all_days = active_df.columns
        weeks = [(f"Week {i+1}", all_days[i*7 : (i+1)*7]) for i in range((len(all_days) + 6) // 7)]
        cols = st.columns(len(weeks))
        
        for i, (week_name, week_days) in enumerate(weeks):
            with cols[i]:
                week_data = active_df[week_days]
                total_cells = len(active_df) * len(week_days)
                week_percentage = (week_data.sum().sum() / total_cells) * 100 if total_cells > 0 else 0
                
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=week_percentage,
                    number={'suffix': "%", 'font': {'size': 26, 'color': "#82b1ff"}}, 
                    gauge={
                        'axis': {'range': [None, 100], 'visible': False},
                        'bar': {'color': "#ff80ab", 'thickness': 0.8}, 
                        'bgcolor': "rgba(255,255,255,0.05)",
                    }
                ))
                fig.update_layout(height=160, margin=dict(l=10, r=10, t=10, b=10), template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True, key=f"gauge_week_{i}_{month_key}")
                st.markdown(f"<p style='text-align: center; color: #82b1ff; font-weight: bold;'>{week_name}</p>", unsafe_allow_html=True)
        
        st.divider()
        
        col_chart1, col_chart2 = st.columns(2)
        daily_completion = active_df.sum()
        daily_percentages = (daily_completion / len(active_df)) * 100
        chart_df = pd.DataFrame({"Day": daily_percentages.index, "Completion %": daily_percentages.values})
        
        with col_chart1:
            st.write("**Completion Trend**")
            fig_area = px.area(chart_df, x="Day", y="Completion %", template="plotly_dark", color_discrete_sequence=['#82b1ff'])
            fig_area.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=250)
            st.plotly_chart(fig_area, use_container_width=True, key="area_chart_trend")
            
        with col_chart2:
            st.write("**Daily Count**")
            fig_bar = px.bar(x=daily_completion.index, y=daily_completion.values, template="plotly_dark", color_discrete_sequence=['#ff80ab'])
            fig_bar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=250)
            st.plotly_chart(fig_bar, use_container_width=True, key="bar_chart_count")

        st.divider()
        st.subheader("Daily Progress & Streaks")
        
        total_days = len(active_df.columns)
        actual_completed = active_df.sum(axis=1)
        streaks = calculate_longest_streak(active_df)
        
        analysis_df = pd.DataFrame({
            "Habit": active_df.index,
            "Goal": total_days,
            "Actual": actual_completed,
            "Rate": (actual_completed / total_days) * 100,
            "Longest Streak": streaks
        })
        
        st.dataframe(
            analysis_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Habit": st.column_config.TextColumn("Habit Name", width="medium"),
                "Goal": st.column_config.NumberColumn("Goal", format="%d days"),
                "Actual": st.column_config.NumberColumn("Completed", format="%d days"),
                "Rate": st.column_config.ProgressColumn(
                    "Percentage",
                    help="Visual completion rate",
                    format="%.0f %%",
                    min_value=0,
                    max_value=100,
                ),
                "Longest Streak": st.column_config.NumberColumn("🔥 Longest Streak", format="%d days")
            }
        )
    else:
        st.info("No habits added yet. Go to 'The Master Grid' to add your first habit!")

# ==========================================
# TAB 3: EDUCATIONAL DEADLINES 
# ==========================================
with tab3:
    st.subheader("Upcoming Deadlines & Milestones")
    
    with st.form("add_deadline_form", clear_on_submit=True):
        col_t, col_d, col_btn = st.columns([3, 1, 1])
        with col_t:
            new_task = st.text_input("New Educational Task:")
        with col_d:
            new_date = st.date_input("Deadline:", datetime.date.today())
        with col_btn:
            st.write("") 
            st.write("") 
            submit_deadline = st.form_submit_button("➕ Add Task", use_container_width=True)
            
        if submit_deadline and new_task.strip() != "":
            new_deadline_row = pd.DataFrame([[False, new_task, new_date]], columns=["Done", "Task", "Deadline"])
            st.session_state.deadlines_df = pd.concat([st.session_state.deadlines_df, new_deadline_row], ignore_index=True)
            save_data() 
            st.rerun()

    if not st.session_state.deadlines_df.empty:
        # Create a display copy so we can dynamically calculate the "Urgency Status"
        display_df = st.session_state.deadlines_df.copy()
        
        def get_urgency_status(row):
            if row['Done']: return "✅ Completed"
            if pd.isnull(row['Deadline']): return "⏳ No Date"
            
            # Ensure deadline is compared as a date object
            dl_date = row['Deadline']
            if isinstance(dl_date, datetime.datetime):
                dl_date = dl_date.date()
                
            days_left = (dl_date - datetime.date.today()).days
            
            if days_left < 0: return f"🚨 Overdue ({abs(days_left)}d)"
            if days_left <= 1: return f"🔴 {days_left} day(s) left"
            if days_left <= 4: return f"🟠 {days_left} days left"
            if days_left <= 8: return f"🟢 {days_left} days left"
            return f"🔵 {days_left} days left"

        # Insert the Status column at the beginning
        display_df.insert(0, "Urgency", display_df.apply(get_urgency_status, axis=1))
        
        # Sort so "Done = False" tasks stay at top, sorted by closest deadline
        display_df = display_df.sort_values(by=["Done", "Deadline"]).reset_index(drop=True)
        
        # Render the editor with dynamic rows enabled (Allows Deletion!)
        edited_deadlines = st.data_editor(
            display_df,
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Urgency": st.column_config.TextColumn("Urgency", disabled=True, width="small"),
                "Done": st.column_config.CheckboxColumn("Done"),
                "Task": st.column_config.TextColumn("Educational Task", width="large"),
                "Deadline": st.column_config.DateColumn("Deadline", format="MMM DD, YYYY")
            }
        )
        
        # If user edits the grid (deletes row, changes date, clicks done)
        if not display_df.equals(edited_deadlines):
            # Clean up new rows
            edited_deadlines["Task"] = edited_deadlines["Task"].fillna("New Task")
            
            # Strip the temporary "Urgency" column before saving to database
            st.session_state.deadlines_df = edited_deadlines.drop(columns=["Urgency"])
            save_data() 
            st.rerun()
    else:
        st.info("No active deadlines! You're all caught up. 🎉")