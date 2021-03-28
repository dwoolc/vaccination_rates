import copy
import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
import matplotlib.pyplot as plt
from pywaffle import Waffle
import plotly.graph_objects as go

class current_vaccine_data():

    def __init__(self, fd_fname, sd_fname, target_val = 53000000, orig_target_date = '31/07/2021', rev_target_date = '31/08/2021'):
        self.read_in_data(fd_fname, sd_fname)
        self.set_targets(target_val, orig_target_date, rev_target_date)
        self.create_waffle_data()
        self.run_rate_stats()
        self.adjust_prior_data()


    def read_in_data(self, fd_fname, sd_fname):
        """Take the govt csv for first and second doses and returns a combined df of both"""
        vac1_df = pd.read_csv(fd_fname)
        vac2_df = pd.read_csv(sd_fname)

        self.vac_df = vac1_df
        self.vac_df['newPeopleVaccinatedSecondDoseByPublishDate'] = vac2_df['newPeopleVaccinatedSecondDoseByPublishDate']
        self.vac_df['cumPeopleVaccinatedSecondDoseByPublishDate'] = vac2_df['cumPeopleVaccinatedSecondDoseByPublishDate']

        self.vac_df = self.vac_df.rename(columns={'newPeopleVaccinatedFirstDoseByPublishDate': 'daily_first_dose',
                                        'cumPeopleVaccinatedFirstDoseByPublishDate': 'cumu_first_dose',
                                        'newPeopleVaccinatedSecondDoseByPublishDate': 'daily_second_dose',
                                        'cumPeopleVaccinatedSecondDoseByPublishDate': 'cumu_second_dose'})

        self.vac_df = self.vac_df.drop(columns=['areaType', 'areaCode'])

        self.vac_df['vac_backlog'] = self.vac_df['cumu_first_dose'] - self.vac_df['cumu_second_dose']
        self.vac_df['daily_all_vac'] = self.vac_df['daily_first_dose'] + self.vac_df['daily_second_dose']

        self.vac_df['date'] = pd.to_datetime(self.vac_df['date'], dayfirst=True)
        for i in self.vac_df.index:
            self.vac_df.loc[i, 'second_vac_cutoff'] = self.vac_df.loc[i, 'date'] + relativedelta(months=3)

        self.vac_df = self.vac_df.sort_values(by=['date']).reset_index(drop=True)

    def set_targets(self, target_val = 53000000, orig_target_date = '31/07/2021', rev_target_date = '31/08/2021'):
        """Set target values and dates to base projections on"""
        orig_target_date = datetime.strptime(orig_target_date, '%d/%m/%Y')
        rev_target_date = datetime.strptime(rev_target_date, '%d/%m/%Y')
        today = datetime.strptime('21/03/2021', '%d/%m/%Y')

        diff_1 = orig_target_date - today
        diff_2 = rev_target_date - today

        self.target_val = target_val
        self.orig_target_date = orig_target_date
        self.rev_target_date = rev_target_date
        self.today = today
        self.diff_1 = diff_1
        self.diff_2 = diff_2



    def create_waffle_data(self):
        """use current data to get % completed today waffle chart. Returns df"""

        current_sd = self.vac_df['cumu_second_dose'].max()
        current_sd_perc = int((current_sd / self.target_val) * 100)

        current_fd = self.vac_df['cumu_first_dose'].max()
        current_fd_perc = int((current_fd / self.target_val) * 100) - current_sd_perc

        unvaxed_perc = 100 - (current_fd_perc + current_sd_perc)
        waffle_data = {'segments': ['Second Dose', 'First Dose', 'Unvaccinated'],
                       'perc': [current_sd_perc, current_fd_perc, unvaxed_perc]}

        self.waffle_df = pd.DataFrame(waffle_data)


    def plot_waffle_chart(self):
        """Plot a waffle chart"""
        fig = plt.figure(
            FigureClass=Waffle,
            rows=10,
            values=self.waffle_df.perc,
            labels=list(self.waffle_df.segments),
            icons='syringe', icon_size=18,
            vertical=True,
            block_arranging_style='snake'
        )

        return fig

    @staticmethod
    def get_stats(df, date):
        """take date and df, return the daily avg in that window for all vacs, fd & sd"""
        tmpdf = df[df['date'] > date]
        daily_avg = tmpdf.daily_all_vac.mean()
        daily_avg_fd = tmpdf.daily_first_dose.mean()
        daily_avg_sd = tmpdf.daily_second_dose.mean()
        return (daily_avg, daily_avg_fd, daily_avg_sd)


    def run_rate_stats(self):
        """get daily vac rate (last 3 months, last month, last week)"""

        prev_3month = self.today - relativedelta(months=3)
        daily_avg_3month = self.get_stats(self.vac_df, prev_3month)

        prev_month = self.today - relativedelta(months=1)
        daily_avg_1month = self.get_stats(self.vac_df, prev_month)

        prev_week = self.today - relativedelta(days=7)
        daily_avg_week = self.get_stats(self.vac_df, prev_week)

        self.daily_avg_3month = daily_avg_3month
        self.daily_avg_1month = daily_avg_1month
        self.daily_avg_week = daily_avg_week


    def raw_nums_remaining(self, avg_rr_all, avg_rr_fd):
        """Get numbers of doses left to target as raw number, and some high level numbers of days left"""
        self.outstanding_1dose = self.target_val - self.vac_df['cumu_first_dose'].max()
        self.req_days_all_fd = self.outstanding_1dose / avg_rr_fd  # using all vaccination capability
        self.req_days_all_cap = self.outstanding_1dose / avg_rr_all  # at current run rate


    def adjust_prior_data(self):
        prior_fd = self.vac_df.loc[0, 'cumu_first_dose']
        prior_sd = self.vac_df.loc[self.vac_df.index.max(), 'cumu_second_dose']
        one_off_allocate = prior_fd - prior_sd

        self.vac_df.loc[0, 'daily_first_dose'] = one_off_allocate
        self.vac_df.loc[0, 'daily_second_dose'] = self.vac_df.loc[0, 'cumu_second_dose']

##################################################################################################

fd_fname = 'first_dose_data_220321.csv'
sd_fname = 'second_dose_data_220321.csv'
test_run = current_vaccine_data(fd_fname, sd_fname)
#test_run.vac_df.to_csv('test_output.csv')