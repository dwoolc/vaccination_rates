import copy
import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
import matplotlib.pyplot as plt
from pywaffle import Waffle
import plotly.graph_objects as go

from vaccination_data import current_vaccine_data

class projected_data():

    def __init__(self, actual_data_obj, run_rate_window= "weekly_avg", randomise_daily_capacity="True", std_dev=0.1):
        self.actual_data = actual_data_obj
        self.projected_df = copy.deepcopy(self.actual_data.vac_df)
        self.daily_avg_3month = self.actual_data.daily_avg_3month[0]
        self.daily_avg_1month = self.actual_data.daily_avg_1month[0]
        self.daily_avg_week = self.actual_data.daily_avg_week[0]
        self.randomise_daily_capacity = randomise_daily_capacity
        self.randomise_std_dev = std_dev
        self.run_rate_window = run_rate_window

    def get_capacity(self):
        """set a capacity value to base projections on"""
        if self.run_rate_window == "weekly_avg":
            self.capacity = self.daily_avg_week
        elif self.run_rate_window == "monthly_avg":
            self.capacity = self.daily_avg_1month
        elif self.run_rate_window == "3_month_avg":
            self.capacity = self.daily_avg_3month

    @staticmethod
    def gen_rand_var(mu=0, sigma=0.1):
        """gen random vals from a normal distribution. mu (mean) and signma (std dv) control dist."""
        s = np.random.normal(mu, sigma, 1)
        return s[0]

    def create_empty_projected_df(self):
        """takes the actual vac_df data, augments with extra columns and then adds an empty projected row for every day
        remaining between now and target"""
        self.projected_df['status'] = 'actual'
        self.projected_df['processed'] = 'False'
        self.projected_df['due_by_today'] = 0
        self.projected_df['sd_overflow'] = 0
        self.projected_df['falling_due_allocated'] = 'NA'
        self.projected_df['day_filled'] = 'True'

        # add a row for each day between now and target
        for i in range(self.actual_data.diff_1.days):
            new_date = self.actual_data.today + relativedelta(days=i)
            # initilise with empty values but correct dates in future
            row = {'date': new_date,
                   'areaName': 'United Kingdom',
                   'daily_first_dose': 0,
                   'daily_second_dose': 0,
                   'cumu_first_dose': 0,
                   'cumu_second_dose': 0,
                   'vac_backlog': 0,
                   'daily_all_vac': 0,
                   'second_vac_cutoff': new_date + relativedelta(months=3),
                   'status': 'projected',
                   'processed': 'False',
                   'due_by_today': 0,
                   'sd_overflow': 0,
                   'falling_due_allocated': 'False',
                   'day_filled': 'False'}
            self.projected_df = self.projected_df.append(row, ignore_index=True)

    def allocate_second_doses(self, date, adj_capacity):
        """fill second doses on a given day, based on first doses distributed on the same day 3 months before. In the case
        that a day has too many to process, seeks the first available slots in the day before, working backwards until
        all scheduled vaccines are completed."""
        amount_due = self.projected_df.loc[self.projected_df['date']==date, 'due_by_today'].values[0]
        if amount_due > adj_capacity:
            self.projected_df.loc[self.projected_df['date']==date, 'daily_second_dose'] = adj_capacity
            self.projected_df.loc[self.projected_df['date']==date, 'day_filled'] = 'True'
            overflow = amount_due - adj_capacity
            day_before = date
            self.projected_df.loc[self.projected_df['date']==date, 'processed'] = 'True'
            while overflow > 0:
                day_before = day_before - relativedelta(days=1)
                if self.projected_df.loc[self.projected_df['date']==day_before, 'day_filled'].values[0] != 'True':
                    currently_allocated = self.projected_df.loc[self.projected_df['date']==day_before, 'daily_second_dose'].values[0]
                    remaining_availability = adj_capacity - currently_allocated
                    if remaining_availability < overflow:
                        filled = remaining_availability
                        self.projected_df.loc[self.projected_df['date']==day_before, 'day_filled'] = 'True'
                        self.projected_df.loc[self.projected_df['date']==day_before, 'processed'] = 'True'
                    else:
                        filled = overflow
                    overflow -= filled
                    self.projected_df.loc[self.projected_df['date']==day_before, 'daily_second_dose'] = currently_allocated + filled
                    self.projected_df.loc[self.projected_df['date']==day_before, 'sd_overflow'] += filled
                else:
                    pass
        else:
            self.projected_df.loc[self.projected_df['date']==date, 'daily_second_dose'] = amount_due
        self.projected_df.loc[self.projected_df['date']==date, 'falling_due_allocated'] = 'True'


    def fill_falling_due(self, i):
        """looks at first doses due to be administered. Schedules them for 3 months time"""
        if self.projected_df.loc[i, 'processed'] == 'True':
            pass
        else:
            due_date = self.projected_df.loc[i, 'second_vac_cutoff']
            due = self.projected_df.loc[i, 'daily_first_dose']
            self.projected_df.loc[self.projected_df['date']==due_date, 'due_by_today'] = due
            self.projected_df.loc[i, 'processed'] = 'True'

    def fill_remaining_space_fd(self, i, adj_capacity):
        """once second doses are allocated, fill remaining space with first doses"""
        if self.projected_df.loc[i, 'daily_second_dose'] >= adj_capacity or self.projected_df.loc[i, 'status'] == 'actual':
            pass
        else:
            self.projected_df.loc[i, 'daily_first_dose'] = adj_capacity - self.projected_df.loc[i, 'daily_second_dose']
            self.projected_df.loc[i, 'day_filled'] = 'True'

    def create_date_filters(self):
        """get a set of dates to work through projections with"""
        months = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september']
        base_filter_date = '01/01/2021'
        base_filter_date = datetime.strptime(base_filter_date, '%d/%m/%Y')
        filter_dict = {}
        for i in range(len(months)):
            filter_dict[months[i]] = base_filter_date + relativedelta(months=i)
        self.filter_dict = filter_dict

    def project_data(self):
        """run through empty projection df, taking 2 month windows of dates, projecting second vaccines falling due, allocating
        and then filling remaining space with first doses. works iteratively so that when a fd is filled, the corresponding sd
        are put in the relavant row to be allocated 3 months later"""

        self.create_date_filters()
        months = list(self.filter_dict.keys())

        for i in range(len(months) - 2):
            valid_data = self.projected_df[self.projected_df['date'] < self.filter_dict[months[i + 2]]]
            valid_data = valid_data[valid_data['date'] >= self.filter_dict[months[i]]]
            for j in valid_data.index:
                if self.randomise_daily_capacity == "True":
                    rand_cap_adj = self.gen_rand_var(mu=0, sigma=self.randomise_std_dev)
                    capacity_adj = self.capacity + (rand_cap_adj * self.capacity)
                else:
                    capacity_adj = self.capacity
                self.fill_remaining_space_fd(j, capacity_adj)
                self.fill_falling_due(j)
                if valid_data.loc[j, 'second_vac_cutoff'] < self.projected_df.date.max():
                    self.allocate_second_doses(valid_data.loc[j, 'second_vac_cutoff'], capacity_adj)

    def complete_projection_df(self):
        """takes the project_data output and then augments with cumsum, updated all vaccine output and backlog"""
        manual_cumsum = self.projected_df[self.projected_df['cumu_first_dose'] == 0]
        for i in manual_cumsum.index:
            prev = i - 1
            self.projected_df.loc[i, 'cumu_first_dose'] = self.projected_df.loc[i, 'daily_first_dose'] + self.projected_df.loc[prev, 'cumu_first_dose']
            self.projected_df.loc[i, 'cumu_second_dose'] = self.projected_df.loc[i, 'daily_second_dose'] + self.projected_df.loc[prev, 'cumu_second_dose']

        self.projected_df['daily_all_vac'] = self.projected_df['daily_first_dose'] + self.projected_df['daily_second_dose']
        self.projected_df['vac_backlog'] = self.projected_df['cumu_first_dose'] - self.projected_df['cumu_second_dose']

    def est_target_hit_date(self):
        """get estimated target hit date based on projections"""
        target_hit = False
        for i in self.projected_df.index:
            if self.projected_df.loc[i, 'cumu_first_dose'] >= self.actual_data.target_val:
                self.date_hit = f"The government will hit its target on {self.projected_df.loc[i, 'date'].date()}"
                target_hit = True
                break
        if not target_hit:
            amount_vaccinated = int(self.projected_df['cumu_first_dose'].max())
            self.date_hit = f"Doesnt look like we're hitting any targets. At this rate we'll get to {amount_vaccinated} vaccinated, with " \
                            f"{self.actual_data.target_val - amount_vaccinated} left"

    def collate_and_project_data(self):
        self.get_capacity()
        self.create_empty_projected_df()
        self.project_data()
        self.complete_projection_df()

    def daily_doses_projection_plot(self):

        fig = go.Figure(data=[
            go.Bar(name='First Dose', x=self.projected_df['date'], y=self.projected_df['daily_first_dose'], marker_color='royalblue'),
            go.Bar(name='Second Dose', x=self.projected_df['date'], y=self.projected_df['daily_second_dose'], marker_color='firebrick')
        ])

        fig.add_shape(type="line",
            xref="x", yref="y",
            x0=self.projected_df['date'].min(), y0=self.capacity, x1=self.projected_df['date'].max(), y1=self.capacity,
            line=dict(
                color="black",
                width=3,
            ))

        fig.add_trace(go.Scatter(
            name='Average Daily Capacity',
            x=[self.projected_df['date'][len(self.projected_df['date'])//2]],
            y=[self.capacity + (self.capacity*.4)],
            text="Average Daily Vaccines Administered - All Types",
            mode="text",
        ))

        # Change the bar mode -> stacked
        fig.update_layout(barmode='stack')
        fig.update_layout(title_text="Daily Doses Projection",
                          xaxis_title="Date",
                          yaxis_title="Number of Doses Administered",font_size=14,
                          font_color="black",
                          title={
                          'y':0.9,
                          'x':0.5,
                          'xanchor': 'center',
                          'yanchor': 'top',
                          'font_size':20})
        return fig


    def cumulative_doses_plot(self):
        fig = go.Figure(data=[
            go.Bar(name='First Dose', x=self.projected_df['date'], y=self.projected_df['cumu_first_dose'], marker_color='royalblue'),
            go.Bar(name='Second Dose', x=self.projected_df['date'], y=self.projected_df['cumu_second_dose'], marker_color='firebrick')
        ])

        fig.add_shape(type="line",
                      xref="x", yref="y",
                      x0=self.projected_df['date'].min(), y0=self.actual_data.target_val, x1=self.projected_df['date'].max(), y1=self.actual_data.target_val,
                      line=dict(
                          color="black",
                          width=3,
                      ))

        fig.add_trace(go.Scatter(
            name='Govt Target',
            x=[self.projected_df['date'][len(self.projected_df['date']) // 2]],
            y=[self.actual_data.target_val + (self.actual_data.target_val * .3)],
            text="All Adults In UK - Gov't Target",
            mode="text",
        ))

        # Change the bar mode -> stacked
        fig.update_layout(barmode='stack')
        fig.update_layout(title_text="Cumulative Doses Projection",
                          xaxis_title="Date",
                          yaxis_title="Cumulative Doses Administered", font_size=14,
                          font_color="black",
                          title={
                              'y': 0.9,
                              'x': 0.5,
                              'xanchor': 'center',
                              'yanchor': 'top',
                              'font_size': 20})
        return fig


    def second_doses_by_month_perc_plot(self):

        second_dose_by_month = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0}
        for i in self.projected_df.index:
            month_val = self.projected_df.loc[i, 'date'].month
            second_dose_by_month[month_val] += self.projected_df.loc[i, 'daily_second_dose']

        month_list = list(second_dose_by_month.values())
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul']
        days_in_month= {'Jan':31,
                       'Feb':28,
                        'Mar':31,
                        'Apr':30,
                        'May':31,
                        'Jun':30,
                        'Jul':31}

        monthly_vax_cap = []

        for i in range(len(months)):
            cap = self.capacity * days_in_month[months[i]]
            monthly_vax_cap.append(cap - month_list[i])

        # plot as bar
        fig = go.Figure(data=[
            go.Bar(name='Monthly Second Doses Req', x=months, y=month_list, marker_color='firebrick'),
            go.Bar(name='Monthly Vax Capability', x=months, y=monthly_vax_cap, marker_color='royalblue')
        ])

        fig.update_layout(barmode='stack')
        fig.update_layout(title_text="Cumulative Doses Projection",
                          xaxis_title="Date",
                          yaxis_title="Cumulative Doses Administered", font_size=14,
                          font_color="black",
                          title={
                              'y': 0.9,
                              'x': 0.5,
                              'xanchor': 'center',
                              'yanchor': 'top',
                              'font_size': 20})
        return fig


    def second_dose_backlog_daily_plot(self):
        fig = go.Figure([go.Scatter(x=self.projected_df['date'], y=self.projected_df['vac_backlog'],
                                    line=dict(color='LightSeaGreen', width=4)),
                         go.Scatter(x=self.projected_df['date'], y=self.projected_df['daily_first_dose'],
                                    line=dict(color='royalblue', width=4)),
                         go.Scatter(x=self.projected_df['date'], y=self.projected_df['daily_second_dose'],
                                    line=dict(color='firebrick', width=4))]
                        )

        fig.update_layout(title_text="Second Dose Backlog",
                          xaxis_title="Date",
                          yaxis_title="Doses",
                          font_color="black",
                          font_size=14,
                          title={
                              'y': 0.9,
                              'x': 0.5,
                              'xanchor': 'center',
                              'yanchor': 'top',
                              'font_size': 20},
                          )
        return fig


    def second_dose_backlog_cumu_plot(self):
        fig = go.Figure([go.Scatter(name='2nd Doses Outstanding', x=self.projected_df['date'], y=self.projected_df['vac_backlog'],
                                    line=dict(color='LightSeaGreen', width=4)),
                         go.Scatter(name='Cumulative 1st Doses', x=self.projected_df['date'], y=self.projected_df['cumu_first_dose'],
                                    line=dict(color='royalblue', width=4)),
                         go.Scatter(name='Cumulative 2nd Doses', x=self.projected_df['date'], y=self.projected_df['cumu_second_dose'],
                                    line=dict(color='firebrick', width=4))]
                        )

        fig.add_shape(type="line",
                      xref="x", yref="y",
                      x0=self.projected_df['date'].min(), y0=self.actual_data.target_val, x1=self.projected_df['date'].max(), y1=self.actual_data.target_val,
                      line=dict(
                          color="black",
                          width=3,
                      ))

        fig.add_trace(go.Scatter(
            name='Govt Target',
            x=[self.projected_df['date'][len(self.projected_df['date']) // 2]],
            y=[self.actual_data.target_val + (self.actual_data.target_val * .1)],
            text="All Adults In UK - Gov't Target",
            mode="text",
        ))

        fig.update_layout(title_text="Second Dose Backlog",
                          xaxis_title="Date",
                          yaxis_title="Doses",
                          font_color="black",
                          font_size=14,
                          title={
                              'y': 0.9,
                              'x': 0.5,
                              'xanchor': 'center',
                              'yanchor': 'top',
                              'font_size': 20},
                          )
        return fig


fd_fname = 'first_dose_data_220321.csv'
sd_fname = 'second_dose_data_220321.csv'
actual_vaccine_data = current_vaccine_data(fd_fname, sd_fname)
test = projected_data(actual_vaccine_data)
test.collate_and_project_data()
#test.projected_df.to_csv('projected_test.csv')
test.second_dose_backlog_cumu_plot()