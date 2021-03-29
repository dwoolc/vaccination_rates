import streamlit as st
from vaccination_data import current_vaccine_data
from projection_data import projected_data

# @TODO: Give option for capacity growth
# @TODO: Fix monthly capacity to reflect actual capacity for historic dates
# @TODO: Fix waffle chart % and size

fd_fname = 'first_dose_data_220321.csv'
sd_fname = 'second_dose_data_220321.csv'

@st.cache
def get_actual_data(fd_fname, sd_fname):
    return current_vaccine_data(fd_fname, sd_fname)


actual_vaccine_data = get_actual_data(fd_fname, sd_fname)

st.sidebar.header('Projection Parameters')
st.sidebar.write('Choose whether to apply random variance to daily capacity, how random to make it and how far back to look for the capacity')

st.sidebar.write('**Select Capacity Average**')
run_rate_radio = st.sidebar.radio('', ["weekly_avg", "monthly_avg", "3_month_avg"], index=0)
st.sidebar.write('**Random Factor To Daily Capacity**')
set_random = st.sidebar.radio('', ["Randomise", "Don't Randomise"], index=0)
st.sidebar.write('**Control Daily Capacity Randomness**')
std_dev = st.sidebar.slider('', min_value=0.05, max_value=0.25)


if set_random == 'Randomise':
    test = projected_data(actual_vaccine_data, randomise_daily_capacity='True', std_dev=std_dev, run_rate_window=run_rate_radio)
else:
    test = projected_data(actual_vaccine_data, randomise_daily_capacity='False', run_rate_window=run_rate_radio)

test.collate_and_project_data()
second_dose_backlog_fig = test.second_dose_backlog_cumu_plot()
daily_doses_fig = test.daily_doses_projection_plot()
waffle = actual_vaccine_data.plot_waffle_chart()
cumu_doses_fig = test.cumulative_doses_plot()
second_dose_as_perc_cap_plot = test.second_doses_by_month_perc_plot()
test.est_target_hit_date()

st.write("""
# UK Covid Vaccine Projections
This is an interactive dashboard to help tracking the progress of the UK government towards its target of vaccinating
all adults by the end of July 2021. That's roughly 53,000,000 people. 

Use the widgets on the left to change the inputs.""")


st.write(test.date_hit)

# slider for % change in capacity

st.subheader("Daily Doses Projection")

st.plotly_chart(daily_doses_fig)

with st.beta_expander("Daily Doses Explanation"):
    st.write("""
    This graph shows a projection first and second doses applied in a given day. The black line is the run rate based on the 
    time window chosen in the sidebar. As we move towards May, the emphasis moves towards the backlog of second doses built up.
    """)

st.subheader("Cumulative Doses Projection")

st.plotly_chart(cumu_doses_fig)

with st.beta_expander("Cumulative Doses Explanation"):
    st.write("""
    This graph is the cumulative version of the above, tracking the total number of doses administered. The black line is the gov't target.
    """)

st.subheader("Second Dose Backlog")

st.plotly_chart(second_dose_backlog_fig)

with st.beta_expander("Second Dose Backlog Explanation"):
    st.write("""
    Diving into what we saw in the first graphic, the heavy early emphasis on first doses results in a large number of second 
    doses which need to be scheduled. As these come due, topping out around 40M, capacity is increasingly filled with second doses.
    """)

st.subheader("Second Doses As % Of Capacity")

st.plotly_chart(second_dose_as_perc_cap_plot)

with st.beta_expander("Cumulative Doses Projection Explanation"):
    st.write("""
    Building on the backlog, a projection of the number of the second doses which need to be applied as a percentage of the
    total vaccine capability. More and more of the doses administered will be for the second dose.
    - Note - Change Jan/Feb/Mar to actual
    """)

st.subheader("Vaccination Coverage of Pop")

st.pyplot(waffle)

with st.beta_expander("% Progress Explanation"):
    st.write("""
    The waffle chart shows the % of people who have received the first and second doses relative to the target.
    """)


st.subheader("General Explainer")

st.write("""The idea behind this dashboard is to help track and visualise the vaccination rate, particularly around how the focus on the first dose has
resulted in a large backlog of second doses. The projections are indicative, not concrete, many people receive their second
dose inside of the 3 month window.

The dashboard uses the government's publically available data on vaccinations. Behind the scenes a script calculates the 
run daily average, schedules the outstanding second doses (due within 3 months), and then fills remaining capacity with first doses.
The script makes some assumptions - that everyone who gets the first dose will get the second, and that the second dose will be
administered within the 3 month cut off.""")
