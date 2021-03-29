# vaccination_rates

Code creating a projection for UK vaccination coverage trajectory based on previous rates. 

- Three scripts are used to produce a streamlit dashboard. Actual data is read and prepped in the vaccination_data class. 
- This is called as an attribute of the projection data class which projects data to a designated target date.
- The porjections and plots are called into a Streamlit dash to enable interactive inputs for assumptions.

Early versions of this code used csvs for importing data, also provided.

Full writeup available on <a href="https://www.danielwoolcott.info/projects/uk_vax_backlog">portfolio website</a>.  
